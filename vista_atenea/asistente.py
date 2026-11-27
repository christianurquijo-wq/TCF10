"""
Asistente de datos de la vista interna (nov-2026): botón flotante «Asistente de datos» → ventana con
  * Consultas frecuentes: conversación guiada (eliges la consulta, ajustas el dato que pide y, si quieres, más filtros).
  * Constructor: eliges qué quieres (lista, faltas, asistencia por grupo, resumen o distribución) y combinas filtros.
Cada respuesta trae la cifra, una vista previa y el CSV. Las listas llevan documento, nombre, teléfono y correo
(de la base de Formalización) y cada descarga queda en el registro de seguridad (quién, cuándo, qué filtros).
La lógica (filtros, tablas, CSV) está en tcf10/consultas.py; aquí solo la interfaz.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import streamlit as st

from tcf10 import config as C
from tcf10 import consultas as Q
from tcf10 import data, metrics, ui
from vista_atenea import comun, seguridad

VISTA_PREVIA = 300
CSS = """<style>
.st-key-asistente_fab { position: fixed; right: 24px; bottom: 24px; z-index: 999990; width: auto !important; }
.st-key-asistente_fab button { border-radius: 999px; padding: .65rem 1.25rem; font-weight: 600;
                               box-shadow: 0 8px 22px rgba(0,0,0,.28); }
