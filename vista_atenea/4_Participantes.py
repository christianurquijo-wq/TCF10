"""Listado de participantes con nombre y documento (solo con sesión autorizada) y ficha individual."""
import io

import pandas as pd
import streamlit as st

from tcf10 import config as C
from tcf10 import data
from tcf10 import ui
from vista_atenea import comun, estilo

estilo.pagina("Participantes", "Estado de formación, asistencia y horas de cada participante")
df = comun.filtrado(comun.todos())
comun.nota_filtros()

ident = data.identidades()
df = df.drop(columns=[c for c in ("nombre_completo", "tipo_documento", "documento") if c in df])
if "huella" in df and "huella" in ident:
    df = df.merge(ident.drop(columns=[c for c in ("id_sis",) if c in ident]), on="huella", how="left")
else:  # demo
    df = df.merge(ident, on="id_sis", how="left")
for c in ("nombre_completo", "documento", "tipo_documento"):
    if c not in df:
        df[c] = None

b1, b2, b3 = st.columns([1.4, 1, 1])
nombre = b1.text_input("Nombre", placeholder="Escribe parte del nombre o apellido", key="at_nombre").strip()
cedula = b2.text_input("Documento", placeholder="Número sin puntos", key="at_doc").strip()
estados = b3.multiselect("Estado", comun.ORDEN_ESTADO, placeholder="Todos", key="at_estado")
if nombre:
    from tcf10.base_atenea import _plano
    buscar = _plano(nombre)
    df = df[df["nombre_completo"].fillna("").map(_plano).str.contains(buscar, regex=False)]
if cedula:
    digitos = "".join(ch for ch in cedula if ch.isdigit())
    df = df[df["documento"].fillna("").astype(str).str.contains(digitos, regex=False)] if digitos else df.iloc[0:0]
if estados:
    df = df[df["estado_atenea"].isin(estados)]

df = df.assign(asistencia=comun.asistencia_personas(df) * 100,
               avance_meta=(df["horas_validas"] / C.HORAS_CULMINACION).clip(upper=1) * 100,
               sesiones=lambda x: x["sesiones_asistidas"].fillna(0).astype(int).astype(str) + " de "
                                  + x["sesiones_registradas"].fillna(0).astype(int).astype(str))
cols = ["nombre_completo", "tipo_documento", "documento", "cohorte", "grupo", "franja", "nivel", "perfil",
        "estado_atenea", "sesiones", "asistencia", "horas_sinc_val", "horas_asinc_val", "horas_validas",
        "avance_meta", "ultima_actividad"]
vista = df.sort_values(["cohorte", "grupo", "nombre_completo"])[cols + ["id_sis"]].reset_index(drop=True)
st.caption(f"{ui.num(len(vista))} participantes · selecciona una fila para ver su ficha")
evento = st.dataframe(
    vista[cols], hide_index=True, width="stretch", height=460, on_select="rerun", selection_mode="single-row",
    key="at_tabla",
    column_config={
        "nombre_completo": "Nombre", "tipo_documento": "Tipo doc.", "documento": "Documento", "cohorte": "Cohorte",
        "grupo": "Grupo", "franja": "Franja", "nivel": "Nivel", "perfil": "Programa", "estado_atenea": "Estado",
        "sesiones": "Sesiones asistidas",
        "asistencia": st.column_config.NumberColumn("% asistencia", format="%.0f %%"),
        "horas_sinc_val": st.column_config.NumberColumn("Sincrónicas (h)", format="%.1f"),
        "horas_asinc_val": st.column_config.NumberColumn("Asincrónicas (h)", format="%.1f"),
        "horas_validas": st.column_config.NumberColumn("Horas válidas", format="%.1f"),
        "avance_meta": st.column_config.ProgressColumn("Avance a 63 h", format="%.0f %%", min_value=0, max_value=100),
        "ultima_actividad": st.column_config.DateColumn("Última actividad", format="DD/MM/YYYY"),
    })

buf = io.BytesIO()
exportar = vista[cols].rename(columns={
    "nombre_completo": "Nombre", "tipo_documento": "Tipo documento", "documento": "Documento", "cohorte": "Cohorte",
    "grupo": "Grupo", "franja": "Franja", "nivel": "Nivel", "perfil": "Programa", "estado_atenea": "Estado",
    "sesiones": "Sesiones asistidas", "asistencia": "% asistencia", "horas_sinc_val": "Horas sincrónicas",
    "horas_asinc_val": "Horas asincrónicas", "horas_validas": "Horas válidas", "avance_meta": "% avance a 63 h",
    "ultima_actividad": "Última actividad"})
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    exportar.round({c: 1 for c in exportar.select_dtypes("number").columns}).to_excel(
        xw, sheet_name="Participantes", index=False)
st.download_button("Descargar Excel", buf.getvalue(), "TCF10_participantes.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:")

# ------------------------------------------------------------------ ficha
filas = evento.selection.rows if evento and evento.selection else []
if len(vista) == 1:
    filas = [0]
if filas:
    f = vista.iloc[filas[0]]
    st.divider()
    st.subheader(f"Ficha · {f['nombre_completo'] or 'Participante'}")
    color = comun.COLOR_ESTADO.get(f["estado_atenea"], ui.GRIS)
    k = st.columns(4)
    with k[0]:
        estilo.kpi("Estado", f["estado_atenea"], f"{f['cohorte']} · {f['grupo']} · {f['franja']}", "noche")
    with k[1]:
        estilo.kpi("Asistencia", "–" if pd.isna(f["asistencia"]) else f"{f['asistencia']:.0f} %",
                   f"{f['sesiones']} sesiones registradas", "azul")
    with k[2]:
        estilo.kpi("Horas válidas", ui.num(f["horas_validas"], 1),
                   f"{ui.num(f['horas_sinc_val'], 1)} sincrónicas + {ui.num(f['horas_asinc_val'], 1)} asincrónicas · "
                   f"{ui.pct(min(1, f['horas_validas'] / C.HORAS_CULMINACION))} de 63 h", "profundo")
    with k[3]:
        estilo.kpi("Última actividad", ui.fecha_corta(f["ultima_actividad"]),
                   f"{f['tipo_documento'] or ''} {f['documento'] or ''}".strip() or "–", "azul")
    sesiones, cursos = data.detalle_persona(f["id_sis"])
    izq, der = st.columns([1.2, 1])
    with izq:
        st.markdown("**Asistencia sesión por sesión**")
        if sesiones.empty:
            st.caption("Sin sesiones registradas en la plataforma.")
        else:
            st.dataframe(sesiones, hide_index=True, width="stretch", height=300,
                         column_config={"Fecha": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                        "Sesión": st.column_config.NumberColumn(format="%d")})
    with der:
        st.markdown("**Avance por curso**")
        if cursos.empty:
            st.caption("Sin avance registrado en la plataforma.")
        else:
            cursos["Curso"] = cursos["Curso"].map(ui.curso_corto)
            st.dataframe(cursos, hide_index=True, width="stretch",
                         column_config={"Avance": st.column_config.ProgressColumn(format="percent", min_value=0,
                                                                                  max_value=1)})
