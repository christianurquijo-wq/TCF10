"""Usuarios con contraseña propia (nov-2026): pestaña «USUARIOS STREAMLIT» de la DB Formalización TCF10.

Kuepa llena: correo, nombre y estado (Activo / Inactivo). Solo esos correos pueden crear o recuperar su contraseña
con un código de 6 dígitos que llega por correo (Google Apps Script, ver scripts/apps_script_correo.gs). La app
escribe el resto de columnas: la huella de la contraseña (PBKDF2, nunca la contraseña) y el estado del código.

Secrets:
    [atenea]
    correo_url = "https://script.google.com/macros/s/…/exec"   # web app de Apps Script
    correo_secreto = "…"                                        # la misma clave que en las propiedades del script
    usuarios_pestana = "USUARIOS STREAMLIT"                     # opcional
La cuenta de servicio necesita permiso de EDITOR en la DB Formalización (hoy suele tener solo Lector).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import secrets as _secrets
import time
import urllib.request

import streamlit as st

from tcf10 import data

PESTANA = "USUARIOS STREAMLIT"
ENCABEZADOS = ["correo", "nombre", "estado", "hash_contrasena", "creada", "actualizada", "codigo_hash",
               "codigo_vence", "codigo_intentos", "envios"]
VIGENCIA_MIN = 15          # el código vence a los 15 minutos
MAX_ENVIOS_HORA = 3        # códigos por correo por hora
MAX_INTENTOS_CODIGO = 5    # intentos con un mismo código antes de anularlo
MIN_LARGO = 10             # largo mínimo de la contraseña


def _cfg() -> dict:
    try:
        return dict(st.secrets.get("atenea", {}))
    except Exception:  # noqa: BLE001
        return {}


def disponible() -> bool:
    """¿Está configurado el envío de códigos? (sin él no se muestra «Crear o recuperar contraseña»)."""
    c = _cfg()
    return bool(c.get("correo_url") and c.get("correo_secreto")) and not data.modo_demo()


def _ahora() -> dt.datetime:
    from vista_atenea.seguridad import ahora
    return ahora()


# ------------------------------------------------------------------ hoja
def _norm(t: str) -> str:
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFKD", str(t)) if not unicodedata.combining(c))
    return "_".join(t.strip().lower().split())


@st.cache_resource(show_spinner=False)
def _hoja_conectada():
    """La pestaña (se crea si no existe). Respeta las columnas que Kuepa ya haya puesto: las que falten se agregan al
    final, nunca se reescriben encabezados existentes."""
    import gspread
    gc = gspread.authorize(data._credenciales(["https://www.googleapis.com/auth/spreadsheets"]))
    libro = gc.open_by_key(data._cfg()["sheet_id"])
    nombre = _cfg().get("usuarios_pestana", PESTANA)
    try:
        ws = libro.worksheet(nombre)
    except gspread.exceptions.WorksheetNotFound:
        ws = libro.add_worksheet(nombre, rows=200, cols=len(ENCABEZADOS))
    actuales = ws.row_values(1)
    presentes = {_norm(c) for c in actuales if c.strip()}
    faltan = [c for c in ENCABEZADOS if c not in presentes]
    if faltan:
        ancho = len(actuales) if any(c.strip() for c in actuales) else 0
        if ws.col_count < ancho + len(faltan):
            ws.add_cols(ancho + len(faltan) - ws.col_count)
        from gspread.utils import rowcol_to_a1
        ws.update(range_name=rowcol_to_a1(1, ancho + 1), values=[faltan])
    return ws


def _hoja():
    try:
        return _hoja_conectada()
    except Exception as e:  # noqa: BLE001
        print(f"[usuarios] pestaña no disponible: {type(e).__name__}: {str(e)[:160]}")
        return None


def _filas() -> tuple[object, list[dict]]:
    ws = _hoja()
    if ws is None:
        return None, []
    valores = ws.get_all_values()
    if not valores:
        return ws, []
    indice = {}
    for k, c in enumerate(valores[0]):
        indice.setdefault(_norm(c), k)
    ws._tcf10_indice = indice  # columnas por nombre, para escribir cada dato en su sitio
    filas = []
    for i, v in enumerate(valores[1:], start=2):
        d = {c: (v[indice[c]] if c in indice and indice[c] < len(v) else "") for c in ENCABEZADOS}
        d["_fila"] = i
        d["correo"] = d["correo"].strip().lower()
        if d["correo"]:
            filas.append(d)
    return ws, filas


APP_ESCRIBE = ["hash_contrasena", "creada", "actualizada", "codigo_hash", "codigo_vence", "codigo_intentos", "envios"]


def _guardar(ws, fila: dict) -> None:
    """Escribe solo las columnas que maneja la app (correo, nombre y estado son de Kuepa)."""
    from gspread.utils import rowcol_to_a1
    indice = getattr(ws, "_tcf10_indice", {})
    datos = [{"range": rowcol_to_a1(fila["_fila"], indice[c] + 1), "values": [[fila.get(c, "")]]}
             for c in APP_ESCRIBE if c in indice]
    if datos:
        ws.batch_update(datos, value_input_option="RAW")


def _buscar(correo: str) -> tuple[object, dict | None]:
    ws, filas = _filas()
    correo = correo.strip().lower()
    return ws, next((f for f in filas if f["correo"] == correo), None)


def _activo(f: dict | None) -> bool:
    return bool(f) and f.get("estado", "").strip().lower() in ("activo", "si", "sí", "true", "1")


# ------------------------------------------------------------------ ingreso
def verificar_ingreso(correo: str, contrasena: str) -> dict | None:
    """{'nombre', 'usuario'} si el correo está activo en la pestaña y la contraseña coincide."""
    from vista_atenea.acceso import verificar
    if not correo or "@" not in correo:
        return None
    _, f = _buscar(correo)
    if not _activo(f) or not f.get("hash_contrasena"):
        return None
    if verificar(contrasena, f["hash_contrasena"]):
        return {"nombre": f.get("nombre") or correo, "usuario": f["correo"]}
    return None


# ------------------------------------------------------------------ códigos
def _huella_codigo(correo: str, codigo: str) -> str:
    clave = str(_cfg().get("correo_secreto", "")).encode()
    return hmac.new(clave, f"{correo}|{codigo}".encode(), hashlib.sha256).hexdigest()


def _enviar(correo: str, nombre: str, codigo: str) -> bool:
    c = _cfg()
    cuerpo = json.dumps({"secreto": c["correo_secreto"], "para": correo, "nombre": nombre, "codigo": codigo,
                         "minutos": VIGENCIA_MIN}).encode()
    req = urllib.request.Request(c["correo_url"], data=cuerpo, headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 -- URL fija de los Secrets (Apps Script)
            respuesta = json.loads(r.read().decode() or "{}")
        return bool(respuesta.get("ok"))
    except Exception as e:  # noqa: BLE001
        print(f"[usuarios] no se pudo enviar el código: {type(e).__name__}: {str(e)[:160]}")
        return False


def solicitar_codigo(correo: str) -> str:
    """Envía un código si el correo está autorizado. Devuelve 'ok', 'limite' o 'error' (para el usuario siempre se
    muestra el mismo mensaje cuando el correo no está autorizado: no se revela quién está en la lista)."""
    from vista_atenea.seguridad import registrar
    correo = correo.strip().lower()
    ws, f = _buscar(correo)
    if ws is None:
        return "error"
    if not _activo(f):
        registrar("codigo_no_autorizado", correo[:80], "usuario")
        return "ok"
    ahora = time.time()
    envios = [float(x) for x in str(f.get("envios", "")).split(";") if x.strip()]
    envios = [x for x in envios if ahora - x < 3600]
    if len(envios) >= MAX_ENVIOS_HORA:
        return "limite"
    codigo = f"{_secrets.randbelow(1_000_000):06d}"
    if not _enviar(correo, f.get("nombre", ""), codigo):
        return "error"
    f.update({"codigo_hash": _huella_codigo(correo, codigo),
              "codigo_vence": str(int(ahora + VIGENCIA_MIN * 60)), "codigo_intentos": "0",
              "envios": ";".join(str(int(x)) for x in envios + [ahora])})
    _guardar(ws, f)
    registrar("codigo_enviado", correo, "usuario")
    return "ok"


def validar_contrasena(c1: str, c2: str) -> str:
    """'' si sirve; si no, el motivo."""
    if c1 != c2:
        return "Las contraseñas no coinciden."
    if len(c1) < MIN_LARGO:
        return f"La contraseña debe tener al menos {MIN_LARGO} caracteres."
    if not any(ch.isalpha() for ch in c1) or not any(ch.isdigit() for ch in c1):
        return "La contraseña debe combinar letras y números."
    return ""


def cambiar_con_codigo(correo: str, codigo: str, nueva: str) -> str:
    """'ok', 'codigo' (inválido o vencido) o 'error'."""
    from vista_atenea.acceso import hash_contrasena
    from vista_atenea.seguridad import registrar
    correo = correo.strip().lower()
    ws, f = _buscar(correo)
    if ws is None:
        return "error"
    if not _activo(f) or not f.get("codigo_hash"):
        return "codigo"
    intentos = int(f.get("codigo_intentos") or 0)
    vence = float(f.get("codigo_vence") or 0)
    if time.time() > vence or intentos >= MAX_INTENTOS_CODIGO:
        return "codigo"
    if not hmac.compare_digest(_huella_codigo(correo, codigo.strip()), f["codigo_hash"]):
        f["codigo_intentos"] = str(intentos + 1)
        _guardar(ws, f)
        return "codigo"
    primera = not f.get("hash_contrasena")
    marca = _ahora().strftime("%Y-%m-%d %H:%M:%S")
    f.update({"hash_contrasena": hash_contrasena(nueva, os.urandom(16)), "codigo_hash": "", "codigo_vence": "",
              "codigo_intentos": "", "actualizada": marca})
    if primera:
        f["creada"] = marca
    _guardar(ws, f)
    registrar("contrasena_creada" if primera else "contrasena_restablecida", correo, "usuario")
    return "ok"


# ------------------------------------------------------------------ pantalla
def pantalla_clave() -> None:
    """Crear o recuperar contraseña (dentro de la tarjeta de ingreso)."""
    paso = st.session_state.get("at_clave_paso", 1)
    st.markdown("<div class='login-h'>Crear o recuperar contraseña</div>", unsafe_allow_html=True)
    if paso == 1:
        st.caption("Escribe tu correo. Si está autorizado, te enviaremos un código de 6 dígitos válido por "
                   f"{VIGENCIA_MIN} minutos. Revisa también la carpeta de correo no deseado.")
        with st.form("at_clave_1", border=False):
            correo = st.text_input("Correo", key="at_clave_correo", autocomplete="email")
            enviar = st.form_submit_button("Enviar código", type="primary", width="stretch")
        if enviar:
            if "@" not in correo:
                st.error("Escribe un correo válido.", icon=":material/error:")
            else:
                r = solicitar_codigo(correo)
                if r == "limite":
                    st.warning(f"Ya se enviaron {MAX_ENVIOS_HORA} códigos en la última hora. Intenta más tarde.",
                               icon=":material/schedule:")
                elif r == "error":
                    st.error("No pudimos enviar el código en este momento. Intenta de nuevo en unos minutos o "
                             "escribe a contactotalentocapital@kuepa.com.", icon=":material/error:")
                else:
                    st.session_state["at_clave_para"] = correo.strip().lower()
                    st.session_state["at_clave_paso"] = 2
                    st.rerun()
    else:
        correo = st.session_state.get("at_clave_para", "")
        st.info(f"Si **{correo}** está autorizado, le llegó un código. Escríbelo junto con tu nueva contraseña.",
                icon=":material/mark_email_read:")
        with st.form("at_clave_2", border=False):
            codigo = st.text_input("Código de 6 dígitos", key="at_clave_codigo", max_chars=6,
                                   autocomplete="one-time-code")
            c1 = st.text_input("Nueva contraseña", type="password", key="at_clave_n1", autocomplete="new-password",
                               help=f"Mínimo {MIN_LARGO} caracteres, con letras y números.")
            c2 = st.text_input("Confirmar contraseña", type="password", key="at_clave_n2",
                               autocomplete="new-password")
            guardar = st.form_submit_button("Guardar contraseña", type="primary", width="stretch")
        if guardar:
            motivo = validar_contrasena(c1, c2)
            if motivo:
                st.error(motivo, icon=":material/error:")
            else:
                r = cambiar_con_codigo(correo, codigo, c1)
                if r == "ok":
                    for k in ("at_clave_paso", "at_clave_para"):
                        st.session_state.pop(k, None)
                    st.session_state["at_modo_login"] = "ingresar"
                    st.session_state["at_aviso_clave"] = True
                    st.rerun()
                elif r == "codigo":
                    st.error("El código no es válido o ya venció. Pide uno nuevo.", icon=":material/error:")
                else:
                    st.error("No pudimos guardar la contraseña. Intenta de nuevo en unos minutos.",
                             icon=":material/error:")
        if st.button("Pedir otro código", type="tertiary", icon=":material/refresh:"):
            st.session_state["at_clave_paso"] = 1
            st.rerun()
    if st.button("Volver a ingresar", type="tertiary", icon=":material/arrow_back:"):
        st.session_state["at_modo_login"] = "ingresar"
        st.session_state.pop("at_clave_paso", None)
        st.rerun()
