"""
Talento Capital Formación 10 · app unificada (nov-2026).

    streamlit run atenea_app.py      (app.py hace lo mismo: se conserva para el enlace anterior)

Una sola app con dos vistas:
  * Vista Atenea (por defecto): navegación superior, banda institucional con filtros; nombre y documento de los
    participantes, sin montos ni riesgo. Ingreso con usuario/contraseña ([atenea.usuarios]) o Google.
  * Vista interna (Kuepa): metas y pagos, avance y estado de formación, cohortes y equipo, asistencia y plataforma, grupos y
    casos críticos (con la tipificación por estudiante), consulta por participante y metodología, más el botón
    flotante «Asistente de datos» (vista_atenea/asistente.py) para consultas puntuales con cifra y CSV.
    Solo la ven los correos de Google listados en [atenea] internos: para ellos el sello «Operado por Kuepa» de la
    banda es un enlace a la vista interna (para el resto es solo el sello; no hay botón visible).
"""
import streamlit as st

from tcf10 import ui
from vista_atenea import acceso, asistente, comun, estilo, legal, seguridad

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
    # Oculta temporalmente (nov-2026) mientras se ajusta el Looker a las cifras de la app. Para mostrarla de nuevo,
    # quita el «#» de la línea siguiente.
    # st.Page("vista_atenea/6_Looker.py", title="Tablero Looker", icon=":material/insert_chart:", url_path="looker"),
    st.Page("vista_atenea/7_Como_se_calcula.py", title="Cómo se calcula", icon=":material/menu_book:",
            url_path="como-se-calcula"),
    st.Page("vista_atenea/8_Privacidad.py", title="Privacidad y términos", icon=":material/policy:",
            url_path="privacidad"),
]
PAGINAS_INTERNAS = [
    st.Page("tablero/6_Grupos_criticos.py", title="Grupos y casos críticos", icon=":material/crisis_alert:",
            default=True, url_path="interno-criticos"),
    st.Page("tablero/7_Feedbacks.py", title="Feedbacks", icon=":material/rate_review:", url_path="interno-feedbacks"),
    st.Page("tablero/1_Metas_y_pagos.py", title="Metas y pagos", icon=":material/payments:", url_path="interno-metas"),
    st.Page("tablero/2_Avance_y_riesgo.py", title="Avance y estado", icon=":material/monitoring:",
            url_path="interno-avance"),
    st.Page("tablero/3_Cohortes_y_equipo.py", title="Cohortes y equipo", icon=":material/groups:",
            url_path="interno-cohortes"),
    st.Page("tablero/4_Asistencia_y_plataforma.py", title="Asistencia y plataforma", icon=":material/event_available:",
            url_path="interno-asistencia"),
    st.Page("tablero/5_Consulta_participante.py", title="Consulta", icon=":material/person_search:",
            url_path="interno-consulta"),
    st.Page("tablero/10_Bases_formacion.py", title="Bases de formación", icon=":material/sync:",
            url_path="interno-bases-formacion"),
    st.Page("tablero/9_Metodologia.py", title="Cómo se calcula", icon=":material/menu_book:",
            url_path="interno-metodologia"),
]

# Sin sesión: menú oculto y pantalla de ingreso (usuario/contraseña o Google)
sesion = acceso.sesion_actual()
if sesion:
    acceso.identificar(sesion)
    # Cierre por inactividad (se evalúa en la primera interacción después de 30 min sin actividad)
    if sesion.get("via") in ("usuario", "google") and seguridad.expirada():
        acceso.cerrar_sesion(sesion, motivo="cierre_inactividad")
        st.rerun()
    seguridad.tocar()
interno_ok = acceso.es_interno(sesion)
st.session_state["interno_ok"] = interno_ok
st.session_state["interno_correo"] = (sesion or {}).get("nombre", "")
# El sello «Operado por Kuepa» enlaza a ?vista=interna (solo se dibuja como enlace para los autorizados; si otra
# persona escribe el parámetro a mano, se ignora).
_pedida = st.query_params.get("vista")
if _pedida in ("interna", "atenea"):
    if _pedida == "atenea" or interno_ok:
        st.session_state["vista"] = _pedida
        st.session_state["ir_inicio"] = True
    del st.query_params["vista"]
