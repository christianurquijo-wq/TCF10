"""Privacidad, términos de uso, cookies y terceros, eliminación de datos y créditos. nov-2026."""
import streamlit as st

from vista_atenea import estilo, legal

estilo.pagina("Privacidad y términos", "Tratamiento de datos, condiciones de uso y servicios de terceros")
pestanas = st.tabs(["Aviso de privacidad", "Términos de uso", "Cookies y terceros", "Eliminación de datos",
                    "Créditos y licencias"])
for tab, seccion in zip(pestanas, ["privacidad", "terminos", "cookies", "eliminacion", "creditos"]):
    with tab:
        legal.mostrar(seccion)
