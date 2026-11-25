"""Inicio de sesión de la vista Atenea: usuario y contraseña (cuentas de prueba en los Secrets) o Google (OAuth).

Secrets:
    [atenea]
    dominios = ["agenciaatenea.gov.co", "kuepa.com"]   # quién entra con Google
    correos = []                                       # correos sueltos autorizados con Google
    sin_login = false                                  # true = sin pantalla de ingreso (solo pruebas internas)

    internos = ["persona@kuepa.com"]                   # correos (Google) que ven el botón «Vista interna»

    [atenea.usuarios.prueba]                           # una sección por usuario (genera el hash con
    nombre = "Usuario de prueba Atenea"                # python scripts/crear_usuario_atenea.py)
    hash = "pbkdf2_sha256$200000$<sal>$<hash>"

Las contraseñas nunca se guardan en texto plano: solo su hash PBKDF2 con sal.
"""
from __future__ import annotations

import hashlib
import hmac

import streamlit as st

from tcf10 import data, ui
from vista_atenea import legal, seguridad


def hash_contrasena(contrasena: str, sal: bytes, iteraciones: int = 200_000) -> str:
    h = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, iteraciones)
    return f"pbkdf2_sha256${iteraciones}${sal.hex()}${h.hex()}"


def verificar(contrasena: str, guardado: str) -> bool:
    try:
        algoritmo, iteraciones, sal, esperado = guardado.split("$")
        if algoritmo != "pbkdf2_sha256":
            return False
        calculado = hash_contrasena(contrasena, bytes.fromhex(sal), int(iteraciones)).split("$")[-1]
        return hmac.compare_digest(calculado, esperado)
    except (ValueError, AttributeError):
        return False


def _cfg() -> dict:
    try:
        return dict(st.secrets.get("atenea", {}))
    except Exception:  # noqa: BLE001
        return {}


def _usuarios() -> dict:
    u = _cfg().get("usuarios", {})
    return {k: dict(v) for k, v in dict(u).items()} if u else {}


def _hay_oauth() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:  # noqa: BLE001
        return False


def _correo_autorizado(correo: str) -> bool:
    cfg = _cfg()
    correos = {c.strip().lower() for c in cfg.get("correos", [])}
    dominios = {d.strip().lower().lstrip("@") for d in cfg.get("dominios", ["agenciaatenea.gov.co", "kuepa.com"])}
    return correo in correos or correo.split("@")[-1] in dominios


def sesion_actual() -> dict | None:
    """{'nombre', 'via'} si hay sesión válida; None si hay que mostrar la pantalla de ingreso (no dibuja nada)."""
    if data.modo_demo() or str(_cfg().get("sin_login", "")).lower() in ("true", "1", "si", "sí"):
        return {"nombre": "", "via": "demo" if data.modo_demo() else "sin_login"}
    if st.session_state.get("at_usuario"):
        return st.session_state["at_usuario"]
    if _hay_oauth() and st.user.is_logged_in and _correo_autorizado(str(st.user.get("email", "")).lower()):
        return {"nombre": str(st.user.get("email", "")).lower(), "via": "google"}
    return None


def es_interno(s: dict | None) -> bool:
    """¿Puede cambiar a la vista interna? Solo correos de Google listados en [atenea] internos (los usuarios de
    usuario/contraseña nunca). En modo demo sí, para probar con datos sintéticos."""
    if not s:
        return False
    if s.get("via") == "demo":
        return True
    if s.get("via") != "google":
        return False
    internos = {c.strip().lower() for c in _cfg().get("internos", [])}
    return str(s.get("nombre", "")).lower() in internos


def pantalla_ingreso() -> None:
    """Dibuja la pantalla de ingreso y detiene la página."""
    if _hay_oauth() and st.user.is_logged_in:
        correo = str(st.user.get("email", "")).lower()
        if not st.session_state.get("at_rechazo_reg"):
            st.session_state["at_rechazo_reg"] = True
            seguridad.registrar("ingreso_rechazado", correo, "google", "cuenta no autorizada")
        _pantalla(error=f"La cuenta {correo} no está autorizada. Solicita acceso al equipo de Kuepa.", google_salir=True)
    _pantalla()


