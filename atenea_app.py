"""
Talento Capital Formación 10 · vista para la Agencia Atenea (cliente).

    streamlit run atenea_app.py

App aparte del tablero interno (app.py): mismo repositorio y mismos cálculos, otro enlace y otros secretos.
Exige inicio de sesión con Google: correos @agenciaatenea.gov.co y @kuepa.com (ajustable en [atenea]).
Muestra nombre y documento de los participantes; no muestra montos ni clasificación de riesgo.
"""
import streamlit as st

from tcf10 import ui
from vista_atenea import comun

st.set_page_config(page_title="Talento Capital F10 · Atenea", page_icon="assets/atenea_icono.png", layout="wide")
st.logo("assets/atenea_horizontal_blanco.png", icon_image="assets/atenea_icono_blanco.png", size="large")
st.markdown(ui.CSS, unsafe_allow_html=True)

correo = ui.acceso_restringido("atenea", ("agenciaatenea.gov.co", "kuepa.com"))

paginas = [
    st.Page("vista_atenea/1_Resumen.py", title="Resumen", icon=":material/dashboard:", default=True),
    st.Page("vista_atenea/2_Asistencia.py", title="Asistencia", icon=":material/event_available:"),
    st.Page("vista_atenea/3_Progreso.py", title="Progreso", icon=":material/trending_up:"),
    st.Page("vista_atenea/4_Participantes.py", title="Participantes", icon=":material/badge:"),
]
with st.sidebar:
    st.markdown("**Talento Capital · Formación 10**")
    st.caption("Seguimiento del operador Kuepa EduTech")
comun.filtros_laterales(comun.todos())
with st.sidebar:
    st.divider()
    if correo:
        st.caption(f"Sesión: {correo}")
        st.button("Cerrar sesión", on_click=st.logout, width="stretch")
    if st.button("Actualizar datos", icon=":material/refresh:", width="stretch"):
        ui.refrescar()
        st.rerun()

st.navigation(paginas).run()
