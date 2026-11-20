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
alto = st.select_slider("Alto del tablero", options=[500, 650, 800, 1000, 1200], value=800, key="at_looker_alto",
                        label_visibility="collapsed", format_func=lambda v: f"Alto: {v} px")
if hasattr(st, "iframe"):  # Streamlit reciente
    st.iframe(url, height=alto)
else:
    components.html(
        f"""<iframe src="{url}" style="border:0; width:100%; height:{alto - 10}px; border-radius:14px;"
            allowfullscreen sandbox="allow-storage-access-by-user-activation allow-scripts allow-same-origin
            allow-popups allow-popups-to-escape-sandbox"></iframe>""", height=alto)
st.caption(f"[Abrir el tablero en una pestaña nueva]({url.replace('/embed/', '/')})")
