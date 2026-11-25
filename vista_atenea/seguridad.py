"""Controles de seguridad de la app (nov-2026): registro de accesos y descargas, cierre por inactividad y bloqueo por
intentos fallidos de contraseña.

Registro: pestaña «Registro de accesos» del Google Sheet de Asignación docente (o [atenea] registro_sheet_id). La crea
la app con sus encabezados; la cuenta de servicio [gcp_service_account] necesita permiso de EDITOR en ese Sheet.
Se registra lo mínimo para auditar (fecha y hora, evento, usuario, vía de ingreso, detalle, versión de términos y un
identificador corto de la sesión). Nunca se guardan contraseñas, direcciones IP ni datos de los participantes.

Si el Sheet no responde, la app sigue funcionando (el registro es «mejor esfuerzo») y el bloqueo por intentos usa el
contador de la sesión.
"""
from __future__ import annotations

import datetime as dt
import threading
import time
import uuid
from zoneinfo import ZoneInfo

import streamlit as st

from tcf10 import data

ZONA = ZoneInfo("America/Bogota")
INACTIVIDAD_MIN = 30          # cierre de sesión tras 30 min sin interacción
MAX_INTENTOS = 5              # intentos fallidos de contraseña…
BLOQUEO_MIN = 15              # …antes de bloquear el usuario 15 min
PESTANA = "Registro de accesos"
ENCABEZADOS = ["Fecha y hora (Bogotá)", "Evento", "Usuario", "Vía", "Detalle", "Versión términos", "Sesión"]
FORMATO = "%Y-%m-%d %H:%M:%S"


def ahora() -> dt.datetime:
    return dt.datetime.now(ZONA)


def id_sesion() -> str:
    if "seg_id" not in st.session_state:
        st.session_state["seg_id"] = uuid.uuid4().hex[:8]
    return st.session_state["seg_id"]


# ------------------------------------------------------------------ hoja de registro
def _sheet_id() -> str:
    try:
        cfg = dict(st.secrets.get("atenea", {}))
    except Exception:  # noqa: BLE001
        cfg = {}
    return str(cfg.get("registro_sheet_id") or data.ASIGNACION_SHEET_ID)


@st.cache_resource(show_spinner=False)
def _hoja_conectada():
    """Pestaña de registro (se crea si no existe). Lanza excepción si no hay permiso: así un fallo pasajero no queda
    guardado en caché y se reintenta más tarde."""
    import gspread
    gc = gspread.authorize(data._credenciales(["https://www.googleapis.com/auth/spreadsheets"]))
    libro = gc.open_by_key(_sheet_id())
    try:
        ws = libro.worksheet(PESTANA)
    except gspread.exceptions.WorksheetNotFound:
        ws = libro.add_worksheet(PESTANA, rows=1000, cols=len(ENCABEZADOS))
        ws.update(range_name="A1", values=[ENCABEZADOS])
        ws.freeze(rows=1)
    return ws


_ULTIMO_FALLO = {"t": 0.0}


def _hoja():
    """La pestaña de registro, o None (modo demo, sin permiso o sin conexión; se reintenta cada 5 min)."""
    if data.modo_demo() or time.time() - _ULTIMO_FALLO["t"] < 300:
        return None
    try:
        return _hoja_conectada()
    except Exception as e:  # noqa: BLE001 -- sin registro la app sigue; se avisa en el log del servidor
        _ULTIMO_FALLO["t"] = time.time()
        print(f"[seguridad] registro no disponible: {type(e).__name__}: {str(e)[:160]}")
        return None


def registrar(evento: str, usuario: str = "", via: str = "", detalle: str = "", esperar: bool = False) -> None:
    """Agrega una fila al registro en segundo plano (no frena la app)."""
    from vista_atenea import legal  # import tardío: legal importa streamlit y no depende de este módulo
    fila = [ahora().strftime(FORMATO), evento, usuario, via, detalle, legal.VERSION_TERMINOS, id_sesion()]
    ws = _hoja()
    if ws is None:
        return

    def escribir():
        try:
            ws.append_row(fila, value_input_option="RAW", table_range="A1")
        except Exception as e:  # noqa: BLE001
            print(f"[seguridad] no se pudo registrar {evento}: {type(e).__name__}")

    hilo = threading.Thread(target=escribir, daemon=True)
    hilo.start()
    if esperar:
        hilo.join(timeout=5)