def aviso_modo(s: dict) -> None:
    if s.get("via") == "sin_login":
        st.warning("**Modo pruebas:** inicio de sesión desactivado. Quita `sin_login` de los Secrets antes de "
                   "compartir el enlace.", icon=":material/lock_open:")


def identificar(s: dict | None) -> None:
    """Deja en la sesión el usuario y la vía para el registro de accesos y la marca de agua de las descargas."""
    if not s:
        return
    st.session_state["seg_usuario"] = s.get("usuario") or s.get("nombre", "")
    st.session_state["seg_via"] = s.get("via", "")


def cerrar_sesion(s: dict, motivo: str = "salida") -> None:
    if s and s.get("via") in ("usuario", "google"):
        seguridad.registrar(motivo, st.session_state.get("seg_usuario", ""), s.get("via", ""), esperar=True)
    for k in ("vista", "at_usuario", "at_acepto", "seg_ultima", "at_looker_ok"):
        st.session_state.pop(k, None)
    if motivo == "cierre_inactividad":
        st.session_state["at_aviso_inactividad"] = True
    if s and s.get("via") == "google":
        st.logout()


def exigir_aceptacion(s: dict) -> None:
    """Tras ingresar con Google: aceptar los términos vigentes (una vez por versión; queda en el registro)."""
    if s.get("via") != "google" or st.session_state.get("at_acepto") == legal.VERSION_TERMINOS:
        return
    correo = s.get("nombre", "")
    if seguridad.ya_acepto(correo, legal.VERSION_TERMINOS):
        st.session_state["at_acepto"] = legal.VERSION_TERMINOS
        seguridad.registrar("ingreso", correo, "google")
        return
    _css()
    with st.container(key="login"):
        with st.container(key="login_form"):
            st.markdown("<div class='login-h'>Antes de continuar</div>", unsafe_allow_html=True)
            st.markdown(legal.AVISO_CORTO)
            if st.button("Leer términos de uso y aviso de privacidad", icon=":material/gavel:", type="tertiary"):
                legal.dialogo()
            acepto = st.checkbox("He leído y acepto los Términos de uso y el Aviso de privacidad", key="at_g_acepto")
            c1, c2 = st.columns(2)
            if c1.button("Continuar", type="primary", width="stretch", disabled=not acepto):
                st.session_state["at_acepto"] = legal.VERSION_TERMINOS
                seguridad.registrar("acepta_terminos", correo, "google")
                seguridad.registrar("ingreso", correo, "google")
                st.rerun()
            c2.button("Salir", on_click=st.logout, width="stretch")
            st.caption(f"Sesión de Google: {correo}")
    st.stop()


def _css() -> None:
    st.markdown("""
<style>
.st-key-login {max-width: 920px; margin: 4vh auto 0 auto;}
.st-key-login_marca {background:#141439; border-radius:18px; padding:30px 28px; height:100%;}
.st-key-login_form {background:#FFFFFF; border:1px solid #D3E7EF; border-radius:18px; padding:26px 26px 18px 26px;
                    box-shadow:0 4px 18px rgba(20,20,57,.08);}
.login-eyebrow {font-size:.78rem; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:#EF6F18;}
.login-titulo {font-family:'Barlow Semi Condensed', sans-serif; font-size:2.2rem; font-weight:700; color:#fff;
               line-height:1.05; margin:6px 0 10px 0;}
.login-texto {color:#B7D9E6; font-size:.95rem;}
.login-h {font-family:'Barlow Semi Condensed', sans-serif; font-size:1.5rem; font-weight:700; color:#141439;}
.login-o {text-align:center; color:#5E6488; font-size:.85rem; margin:10px 0;}
.login-aviso {color:#4A4F78; font-size:.85rem; margin:4px 0 8px 0;}
</style>""", unsafe_allow_html=True)


