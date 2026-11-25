"""Listado de participantes con nombre y documento (solo con sesión autorizada) y ficha individual."""
import pandas as pd
import streamlit as st

from tcf10 import config as C
from tcf10 import data
from tcf10 import ui
from vista_atenea import comun, estilo, seguridad

estilo.pagina("Participantes", "Estado de formación, asistencia y horas de cada participante")
df = comun.filtrado(comun.todos())
comun.nota_filtros()

if ui.sensible_activo():
    ui.aviso_sensible()
    st.stop()

ident = data.identidades()
df = df.drop(columns=[c for c in ("nombre_completo", "tipo_documento", "documento") if c in df])
if "huella" in df and "huella" in ident:
    df = df.merge(ident.drop(columns=[c for c in ("id_sis",) if c in ident]), on="huella", how="left")
else:  # demo
    df = df.merge(ident, on="id_sis", how="left")
for c in ("nombre_completo", "documento", "tipo_documento"):
    if c not in df:
        df[c] = None

b1, b2, b3 = estilo.fila(3, "buscar")
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

df = df.assign(asistencia=comun.asistencia_personas(df) * 100, pct_esperado=df["pct_esperado"] * 100,
               avance_meta=(df["horas_validas"] / C.HORAS_CULMINACION).clip(upper=1) * 100,
               avance_90=(df["horas_validas"] / C.HORAS_TOTALES).clip(upper=1) * 100,
               sesiones=lambda x: x["sesiones_asistidas"].fillna(0).astype(int).astype(str) + " de "
                                  + x["sesiones_registradas"].fillna(0).astype(int).astype(str))
for c in ("sexo", "estrato", "nivel_educativo"):
    if c not in df:
        df[c] = C.SIN_INFO
cols = ["nombre_completo", "tipo_documento", "documento", "sexo", "estrato", "nivel_educativo", "cohorte", "grupo",
        "franja", "nivel", "perfil", "estado_atenea", "pct_esperado", "sesiones", "asistencia", "horas_sinc_val", "horas_asinc_val", "horas_validas",
        "avance_meta", "avance_90", "ultima_actividad"]
vista = df.sort_values(["cohorte", "grupo", "nombre_completo"])[cols + ["id_sis"]].reset_index(drop=True)
st.caption(f"{ui.num(len(vista))} participantes · selecciona una fila para abrir su ficha integral (con teclado: "
           "pestaña «Ficha», buscador por nombre o documento)")
evento = st.dataframe(
    vista[cols], hide_index=True, width="stretch", height=460, on_select="rerun", selection_mode="single-row",
    key="at_tabla",
    column_config={
        "nombre_completo": "Nombre", "tipo_documento": "Tipo doc.", "documento": "Documento", "sexo": "Sexo",
        "estrato": "Estrato", "nivel_educativo": "Nivel educativo", "cohorte": "Cohorte",
        "grupo": "Grupo", "franja": "Franja", "nivel": "Nivel", "perfil": "Programa", "estado_atenea": "Estado",
        "sesiones": "Sesiones asistidas",
        "pct_esperado": st.column_config.NumberColumn("ICP", format="%.0f %%",
                                                      help="Índice de Cumplimiento del Plan: avance ÷ línea base del plan a hoy (define el estado de formación)"),
        "asistencia": st.column_config.NumberColumn("% asistencia", format="%.0f %%"),
        "horas_sinc_val": st.column_config.NumberColumn("Sincrónico (h)", format="%.1f"),
        "horas_asinc_val": st.column_config.NumberColumn("Asincrónico (h)", format="%.1f"),
        "horas_validas": st.column_config.NumberColumn("Horas completadas", format="%.1f"),
        "avance_meta": st.column_config.ProgressColumn("Avance a 63 h", format="%.0f %%", min_value=0, max_value=100),
        "avance_90": st.column_config.ProgressColumn("Avance del curso (90 h)", format="%.0f %%", min_value=0,
                                                     max_value=100),
        "ultima_actividad": st.column_config.DateColumn("Última actividad", format="DD/MM/YYYY"),
    })

exportar = vista[cols].rename(columns={
    "nombre_completo": "Nombre", "tipo_documento": "Tipo documento", "documento": "Documento", "sexo": "Sexo",
    "estrato": "Estrato", "nivel_educativo": "Nivel educativo", "cohorte": "Cohorte",
    "grupo": "Grupo", "franja": "Franja", "nivel": "Nivel", "perfil": "Programa", "estado_atenea": "Estado",
    "pct_esperado": "ICP (%)", "sesiones": "Sesiones asistidas", "asistencia": "% asistencia", "horas_sinc_val": "Horas sincrónico (asistencia)",
    "horas_asinc_val": "Horas asincrónico (contenidos)", "horas_validas": "Horas completadas", "avance_meta": "% avance a 63 h", "avance_90": "% avance del curso (90 h)",
    "ultima_actividad": "Última actividad"})
exportar = exportar.round({c: 1 for c in exportar.select_dtypes("number").columns})
seguridad.boton_descarga("Descargar Excel", exportar, "TCF10_participantes.xlsx", "Participantes",
                         titulo="TCF10 · Participantes", clave="at_dl_participantes")
st.write("")
seguridad.bloque_vistas_crudas()

# ------------------------------------------------------------------ ir a la ficha integral
filas = evento.selection.rows if evento and evento.selection else []
if filas:
    st.session_state["at_ficha_id"] = int(vista.iloc[filas[0]]["id_sis"])
    st.switch_page("vista_atenea/5_Ficha.py")
