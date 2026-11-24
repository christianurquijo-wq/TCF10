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
import time

import streamlit as st

from tcf10 import data, ui

MAX_INTENTOS = 5
BLOQUEO_SEG = 60


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
        _pantalla(error=f"La cuenta {correo} no está autorizada. Solicita acceso al equipo de Kuepa.", google_salir=True)
    _pantalla()


def aviso_modo(s: dict) -> None:
    if s.get("via") == "sin_login":
        st.warning("**Modo pruebas:** inicio de sesión desactivado. Quita `sin_login` de los Secrets antes de "
                   "compartir el enlace.", icon=":material/lock_open:")


def cerrar_sesion(s: dict) -> None:
    st.session_state.pop("vista", None)
    if s.get("via") == "google":
        st.logout()
    st.session_state.pop("at_usuario", None)


def _pantalla(error: str = "", google_salir: bool = False) -> None:
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
.login-o {text-align:center; color:#8A8FA8; font-size:.85rem; margin:10px 0;}
</style>""", unsafe_allow_html=True)
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
            bloqueado = st.session_state.get("at_bloqueo", 0) > time.time()
            with st.form("at_login", border=False):
                usuario = st.text_input("Usuario", key="at_login_usuario")
                clave = st.text_input("Contraseña", type="password", key="at_login_clave")
                entrar = st.form_submit_button("Ingresar", type="primary", width="stretch", disabled=bloqueado)
            if bloqueado:
                st.warning(f"Demasiados intentos. Espera {int(st.session_state['at_bloqueo'] - time.time())} s.")
            elif entrar:
                u = _usuarios().get(usuario.strip().lower())
                if u and verificar(clave, str(u.get("hash", ""))):
                    st.session_state["at_usuario"] = {"nombre": u.get("nombre", usuario), "via": "usuario"}
                    st.session_state.pop("at_intentos", None)
                    st.rerun()
                n = st.session_state.get("at_intentos", 0) + 1
                st.session_state["at_intentos"] = n
                if n >= MAX_INTENTOS:
                    st.session_state["at_bloqueo"] = time.time() + BLOQUEO_SEG
                    st.session_state["at_intentos"] = 0
                st.error("Usuario o contraseña incorrectos.", icon=":material/error:")
            if _hay_oauth():
                st.markdown("<div class='login-o'>o</div>", unsafe_allow_html=True)
                auth = st.secrets["auth"]
                proveedor = next((k for k in auth.keys() if hasattr(auth[k], "keys")), None)
                st.button("Ingresar con Google", icon=":material/account_circle:", on_click=st.login,
                          args=(proveedor,) if proveedor else (), width="stretch")
                st.caption("Con Google: cuentas @agenciaatenea.gov.co y @kuepa.com autorizadas.")
    st.stop()
