"""
Talento Capital Formación 10 (TCF10) · tablero de seguimiento contractual.
Contrato ATENEA-497-2026 · Kuepa EduTech.

    streamlit run app.py

Páginas en pages/; reglas de negocio en tcf10/metrics.py; parámetros del contrato en tcf10/config.py.
"""
import streamlit as st

from tcf10.ui import refrescar

st.set_page_config(page_title="TCF10 · Seguimiento", page_icon="assets/atenea_icono.png", layout="wide")
st.logo("assets/atenea_horizontal_blanco.png", icon_image="assets/atenea_icono_blanco.png", size="large")

paginas = {
    "Seguimiento": [
        st.Page("pages/1_Metas_y_pagos.py", title="Metas y pagos", icon=":material/payments:", default=True),
        st.Page("pages/2_Avance_y_riesgo.py", title="Avance y riesgo", icon=":material/monitoring:"),
        st.Page("pages/3_Cohortes_y_equipo.py", title="Cohortes y equipo", icon=":material/groups:"),
        st.Page("pages/4_Asistencia_y_plataforma.py", title="Asistencia y plataforma", icon=":material/event_available:"),
        st.Page("pages/5_Consulta_participante.py", title="Consulta por participante", icon=":material/person_search:"),
    ],
    "Referencia": [
        st.Page("pages/9_Metodologia.py", title="Cómo se calcula", icon=":material/menu_book:"),
    ],
}

with st.sidebar:
    st.markdown("**Talento Capital · Formación 10**")
    st.caption("Operador: Kuepa EduTech · Contrato ATENEA-497-2026")
    if st.button("Actualizar datos", icon=":material/refresh:", width="stretch"):
        refrescar()
        st.rerun()

st.navigation(paginas).run()