if not interno_ok:
    st.session_state["vista"] = "atenea"  # quien no está autorizado nunca queda en la vista interna
interna = st.session_state.get("vista") == "interna"

nav = st.navigation(PAGINAS_INTERNAS if interna else PAGINAS_ATENEA, position="top" if sesion else "hidden")
if not sesion:
    acceso.pantalla_ingreso()
if sesion:
    acceso.exigir_aceptacion(sesion)  # Google: aceptar términos vigentes antes de ver datos
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
        st.markdown(estilo.banda_html(f"{comun.hoy():%d/%m/%Y}", interna=True, enlace="?vista=atenea"),
                    unsafe_allow_html=True)
        pie = st.columns([1.3, 1.7, 1.2, 1, 1], vertical_alignment="bottom")
        ui.selector_corte(pie[0])
        pie[1].caption(f"Vista interna Kuepa · {correo}" if correo else "Vista interna Kuepa")
        pie[2].button("Vista Atenea", icon=":material/visibility:", on_click=cambiar_vista, args=("atenea",),
                      width="stretch", type="primary")
        if pie[3].button("Actualizar", icon=":material/refresh:", width="stretch"):
            ui.refrescar()
            st.rerun()
        if correo:
            pie[4].button("Salir", icon=":material/logout:", on_click=acceso.cerrar_sesion, args=(sesion,),
                          width="stretch")
    # Botón flotante «Asistente de datos» (consultas puntuales con cifra y CSV): en todas las páginas internas.
    # Va antes de nav.run() porque algunas páginas terminan con st.stop().
    asistente.boton_flotante()
else:
    # Banda institucional con los filtros globales (aplican a todas las páginas de la vista Atenea)
    with st.container(key="banda"):
        st.markdown(estilo.banda_html(f"{comun.hoy():%d/%m/%Y}", enlace="?vista=interna" if interno_ok else None),
                    unsafe_allow_html=True)
        comun.filtros_banda(comun.todos())
        pie = st.columns([4, 1, 1])
        if correo:
            pie[0].caption(f"Sesión: {correo}")
        if pie[1].button("Actualizar", icon=":material/refresh:", width="stretch"):
            ui.refrescar()
            st.rerun()
        if correo:
            pie[2].button("Salir", icon=":material/logout:", on_click=acceso.cerrar_sesion, args=(sesion,),
                          width="stretch")

nav.run()

# Pie en todas las páginas: fuentes y fecha de corte (transparencia) y enlaces legales
try:
    _df = comun.todos()
    _sis = _df["actualizado_sis"].max() if "actualizado_sis" in _df else None
    import pandas as _pd  # noqa: E402
    _sis_txt = "" if _sis is None or _pd.isna(_pd.to_datetime(_sis, errors="coerce")) else \
        f" · SIS actualizado: {_pd.to_datetime(_sis):%d/%m/%Y %H:%M}"
    st.markdown(
        f"<div class='pie-legal'>Corte: {comun.hoy():%d/%m/%Y}{_sis_txt} · Fuentes: base de formalización, asignación "
        f"docente y plataforma académica (SIS) de Kuepa EduTech · Información confidencial: uso exclusivo para el "
        f"seguimiento del contrato {legal.CONTRATO}.</div>", unsafe_allow_html=True)
    if not interna:
        p1, p2, _ = st.columns([1, 1, 3])
        p1.page_link(PAGINAS_ATENEA[-2], label="Cómo se calcula", icon=":material/menu_book:")
        p2.page_link(PAGINAS_ATENEA[-1], label="Privacidad y términos", icon=":material/policy:")
except Exception:  # noqa: BLE001 -- el pie nunca debe tumbar la página
    pass