# ------------------------------------------------------------------ intentos fallidos
def _fallos_en_hoja(usuario: str, desde: dt.datetime) -> tuple[int, dt.datetime | None]:
    """Fallos de `usuario` desde `desde` que no fueron seguidos de un ingreso exitoso."""
    ws = _hoja()
    if ws is None:
        return 0, None
    try:
        filas = ws.get("A2:C")
    except Exception:  # noqa: BLE001
        return 0, None
    n, ultimo = 0, None
    for f in filas:
        if len(f) < 3 or f[2].strip().lower() != usuario:
            continue
        try:
            t = dt.datetime.strptime(f[0], FORMATO).replace(tzinfo=ZONA)
        except ValueError:
            continue
        if t < desde:
            continue
        if f[1] == "ingreso":
            n, ultimo = 0, None
        elif f[1] == "ingreso_fallido":
            n, ultimo = n + 1, t
    return n, ultimo


def bloqueado_hasta(usuario: str) -> dt.datetime | None:
    """Hora hasta la que el usuario está bloqueado, o None. Cuenta los fallos de la sesión y los del registro
    (así recargar la página no reinicia el contador)."""
    usuario = usuario.strip().lower()
    if not usuario:
        return None
    ventana = ahora() - dt.timedelta(minutes=BLOQUEO_MIN)
    locales = [t for t in st.session_state.get("seg_fallos", {}).get(usuario, []) if t >= ventana]
    n_hoja, ultimo_hoja = _fallos_en_hoja(usuario, ventana)
    n = max(len(locales), n_hoja)
    if n < MAX_INTENTOS:
        return None
    ultimo = max([t for t in locales] + ([ultimo_hoja] if ultimo_hoja else []))
    fin = ultimo + dt.timedelta(minutes=BLOQUEO_MIN)
    return fin if fin > ahora() else None


def anotar_fallo(usuario: str) -> None:
    usuario = usuario.strip().lower()
    fallos = st.session_state.setdefault("seg_fallos", {})
    fallos.setdefault(usuario, []).append(ahora())
    registrar("ingreso_fallido", usuario, "usuario", esperar=True)


def limpiar_fallos(usuario: str) -> None:
    st.session_state.get("seg_fallos", {}).pop(usuario.strip().lower(), None)


def ya_acepto(usuario: str, version: str) -> bool:
    """¿El usuario ya aceptó esta versión de los términos (según el registro)? Se consulta una vez por sesión."""
    clave = f"seg_acepto_{usuario}_{version}"
    if clave in st.session_state:
        return st.session_state[clave]
    ok = False
    ws = _hoja()
    if ws is not None:
        try:
            ok = any(len(f) >= 6 and f[1] == "acepta_terminos" and f[2].strip().lower() == usuario
                     and f[5] == version for f in ws.get("A2:F"))
        except Exception:  # noqa: BLE001
            ok = False
    st.session_state[clave] = ok
    return ok


# ------------------------------------------------------------------ inactividad
def expirada() -> bool:
    """True si pasaron más de INACTIVIDAD_MIN minutos desde la última interacción de esta sesión."""
    ultima = st.session_state.get("seg_ultima")
    return bool(ultima) and (time.time() - ultima) > INACTIVIDAD_MIN * 60


def tocar() -> None:
    st.session_state["seg_ultima"] = time.time()


# ------------------------------------------------------------------ descargas
def usuario_actual() -> str:
    return str(st.session_state.get("seg_usuario", "") or "")


def excel_confidencial(tabla, hoja: str = "Datos", titulo: str = "") -> bytes:
    """Excel con marca de agua: aviso de confidencialidad, usuario y fecha de descarga arriba de la tabla, en el
    encabezado/pie de impresión y en las propiedades del archivo."""
    import io

    import pandas as pd
    from openpyxl.styles import Font, PatternFill

    from vista_atenea import legal
    quien = usuario_actual() or "usuario no identificado"
    cuando = ahora().strftime("%d/%m/%Y %H:%M")
    marca = f"CONFIDENCIAL · Descargado por {quien} el {cuando} (hora Colombia)"
    nota = (f"Datos personales tratados por Kuepa EduTech como encargado de Atenea (Ley 1581 de 2012). Uso exclusivo "
            f"para el seguimiento del contrato {legal.CONTRATO}. Prohibida su divulgación o reenvío a terceros.")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        tabla.to_excel(xw, sheet_name=hoja[:31], index=False, startrow=3)
        ws = xw.sheets[hoja[:31]]
        ws["A1"] = (titulo + " · " if titulo else "") + marca
        ws["A1"].font = Font(bold=True, color="FFFFFF", size=12)
        ws["A2"] = nota
        ws["A2"].font = Font(italic=True, color="141439", size=10)
        for celda, fondo in (("A1", "E55B0E"), ("A2", "EEF6F9")):
            ws[celda].fill = PatternFill("solid", fgColor=fondo)
        ancho = max(1, len(tabla.columns))
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ancho)
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ancho)
        for celda in ws[4]:
            celda.font = Font(bold=True, color="FFFFFF")
            celda.fill = PatternFill("solid", fgColor="141439")
        ws.freeze_panes = "A5"
        ws.auto_filter.ref = f"A4:{ws.cell(row=4, column=ancho).column_letter}{4 + len(tabla)}"
        ws.oddHeader.center.text = "CONFIDENCIAL"
        ws.oddFooter.left.text = marca
        ws.oddFooter.right.text = "Página &P de &N"
        props = xw.book.properties
        props.creator = "Kuepa EduTech · Talento Capital F10"
        props.title = titulo or hoja
        props.subject = "CONFIDENCIAL · datos personales"
        props.description = marca + ". " + nota
        props.keywords = "confidencial; Ley 1581"
    return buf.getvalue()


