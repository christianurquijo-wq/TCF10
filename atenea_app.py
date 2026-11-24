"""
Talento Capital Formación 10 · app unificada (nov-2026).

    streamlit run atenea_app.py      (app.py hace lo mismo: se conserva para el enlace anterior)

Una sola app con dos vistas:
  * Vista Atenea (por defecto): navegación superior, banda institucional con filtros; nombre y documento de los
    participantes, sin montos ni riesgo. Ingreso con usuario/contraseña ([atenea.usuarios]) o Google.
  * Vista interna (Kuepa): metas y pagos, avance y riesgo, cohortes y equipo, asistencia y plataforma, grupos y
    casos críticos (con la tipificación por estudiante), consulta por participante y metodología.
    Solo la ven los correos de Google listados en [atenea] internos: para ellos aparece el botón «Vista interna».
"""
import streamlit as st

from tcf10 import ui
from vista_atenea import acceso, comun, estilo

st.set_page_config(page_title="Talento Capital F10", page_icon="assets/atenea_icono.png", layout="wide",
                   initial_sidebar_state="collapsed")
st.logo("assets/atenea_horizontal.png", icon_image="assets/atenea_icono.png", size="large")
estilo.css()

PAGINAS_ATENEA = [
    st.Page("vista_atenea/1_Resumen.py", title="Resumen", icon=":material/dashboard:", default=True, url_path="resumen"),
    st.Page("vista_atenea/2_Asistencia.py", title="Asistencia", icon=":material/event_available:", url_path="asistencia"),
    st.Page("vista_atenea/3_Progreso.py", title="Progreso", icon=":material/trending_up:", url_path="progreso"),
    st.Page("vista_atenea/4_Participantes.py", title="Participantes", icon=":material/badge:", url_path="participantes"),
    st.Page("vista_atenea/5_Ficha.py", title="Ficha", icon=":material/person_search:", url_path="ficha"),
    st.Page("vista_atenea/6_Looker.py", title="Tablero Looker", icon=":material/insert_chart:", url_path="looker"),
]
PAGINAS_INTERNAS = [
    st.Page("tablero/6_Grupos_criticos.py", title="Grupos y casos críticos", icon=":material/crisis_alert:",
            default=True, url_path="interno-criticos"),
    st.Page("tablero/1_Metas_y_pagos.py", title="Metas y pagos", icon=":material/payments:", url_path="interno-metas"),
    st.Page("tablero/2_Avance_y_riesgo.py", title="Avance y riesgo", icon=":material/monitoring:",
            url_path="interno-avance"),
    st.Page("tablero/3_Cohortes_y_equipo.py", title="Cohortes y equipo", icon=":material/groups:",
            url_path="interno-cohortes"),
    st.Page("tablero/4_Asistencia_y_plataforma.py", title="Asistencia y plataforma", icon=":material/event_available:",
            url_path="interno-asistencia"),
    st.Page("tablero/5_Consulta_participante.py", title="Consulta", icon=":material/person_search:",
            url_path="interno-consulta"),
    st.Page("tablero/9_Metodologia.py", title="Cómo se calcula", icon=":material/menu_book:",
            url_path="interno-metodologia"),
]

# Sin sesión: menú oculto y pantalla de ingreso (usuario/contraseña o Google)
sesion = acceso.sesion_actual()
interno_ok = acceso.es_interno(sesion)
st.session_state["interno_ok"] = interno_ok
st.session_state["interno_correo"] = (sesion or {}).get("nombre", "")
if not interno_ok:
    st.session_state["vista"] = "atenea"  # quien no está autorizado nunca queda en la vista interna
interna = st.session_state.get("vista") == "interna"

nav = st.navigation(PAGINAS_INTERNAS if interna else PAGINAS_ATENEA, position="top" if sesion else "hidden")
if not sesion:
    acceso.pantalla_ingreso()
if st.session_state.pop("ir_inicio", False):  # al cambiar de vista se abre su página inicial
    st.switch_page(PAGINAS_INTERNAS[0] if interna else PAGINAS_ATENEA[0])
acceso.aviso_modo(sesion)
correo = sesion.get("nombre", "")


def cambiar_vista(destino: str) -> None:
    st.session_state["vista"] = destino
    st.session_state["ir_inicio"] = True


if interna:
    # Banda de la vista interna: sin filtros globales (cada página interna trae los suyos)
    with st.container(key="banda"):
        st.markdown(estilo.banda_html(f"{comun.hoy():%d/%m/%Y}", interna=True), unsafe_allow_html=True)
        pie = st.columns([3, 1.2, 1, 1])
        pie[0].caption(f"Vista interna Kuepa · {correo}" if correo else "Vista interna Kuepa")
        pie[1].button("Vista Atenea", icon=":material/visibility:", on_click=cambiar_vista, args=("atenea",),
                      width="stretch", type="primary")
        if pie[2].button("Actualizar", icon=":material/refresh:", width="stretch"):
            ui.refrescar()
            st.rerun()
        if correo:
            pie[3].button("Salir", icon=":material/logout:", on_click=acceso.cerrar_sesion, args=(sesion,),
                          width="stretch")
else:
    # Banda institucional con los filtros globales (aplican a todas las páginas de la vista Atenea)
    with st.container(key="banda"):
        st.markdown(estilo.banda_html(f"{comun.hoy():%d/%m/%Y}"), unsafe_allow_html=True)
        comun.filtros_banda(comun.todos())
        pie = st.columns([3, 1.2, 1, 1]) if interno_ok else st.columns([4, 1, 1])
        if correo:
            pie[0].caption(f"Sesión: {correo}")
        i = 1
        if interno_ok:
            pie[1].button("Vista interna", icon=":material/admin_panel_settings:", on_click=cambiar_vista,
                          args=("interna",), width="stretch", type="primary")
            i = 2
        if pie[i].button("Actualizar", icon=":material/refresh:", width="stretch"):
            ui.refrescar()
            st.rerun()
        if correo:
            pie[i + 1].button("Salir", icon=":material/logout:", on_click=acceso.cerrar_sesion, args=(sesion,),
                              width="stretch")

nav.run()
