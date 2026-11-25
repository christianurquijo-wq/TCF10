"""Piezas compartidas de la vista para Atenea: datos, filtros globales (barra lateral) y estados en lenguaje
institucional. Sin montos ni clasificación de riesgo: solo datos objetivos de asistencia, horas y avance."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from tcf10 import config as C
from tcf10 import data
from tcf10 import ui

FILTROS = [("cohorte", "Cohorte"), ("perfil", "Programa"), ("nivel", "Nivel"), ("grupo", "Grupo"), ("franja", "Franja")]
ORDEN_ESTADO = C.ORDEN_ESTADOS          # estados del cuadro Kuepa EduTech (nov-2026), iguales en la vista interna
COLOR_ESTADO = ui.COLOR_RIESGO


def hoy() -> pd.Timestamp:
    return ui.fecha_corte()  # fecha de corte elegida en la banda (por defecto, hoy)


@st.cache_data(ttl=data.TTL, show_spinner="Cargando datos…")
def _todos(dia: pd.Timestamp, version: str, es_corte: bool = False) -> pd.DataFrame:
    df, _ = ui._preparado(dia, version, es_corte)
    df = df.copy()
    df["estado_atenea"] = df.apply(estado, axis=1)
    return df


def todos() -> pd.DataFrame:
    """Toda la base preparada (sin filtros), con el estado de la vista Atenea. En caché: el banner de filtros y
    cada página la piden en cada clic, y ya no se recalcula."""
    from tcf10 import metrics
    try:
        dia = hoy()
        return _todos(dia, getattr(metrics, "VERSION", ""), dia < ui.hoy_real())
    except data.ErrorConfiguracion as e:
        st.error(str(e), icon=":material/error:")
        st.stop()


def estado(f: pd.Series) -> str:
    """Mismo estado que la vista interna: 5 estados de formación (grupo en curso) o estado final."""
    return f["riesgo"]


def filtros_banda(df: pd.DataFrame) -> None:
    """Filtros globales en la banda superior (valen para todas las páginas)."""
    cols = st.columns(len(FILTROS) + 1)
    ui.selector_corte(cols[-1])
    base = df
    for c, (col, etiqueta) in zip(cols, FILTROS):
        opciones = sorted(base[col].dropna().astype(str).unique(),
                          key=C.orden_franja if col == "franja" else
                          (lambda n: ((["Básico", "Intermedio", "Avanzado"] + [n]).index(n), n)) if col == "nivel" else None)
        sel = c.multiselect(etiqueta, opciones, key=f"at_{col}", placeholder="Todos")
        if sel:
            base = base[base[col].astype(str).isin(sel)]
    ui.filtros_caracterizacion(df, "at")


def filtrado(df: pd.DataFrame) -> pd.DataFrame:
    for col in C.CARACTERIZACION:
        sel = st.session_state.get(f"at_{col}") or []
        if sel and col in df:
            df = df[df[col].astype(str).isin(sel)]
    for col, _ in FILTROS:
        sel = st.session_state.get(f"at_{col}") or []
        if sel:
            df = df[df[col].astype(str).isin(sel)]
    return df


def nota_filtros() -> None:
    """Los filtros ya se ven en la banda: aquí no se repiten."""
    return None


def asistencia_personas(df: pd.DataFrame) -> pd.Series:
    reg = pd.to_numeric(df.get("sesiones_registradas"), errors="coerce")
    return pd.to_numeric(df.get("sesiones_asistidas"), errors="coerce") / reg.where(reg > 0)


def agregados_asistencia(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ids = tuple(sorted(int(x) for x in df["id_sis"].dropna().unique() if int(x) > 0))
    corte = hoy()
    asis, prog = data.agregados(ids, corte if corte < ui.hoy_real() else None)
    grupos = set(df["grupo"])
    asis = asis[asis["grupo"].isin(grupos)].copy()
    prog = prog[prog["grupo"].isin(grupos)].copy()
    # lo de las últimas 24 h todavía puede estar por registrar por el docente
    limite = (min(pd.Timestamp(datetime.now(ui.TZ).replace(tzinfo=None)), corte + pd.Timedelta(days=1))
              - pd.Timedelta(hours=C.REGISTRO_GRACIA_HORAS)).normalize()
    asis.loc[pd.to_datetime(asis["fecha"]) >= limite, "sin_registro"] = 0
    return asis, prog


def con_identidad(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega nombre_completo, tipo_documento y documento (solo detrás de inicio de sesión)."""
    ident = data.identidades()
    df = df.drop(columns=[c for c in ("nombre_completo", "tipo_documento", "documento") if c in df])
    if "huella" in df and "huella" in ident:
        df = df.merge(ident.drop(columns=[c for c in ("id_sis",) if c in ident]), on="huella", how="left")
    else:  # demo
        df = df.merge(ident, on="id_sis", how="left")
    for c in ("nombre_completo", "documento", "tipo_documento"):
        if c not in df:
            df[c] = None
    return df