@media (max-width: 640px) { .st-key-asistente_fab { right: 12px; bottom: 12px; } }
</style>"""


def boton_flotante() -> None:
    """Se llama en cada página de la vista interna (atenea_app.py)."""
    st.markdown(CSS, unsafe_allow_html=True)
    if st.button("Asistente de datos", icon=":material/forum:", key="asistente_fab", type="primary",
                 help="Consultas puntuales con cifra y CSV"):
        dialogo()


# ------------------------------------------------------------------ datos
def _corte() -> pd.Timestamp:
    hoy = ui.hoy_real()
    elegido = st.session_state.get("asis_corte")
    return min(pd.Timestamp(elegido).normalize(), hoy) if elegido else ui.fecha_corte()


def _base(corte: pd.Timestamp) -> pd.DataFrame:
    df, _ = ui._preparado(corte, getattr(metrics, "VERSION", ""), corte < ui.hoy_real())
    return Q.preparar_base(df)


@st.cache_data(ttl=data.TTL, show_spinner="Cargando contactos…")
def _contactos() -> tuple[pd.DataFrame, str]:
    c = data.contactos()
    return c, c.attrs.get("origen", "")


@st.cache_data(ttl=data.TTL, show_spinner="Cargando asistencia por sesión…")
def _detalle_asistencia(corte: pd.Timestamp | None) -> pd.DataFrame:
    return data.asistencia_detalle(corte)


def _con_contacto(d: pd.DataFrame) -> pd.DataFrame:
    """Nombre, documento, teléfono y correo solo para las filas del resultado."""
    d = comun.con_identidad(d.reset_index(drop=True))
    try:
        c, origen = _contactos()
    except Exception as e:  # noqa: BLE001 -- sin contactos la lista sigue sirviendo
        st.warning(f"No se pudieron leer teléfono y correo ({type(e).__name__}). La lista sale sin contacto.",
                   icon=":material/warning:")
        d["telefono"], d["correo"] = None, None
        return d
    llave = "huella" if "huella" in d and "huella" in c else "id_sis"
    d = d.drop(columns=[x for x in ("telefono", "correo") if x in d])
    d = d.merge(c[[llave, "telefono", "correo"]].drop_duplicates(llave), on=llave, how="left")
    d.attrs["origen_contacto"] = origen
    return d


# ------------------------------------------------------------------ ventana
@st.dialog("Asistente de datos · TCF-10", width="large")
def dialogo() -> None:
    hoy = ui.hoy_real().date()
    if "asis_corte" not in st.session_state:
        st.session_state["asis_corte"] = min(ui.fecha_corte().date(), hoy)
    c1, c2 = st.columns([1.3, 2], vertical_alignment="bottom")
    c1.date_input("Fecha de corte", key="asis_corte", min_value=dt.date(2026, 10, 1), max_value=hoy,
                  format="DD/MM/YYYY", help="Las cifras como estaban ese día (incluido). Por defecto, la de la banda.")
    modo = c2.segmented_control("Modo", ["Consultas frecuentes", "Constructor"], key="asis_modo",
                                default="Consultas frecuentes", label_visibility="collapsed")
    corte = _corte()
    try:
        df = _base(corte)
    except data.ErrorConfiguracion as e:
        st.error(str(e), icon=":material/error:")
        return
    if modo == "Constructor":
        _constructor(df, corte)
    else:
        _conversacion(df, corte)


# ------------------------------------------------------------------ consultas frecuentes (conversación guiada)
def _elegir(clave_widget: str) -> None:
    elegido = st.session_state.get(clave_widget)
    for g in {a.grupo for a in Q.ATAJOS}:
        k = f"asis_pill_{g}"
        if k != clave_widget:
            st.session_state[k] = None
    st.session_state["asis_atajo"] = elegido


def _conversacion(df: pd.DataFrame, corte: pd.Timestamp) -> None:
    titulos = {a.titulo: a.clave for a in Q.ATAJOS}
    with st.chat_message("assistant", avatar=":material/smart_toy:"):
        st.markdown("Hola. ¿Qué necesitas? Elige una consulta: te digo la cifra y te dejo el CSV. Después puedes "
                    "acotarla con más filtros (cohorte, grupo, franja, docente, caracterización…).")
        for grupo in dict.fromkeys(a.grupo for a in Q.ATAJOS):
            k = f"asis_pill_{grupo}"
            st.pills(grupo, [a.titulo for a in Q.ATAJOS if a.grupo == grupo], key=k, on_change=_elegir, args=(k,))
    clave = titulos.get(st.session_state.get("asis_atajo") or "")
    if not clave:
        return
    a = Q.POR_CLAVE[clave]
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(a.pregunta)
    with st.chat_message("assistant", avatar=":material/smart_toy:"):
        st.markdown(f"**{a.titulo}.** {a.definicion}")
        extra = _parametro(a, df, corte, f"asis_p_{clave}")
        with st.expander("Más filtros", icon=":material/filter_alt:"):
            mas = _panel_filtros(df, f"asis_f_{clave}", universo_fijo=a.filtros.universo)
        f = _combinar(a.filtros, mas, extra.get("filtros"))
        _resultado(a.tipo, df, f, corte, a.columnas, a.orden, a.asc, extra, a.clave)


def _parametro(a: Q.Atajo, df: pd.DataFrame, corte: pd.Timestamp, pfx: str) -> dict:
    """El dato que pide cada atajo (fecha, estados, rango…)."""
    p = a.parametro
    if p == "fecha_sin_actividad":
        dia = st.date_input("Sin actividad desde", value=(corte - pd.Timedelta(days=7)).date(), key=f"{pfx}_dia",
                            format="DD/MM/YYYY", max_value=corte.date())
        return {"filtros": Q.Filtros(fecha={"ultima_actividad": ("antes", dia)})}
    if p == "estados":
        sel = st.multiselect("Estados", C.ORDEN_ESTADOS, default=[C.RIESGO_ALTO, C.INACTIVO], key=f"{pfx}_est")
        return {"filtros": Q.Filtros(cat={"riesgo": sel or C.ORDEN_ESTADOS})}
    if p == "feedbacks":
        sel = st.pills("Pendientes", ["1 pendiente", "2 pendientes", "3 o más pendientes"], selection_mode="multi",
                       default=["2 pendientes", "3 o más pendientes"], key=f"{pfx}_fb")
        return {"filtros": Q.Filtros(cat={"estado_feedback": sel or ["1 pendiente", "2 pendientes",
                                                                     "3 o más pendientes"]})}
    if p == "rango_fechas":
        return _rango_fechas(corte, pfx, faltas=a.tipo == "faltas")
    if p == "por":
        return {"por": st.segmented_control("Agrupar por", list(Q.POR_RESUMEN), format_func=Q.ETIQ_RESUMEN.get,
                                            default="grupo", key=f"{pfx}_por") or "grupo"}
    if p == "dim":
        c1, c2 = st.columns(2)
        dims = [d for d in Q.DIM_DISTRIBUCION if d in df]
        dim = c1.selectbox("Filas", dims, format_func=lambda x: Q.CAMPOS.get(x, Q.ETIQUETA.get(x, x)),
                           key=f"{pfx}_dim")
        por = c2.segmented_control("Columnas", list(Q.COL_DISTRIBUCION), format_func=Q.COL_DISTRIBUCION.get,
                                   default="riesgo", key=f"{pfx}_col") or "riesgo"
        return {"dim": dim, "por_col": por}
    return {}


def _rango_fechas(corte: pd.Timestamp, pfx: str, faltas: bool) -> dict:
    c1, c2 = st.columns([2, 1.4], vertical_alignment="bottom")
    r = c1.date_input("Sesiones entre", value=((corte - pd.Timedelta(days=6)).date(), corte.date()),
                      max_value=corte.date(), format="DD/MM/YYYY", key=f"{pfx}_rango")
    r = list(r) if isinstance(r, (list, tuple)) else [r]
    desde, hasta = (r[0], r[-1]) if r else (corte.date(), corte.date())  # mientras eligen, llega una sola fecha
    sin_reg = c2.toggle("Incluir «sin registro»", key=f"{pfx}_sinreg",
                        help="Sesiones pasadas en las que el docente no marcó asistencia.") if faltas else False
    return {"desde": desde, "hasta": hasta, "sin_registro": sin_reg}


# ------------------------------------------------------------------ constructor
TIPOS = {"lista": "Lista de personas (cifra + CSV)", "faltas": "Quién faltó a clase",
         "asis_grupos": "Asistencia por grupo y fecha", "resumen": "Tabla resumen por…",
         "distribucion": "Distribución (conteo cruzado)"}


def _constructor(df: pd.DataFrame, corte: pd.Timestamp) -> None:
    tipo = st.selectbox("¿Qué necesitas?", list(TIPOS), format_func=TIPOS.get, key="asis_c_tipo")
    extra: dict = {}
    columnas = Q.COLUMNAS_BASE
    if tipo == "lista":
        columnas = st.multiselect("Columnas del CSV", Q.COLUMNAS_LISTA, default=Q.COLUMNAS_BASE,
                                  format_func=Q.CAMPOS.get, key="asis_c_cols")
    elif tipo in ("faltas", "asis_grupos"):
        extra = _rango_fechas(corte, "asis_c", faltas=tipo == "faltas")
    elif tipo == "resumen":
        extra = {"por": st.segmented_control("Agrupar por", list(Q.POR_RESUMEN), format_func=Q.ETIQ_RESUMEN.get,
                                             default="grupo", key="asis_c_por") or "grupo"}
    elif tipo == "distribucion":
        c1, c2 = st.columns(2)
        dims = [d for d in Q.DIM_DISTRIBUCION if d in df]
        extra = {"dim": c1.selectbox("Filas", dims, format_func=lambda x: Q.CAMPOS.get(x, Q.ETIQUETA.get(x, x)),
                                     key="asis_c_dim"),
                 "por_col": c2.segmented_control("Columnas", list(Q.COL_DISTRIBUCION),
                                                 format_func=Q.COL_DISTRIBUCION.get, default="riesgo",
                                                 key="asis_c_col") or "riesgo"}
    st.markdown("**Filtros**")
    f = _panel_filtros(df, "asis_c")
    _resultado(tipo, df, f, corte, columnas or Q.COLUMNAS_BASE, ["grupo"], True, extra, "constructor")


# ------------------------------------------------------------------ panel de filtros (compartido)
def _opciones(df: pd.DataFrame, col: str) -> list[str]:
    v = df[col].dropna().astype(str)
    v = v[v.ne("")].unique().tolist()
    if col == "riesgo":
        return [e for e in C.ORDEN_ESTADOS if e in v] + sorted(set(v) - set(C.ORDEN_ESTADOS))
    if col == "tipo_ruta":
        return [e for e in Q.ORDEN_RUTA if e in v]
    if col == "franja":
        return sorted(v, key=C.orden_franja)
    if col == "nivel":
        return sorted(v, key=lambda n: (["Básico", "Intermedio", "Avanzado", n].index(n), n))
    return sorted(v)


def _panel_filtros(df: pd.DataFrame, pfx: str, universo_fijo: str | None = None) -> Q.Filtros:
    f = Q.Filtros(universo_fijo or "en_curso")
    if universo_fijo is None:
        f.universo = st.selectbox("¿A quiénes incluyo?", list(Q.UNIVERSOS), format_func=Q.UNIVERSOS.get,
                                  key=f"{pfx}_univ")
    cats = [(c, e) for c, e in Q.FILTROS_CAT if c in df]
    cols = st.columns(3)
    for i, (col, etiqueta) in enumerate(cats):
        ayuda = "Dato sensible: solo permite cifras agregadas (resumen o distribución), no listas." \
            if col in Q.SENSIBLES else None
        sel = cols[i % 3].multiselect(etiqueta, _opciones(df, col), key=f"{pfx}_{col}", placeholder="Todos",
                                      help=ayuda)
        if sel:
            f.cat[col] = sel
    marcas = st.pills("Solo los que tengan", [k for k, _ in Q.FILTROS_BOOL], selection_mode="multi",
                      format_func=dict(Q.FILTROS_BOOL).get, key=f"{pfx}_bool")
    for k in marcas or []:
        f.si[k] = True
    with st.expander("Rangos y fechas", icon=":material/tune:"):
        cols = st.columns(2)
        for i, (col, etiqueta, lo, hi) in enumerate(Q.FILTROS_RANGO):
            if col not in df:
                continue
            if col in ("sesiones_asistidas", "dias_sin_actividad", "dias_sin_plataforma"):
                maximo = pd.to_numeric(df[col], errors="coerce").max()
                hi = float(max(hi if pd.isna(maximo) else maximo, 1))
            r = cols[i % 2].slider(etiqueta, lo, hi, (lo, hi), step=1.0 if hi > 20 else .5, key=f"{pfx}_r_{col}")
            if r != (lo, hi):
                f.rango[col] = r
        cols = st.columns(2)
        for i, (col, etiqueta) in enumerate(Q.FILTROS_FECHA):
            with cols[i]:
                modo = st.selectbox(etiqueta, ["Sin filtro", "Sin registro desde", "Con registro desde"],
                                    key=f"{pfx}_fm_{col}")
                if modo != "Sin filtro":
                    dia = st.date_input("Fecha", key=f"{pfx}_fd_{col}", format="DD/MM/YYYY",
                                        value=(ui.hoy_real() - pd.Timedelta(days=7)).date(),
                                        label_visibility="collapsed")
                    f.fecha[col] = ("antes" if modo.startswith("Sin") else "desde", dia)
    return f


def _combinar(base: Q.Filtros, *otros: Q.Filtros | None) -> Q.Filtros:
    f = Q.Filtros(base.universo, dict(base.cat), dict(base.si), dict(base.rango), dict(base.fecha))
    for o in otros:
        if o is None:
            continue
        f.cat.update({k: v for k, v in o.cat.items() if v})
        f.si.update(o.si)
        f.rango.update(o.rango)
        f.fecha.update(o.fecha)
    return f


# ------------------------------------------------------------------ resultado (cifra, vista previa y CSV)
def _resultado(tipo: str, df: pd.DataFrame, f: Q.Filtros, corte: pd.Timestamp, columnas: list[str],
               orden: list[str], asc, extra: dict, nombre: str) -> None:
    d = Q.aplicar(df, f)
    base_n = len(Q.universo(df, f.universo))
    filtros_txt = Q.describir(f)
    personales = tipo in ("lista", "faltas")
    if personales and f.sensible():
        st.warning("Discapacidad es un dato sensible: con ese filtro solo se permiten cifras agregadas. Usa "
                   "«Tabla resumen» o «Distribución» en el Constructor.", icon=":material/lock:")
        return
    st.divider()
    if tipo == "lista":
        pct = ui.pct(len(d) / base_n, 1) if base_n else "—"
        st.markdown(f"Encontré **{ui.num(len(d))} personas** ({pct} de {ui.num(base_n)} · "
                    f"{Q.UNIVERSOS[f.universo].split(' (')[0].lower()}).")
        if d.empty:
            _sin_resultados()
            return
        e = _con_contacto(d)
        t = Q.lista(e, columnas, orden, asc)
        _salida(Q.para_csv(t), nombre, corte, filtros_txt, e.attrs.get("origen_contacto"))
    elif tipo == "faltas":
        desde, hasta = extra["desde"], extra["hasta"]
        det = _detalle_asistencia(corte if corte < ui.hoy_real() else None)
        r = Q.faltas(det, d, desde, hasta, incluir_sin_registro=extra.get("sin_registro", False))
        st.markdown(f"Encontré **{ui.num(len(r))} inasistencias** de **{ui.num(r['id_sis'].nunique())} personas** "
                    f"entre el {desde:%d/%m/%Y} y el {hasta:%d/%m/%Y}.")
        if r.empty:
            _sin_resultados()
            return
        r = _con_contacto(r)
        origen = r.attrs.get("origen_contacto")
        cols = Q.CONTACTO + ["grupo", "franja", "docente", "sesion", "fecha", "estado_asistencia", "sesiones_asistidas",
                             "riesgo"]
        t = Q.lista(r, cols, ["grupo", "fecha", "sesion"])
        _salida(Q.para_csv(t), nombre, corte, f"{filtros_txt} · sesiones del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}",
                origen)
    elif tipo == "asis_grupos":
        desde, hasta = extra["desde"], extra["hasta"]
        ids = tuple(sorted(int(x) for x in d["id_sis"].dropna().unique() if int(x) > 0))
        asis, _ = data.agregados(ids, corte if corte < ui.hoy_real() else None)
        t = Q.asistencia_grupos(asis, set(d["grupo"].dropna()), desde, hasta)
        if t.empty:
            st.markdown(f"No hay sesiones entre el {desde:%d/%m/%Y} y el {hasta:%d/%m/%Y} para este filtro.")
            return
        reg = (t["Asistieron"] + t["No asistieron"]).sum()
        st.markdown(f"**{ui.num(len(t))} sesiones** de **{ui.num(t['Grupo'].nunique())} grupos** entre el "
                    f"{desde:%d/%m/%Y} y el {hasta:%d/%m/%Y} · asistencia de los registrados: "
                    f"**{ui.pct(t['Asistieron'].sum() / reg if reg else None, 1)}**.")
        _salida(t, nombre, corte, f"{filtros_txt} · {desde:%d/%m/%Y}–{hasta:%d/%m/%Y}")
    elif tipo == "resumen":
        por = extra.get("por", "grupo")
        if d.empty:
            _sin_resultados()
            return
        t = Q.resumen(d, por)
        if f.sensible():  # conteos pequeños ocultos con filtro sensible
            for c in ("Personas", "Formalizados activos", "En curso", "Aprobados", "Casos críticos"):
                t[c] = [f"< {Q.MIN_CELDA_SENSIBLE}" if 0 < int(v) < Q.MIN_CELDA_SENSIBLE else int(v) for v in t[c]]
        st.markdown(f"Resumen por **{Q.ETIQ_RESUMEN[por].lower()}** de **{ui.num(len(d))} personas**.")
        _salida(t, f"{nombre}_{por}", corte, filtros_txt)
    elif tipo == "distribucion":
        dim, por = extra.get("dim"), extra.get("por_col", "riesgo")
        if d.empty or not dim:
            _sin_resultados()
            return
        t = Q.distribucion(d, dim, por, sensible=f.sensible())
        st.markdown(f"**{ui.num(len(d))} personas** por {Q.CAMPOS.get(dim, Q.ETIQUETA.get(dim, dim)).lower()} y "
                    f"{Q.COL_DISTRIBUCION[por].lower()}.")
        _salida(t, f"{nombre}_{dim}", corte, filtros_txt)
    st.caption(f"Corte: {corte:%d/%m/%Y} · Filtros: {filtros_txt}")


def _sin_resultados() -> None:
    st.info("No hay resultados con estos filtros. Prueba quitando alguno en «Más filtros».",
            icon=":material/filter_alt_off:")


def _salida(t: pd.DataFrame, nombre: str, corte: pd.Timestamp, detalle: str, origen_contacto: str | None = None
            ) -> None:
    previa = t.head(VISTA_PREVIA)
    st.dataframe(previa, hide_index=True, width="stretch", height=min(420, 38 + 35 * len(previa)))
    if len(t) > VISTA_PREVIA:
        st.caption(f"Vista previa de {VISTA_PREVIA} filas; el CSV trae las {ui.num(len(t))}.")
    archivo = f"TCF10_{nombre}_{corte:%Y%m%d}.csv"
    st.download_button(f"Descargar CSV ({ui.num(len(t))} filas)", Q.a_csv(t), archivo, "text/csv",
                       icon=":material/download:", type="primary", key=f"asis_dl_{nombre}",
                       on_click=seguridad.registrar,
                       args=("descarga", seguridad.usuario_actual(), st.session_state.get("seg_via", ""),
                             f"{archivo} · {len(t)} filas · {detalle}"[:480]))
    nota = "Información confidencial: la descarga queda registrada con tu usuario."
    if origen_contacto:
        nota += f" Contacto tomado de la base de Formalización ({origen_contacto})."
    st.caption(nota)
