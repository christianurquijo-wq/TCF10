"""Tablero de Looker Studio embebido (interactivo: filtros y controles del propio informe)."""
import streamlit as st
import streamlit.components.v1 as components

from vista_atenea import estilo

# El enlace venía como «datastudio.google.com:/embed/…» (con «:» de más): se usa el dominio vigente de Looker Studio.
URL_DEFECTO = ("https://lookerstudio.google.com/embed/reporting/1c03f250-bb57-40b2-84c2-177d8d99398c/"
               "page/p_aek28e0d9d")

estilo.pagina("Tablero Looker Studio", "Informe interactivo: usa los filtros y controles del propio tablero")
try:
    url = str(st.secrets.get("atenea", {}).get("looker_url", URL_DEFECTO))
except Exception:  # noqa: BLE001
    url = URL_DEFECTO
# Contenido de terceros bajo demanda (nov-2026): el iframe de Google no se carga hasta que la persona lo pide, para
# que Google no reciba datos de navegación ni ponga cookies sin una acción del usuario.
if not st.session_state.get("at_looker_ok"):
    with st.container(border=True):
        st.markdown("**Este tablero lo sirve Looker Studio (Google).** Al cargarlo, tu navegador se conecta a Google, "
                    "que puede usar sus propias cookies y registrar tu visita según su política de privacidad. "
                    "Puede pedirte iniciar sesión con tu cuenta de Google.")
        c1, c2 = st.columns(2)
        if c1.button("Cargar tablero", icon=":material/insert_chart:", type="primary", width="stretch"):
            st.session_state["at_looker_ok"] = True
            st.rerun()
        c2.link_button("Abrir en Looker Studio (pestaña nueva)", url.replace("/embed/", "/"), width="stretch",
                       icon=":material/open_in_new:")
        st.caption("Más información en «Privacidad y términos» → Cookies y terceros.")
    st.stop()
alto = st.select_slider("Alto del tablero", options=[500, 650, 800, 1000, 1200], value=800, key="at_looker_alto",
                        label_visibility="collapsed", format_func=lambda v: f"Alto: {v} px")
if hasattr(st, "iframe"):  # Streamlit reciente
    try:
        st.iframe(url, height=alto, alt="Tablero interactivo de Looker Studio de Talento Capital Formación 10")
    except TypeError:  # versiones sin «alt»
        st.iframe(url, height=alto)
else:
    components.html(
        f"""<iframe src="{url}" title="Tablero de Looker Studio TCF10" style="border:0; width:100%; height:{alto - 10}px; border-radius:14px;"
            allowfullscreen sandbox="allow-storage-access-by-user-activation allow-scripts allow-same-origin
            allow-popups allow-popups-to-escape-sandbox"></iframe>""", height=alto)
st.caption(f"[Abrir el tablero en una pestaña nueva]({url.replace('/embed/', '/')})")