GRUPOS_ESTADO = [("En curso", C.EN_CURSO), (C.APROBADO, [C.APROBADO]), (C.NO_APROBADO, [C.NO_APROBADO]),
                 (C.ABANDONO, [C.ABANDONO]), (C.POR_INICIAR, [C.POR_INICIAR])]
MIN_CELDA_SENSIBLE = 5  # conteos de 1 a 4 en datos sensibles se muestran como «< 5» (evita identificar personas)


def seccion_caracterizacion(df: pd.DataFrame) -> None:
    """Formalizados por sexo, estrato, nivel educativo o discapacidad, cruzados con el estado de formación."""
    import plotly.express as px
    form = df[df["enrolado"]].copy()
    dims = [c for c in C.CARACTERIZACION if c in form]
    if form.empty:
        st.info("No hay formalizados para este filtro.")
        return
    vacias = [c for c in dims if form[c].astype(str).eq(C.SIN_INFO).all()]
    if not dims or len(vacias) == len(dims):
        from tcf10 import base_atenea
        diag = getattr(base_atenea, "DIAGNOSTICO_CARACT", {})  # módulo viejo en memoria: sin diagnóstico
        detalle = (" · ".join(f"{C.CARACTERIZACION[k]}: {v or 'no encontrada'}" for k, v in diag.items())
                   if diag else "la base todavía no se ha releído con esta versión")
        st.warning("La base cargada no trae datos de caracterización. Pulsa **Actualizar** en la banda para releer "
                   f"la base de Formalización. Columnas detectadas → {detalle}.", icon=":material/info:")
        return
    dim = st.pills("Ver por", dims, format_func=C.CARACTERIZACION.get, default=dims[0], key="at_caract_dim") or dims[0]
    sensible = dim in C.CARACT_SENSIBLES
    if dim == "tipo_discapacidad":
        form = form[form["discapacidad"].eq("Sí")]
    form["_asis"] = asistencia_personas(form)
    orden = ui.opciones_caract(form[dim])
    g = form.groupby(dim)
    t = pd.DataFrame({"participantes": g.size(), "horas": g["horas_validas"].mean(), "asis": g["_asis"].mean()})
    for nombre, estados in GRUPOS_ESTADO:
        t[nombre] = g["estado_atenea"].apply(lambda s, e=estados: int(s.isin(e).sum()))
    t = t.reindex(orden).fillna(0)
    total = max(1, int(t["participantes"].sum()))

    def n(v):
        v = int(v)
        return f"< {MIN_CELDA_SENSIBLE}" if sensible and 0 < v < MIN_CELDA_SENSIBLE else ui.num(v)

    tabla = pd.DataFrame({C.CARACTERIZACION[dim]: t.index,
                          "Participantes": t["participantes"].map(n),
                          "%": [ui.pct(v / total, 1) for v in t["participantes"]]})
    for nombre, _ in GRUPOS_ESTADO:
        tabla[nombre] = t[nombre].map(n)
    tabla["Horas completadas promedio"] = t["horas"].map(lambda h: ui.num(h, 1))
    tabla["Asistencia promedio"] = t["asis"].map(lambda a: ui.pct(a, 1))
    if not sensible:
        dist = (form.groupby([dim, "estado_atenea"]).size().rename("personas").reset_index())
        fig = px.bar(dist, y=dim, x="personas", color="estado_atenea", orientation="h",
                     category_orders={"estado_atenea": ORDEN_ESTADO, dim: orden}, color_discrete_map=COLOR_ESTADO,
                     labels={dim: "", "personas": "Participantes", "estado_atenea": "Estado"})
        fig.update_layout(barmode="stack", separators=",.", legend=dict(orientation="h", y=1.15, title=None),
                          yaxis=dict(autorange="reversed"))
        ui.grafica_atenea(fig, max(260, 70 + 34 * len(orden)))
    st.dataframe(tabla, hide_index=True, width="stretch")
    nota = "Formalizados del filtro, según la base de Formalización."
    if sensible:
        nota += (f" Discapacidad es un dato sensible: solo conteos agregados y, si un grupo tiene menos de "
                 f"{MIN_CELDA_SENSIBLE} personas, se muestra «< {MIN_CELDA_SENSIBLE}».")
    st.caption(nota)