def _pantalla(error: str = "", google_salir: bool = False) -> None:
    _css()
    with st.container(key="login"):
        izq, der = st.columns([1, 1.1], gap="large")
        with izq.container(key="login_marca"):
            st.markdown(f"<img src='{ui._logo(blanco=True)}' style='height:46px' alt='Agencia Atenea'>"
                        "<div class='login-eyebrow' style='margin-top:26px'>Informe de seguimiento</div>"
                        "<div class='login-titulo'>Talento Capital · Formación 10</div>"
                        "<div class='login-texto'>Asistencia, progreso y estado de los participantes del contrato "
                        "ATENEA-497-2026.</div>"
                        f"<div style='margin-top:26px'>{ui.chip_kuepa()}</div>", unsafe_allow_html=True)
        with der.container(key="login_form"):
            st.markdown("<div class='login-h'>Ingresar</div>", unsafe_allow_html=True)
            if error:
                st.error(error, icon=":material/block:")
                if google_salir:
                    st.button("Cerrar sesión de Google", on_click=st.logout)
            if st.session_state.pop("at_aviso_inactividad", False):
                st.info(f"Tu sesión se cerró tras {seguridad.INACTIVIDAD_MIN} minutos sin actividad. Ingresa de nuevo.",
                        icon=":material/timer_off:")
            st.markdown(f"<div class='login-aviso'>{legal.AVISO_CORTO.replace('**', '')}</div>",
                        unsafe_allow_html=True)
            with st.form("at_login", border=False):
                usuario = st.text_input("Usuario", key="at_login_usuario", autocomplete="username")
                clave = st.text_input("Contraseña", type="password", key="at_login_clave",
                                      autocomplete="current-password")
                acepto = st.checkbox("He leído y acepto los Términos de uso y el Aviso de privacidad",
                                     key="at_login_acepto")
                entrar = st.form_submit_button("Ingresar", type="primary", width="stretch")
            if st.button("Leer términos de uso y aviso de privacidad", icon=":material/gavel:", type="tertiary"):
                legal.dialogo()
            if entrar:
                nombre_u = usuario.strip().lower()[:80]
                hasta = seguridad.bloqueado_hasta(nombre_u)
                if hasta:
                    st.error(f"Usuario bloqueado por {seguridad.MAX_INTENTOS} intentos fallidos. Intenta de nuevo "
                             f"después de las {hasta:%H:%M} (hora Colombia).", icon=":material/lock_clock:")
                elif not acepto:
                    st.error("Para ingresar debes aceptar los Términos de uso y el Aviso de privacidad.",
                             icon=":material/gavel:")
                else:
                    u = _usuarios().get(nombre_u)
                    if u and verificar(clave, str(u.get("hash", ""))):
                        st.session_state["at_usuario"] = {"nombre": u.get("nombre", usuario), "via": "usuario",
                                                          "usuario": nombre_u}
                        st.session_state["at_acepto"] = legal.VERSION_TERMINOS
                        seguridad.limpiar_fallos(nombre_u)
                        seguridad.registrar("acepta_terminos", nombre_u, "usuario")
                        seguridad.registrar("ingreso", nombre_u, "usuario")
                        st.rerun()
                    seguridad.anotar_fallo(nombre_u)
                    if seguridad.bloqueado_hasta(nombre_u):
                        st.error(f"Usuario bloqueado {seguridad.BLOQUEO_MIN} minutos por intentos fallidos.",
                                 icon=":material/lock_clock:")
                    else:
                        st.error("Usuario o contraseña incorrectos.", icon=":material/error:")
            if _hay_oauth():
                st.markdown("<div class='login-o'>o</div>", unsafe_allow_html=True)
                auth = st.secrets["auth"]
                proveedor = next((k for k in auth.keys() if hasattr(auth[k], "keys")), None)
                st.button("Ingresar con Google", icon=":material/account_circle:", on_click=st.login,
                          args=(proveedor,) if proveedor else (), width="stretch")
                st.caption("Con Google: cuentas @agenciaatenea.gov.co y @kuepa.com autorizadas. Al ingresar se te "
                           "pedirá aceptar los términos.")
    st.stop()
