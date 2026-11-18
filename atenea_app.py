"""
Talento Capital Formación 10 · vista para la Agencia Atenea (cliente).

    streamlit run atenea_app.py

App aparte del tablero interno (app.py): mismo repositorio y mismos cálculos, otro enlace, otros secretos y
otro diseño (navegación superior, banda institucional con filtros, sin barra lateral).
Exige inicio de sesión con Google: correos @agenciaatenea.gov.co y @kuepa.com (ajustable en [atenea]).
Muestra nombre y documento de los participantes; no muestra montos ni clasificación de riesgo.
"""
import streamlit as st

from tcf10 import ui
from vista_atenea import comun, estilo

st.set_page_config(page_title="Talento Capital F10 · Atenea", page_icon="assets/atenea_icono.png", layout="wide",
                   initial_sidebar_state="collapsed")
st.logo("assets/atenea_horizontal.png", icon_image="assets/atenea_icono.png", size="large")
estilo.css()

correo = ui.acceso_restringido("atenea", ("agenciaatenea.gov.co", "kuepa.com"))

paginas = [
    st.Page("vista_atenea/1_Resumen.py", title="Resumen", icon=":material/dashboard:", default=True),
    st.Page("vista_atenea/2_Asistencia.py", title="Asistencia", icon=":material/event_available:"),
    st.Page("vista_atenea/3_Progreso.py", title="Progreso", icon=":material/trending_up:"),
    st.Page("vista_atenea/4_Participantes.py", title="Participantes", icon=":material/badge:"),
]
nav = st.navigation(paginas, position="top")

# Banda institucional con los filtros globales (aplican a todas las páginas)
with st.container(key="banda"):
    st.markdown(estilo.banda_html(f"{comun.hoy():%d/%m/%Y}"), unsafe_allow_html=True)
    comun.filtros_banda(comun.todos())
    pie = st.columns([4, 1, 1])
    if correo:
        pie[0].caption(f"Sesión: {correo}")
    if pie[1].button("Actualizar", icon=":material/refresh:", width="stretch"):
        ui.refrescar()
        st.rerun()
    if correo:
        pie[2].button("Salir", icon=":material/logout:", on_click=st.logout, width="stretch")

nav.run()