def boton_descarga(etiqueta: str, tabla, archivo: str, hoja: str, titulo: str = "", clave: str = "") -> None:
    """Botón de descarga del Excel confidencial; cada descarga queda en el registro."""
    datos = excel_confidencial(tabla, hoja, titulo)
    st.download_button(etiqueta, datos, archivo,
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       icon=":material/download:", key=clave or f"dl_{archivo}",
                       on_click=registrar, args=("descarga", usuario_actual(), st.session_state.get("seg_via", ""),
                                                 f"{archivo} · {len(tabla)} filas"))
    st.caption("El archivo lleva tu usuario y la fecha de descarga, y queda registrado. Trátalo como información "
               "confidencial.")


def bloque_vistas_crudas() -> None:
    """Descarga en un ZIP de las vistas crudas del SIS (CSV). Se genera solo al pedirlo y queda en el registro."""
    from vista_atenea import legal
    st.markdown("**Vistas del SIS en crudo (CSV)**")
    st.caption(f"Un ZIP con {len(data.VISTAS_CRUDAS)} archivos CSV, uno por vista de la plataforma académica, tal cual "
               "están en BigQuery y sin filtros: " + ", ".join(data.VISTAS_CRUDAS) + ". Incluye datos personales "
               "de contacto y actividad: trátalo como información confidencial.")
    if data.modo_demo():
        st.info("Disponible solo con la conexión a BigQuery (no en modo demostración).", icon=":material/info:")
        return
    zip_ok = st.session_state.get("seg_zip_crudo")
    if not zip_ok:
        if st.button("Preparar ZIP de vistas SIS", icon=":material/folder_zip:", key="at_zip_preparar"):
            quien, cuando = usuario_actual() or "usuario no identificado", ahora().strftime("%d/%m/%Y %H:%M")
            leeme = (f"CONFIDENCIAL · Descargado por {quien} el {cuando} (hora Colombia).\n"
                     f"Vistas crudas del SIS de {legal.PROGRAMA} ({data._cfg().get('sis_dataset') or data.DATASET_CRUDO}).\n"
                     f"Datos personales tratados por Kuepa EduTech como encargado de Atenea (Ley 1581 de 2012). Uso "
                     f"exclusivo para el seguimiento del contrato {legal.CONTRATO}. Prohibida su divulgación o reenvío "
                     f"a terceros. Elimina el archivo cuando ya no lo necesites.\n"
                     f"Fechas y horas tal como las guarda la plataforma (UTC).\n")
            barra = st.progress(0.0, text="Consultando BigQuery…")
            try:
                datos, filas = data.zip_vistas_crudas(
                    leeme, avance=lambda i, v: barra.progress((i - 1) / len(data.VISTAS_CRUDAS), text=f"Leyendo {v}…"))
            except data.ErrorConfiguracion as e:
                barra.empty()
                st.error(str(e), icon=":material/error:")
                return
            barra.empty()
            st.session_state["seg_zip_crudo"] = (datos, filas, ahora().strftime("%Y%m%d_%H%M"))
            st.rerun()
        return
    datos, filas, sello = zip_ok
    resumen = " · ".join(f"{v.replace('VTD10_student_', '')}: {n:,}".replace(",", ".") for v, n in filas.items())
    st.caption(f"Listo ({len(datos) / 1e6:.1f} MB) · filas por vista: {resumen}")

    def _descargado():
        registrar("descarga", usuario_actual(), st.session_state.get("seg_via", ""),
                  f"vistas SIS crudas (ZIP) · {sum(filas.values())} filas")
        st.session_state.pop("seg_zip_crudo", None)  # no se guarda en memoria más de lo necesario

    st.download_button("Descargar ZIP de vistas SIS", datos, f"TCF10_vistas_SIS_{sello}.zip", "application/zip",
                       icon=":material/download:", key="at_zip_descargar", type="primary", on_click=_descargado)
