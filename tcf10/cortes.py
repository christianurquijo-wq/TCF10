"""Cortes semanales de la DB Formación TCF10: una COPIA del archivo de cada cohorte «como si se hubiera generado el
domingo a las 11:59 p. m.» de cada semana de la cohorte.

Cada corte:
    1. Copia el archivo original de la cohorte (todas sus pestañas y formatos) en la carpeta de cortes.
    2. En la copia, escribe en «Seg.Formación» las cifras reconstruidas hasta ese domingo (mismo cálculo del tablero con
       fecha de corte: asistencia sesión por sesión, horas asincrónicas por recursos completados hasta ese día y
       retiros posteriores como «en formación»). La semana de la cohorte (N3) y «Control actualización» también.
    3. Cambia HOY()/AHORA() de las fórmulas por la fecha del corte, deja que ICP y ESTADO se recalculen y CONGELA todas
       las pestañas en valores: la copia ya no cambia aunque cambie el original.
    4. Le pone a la copia marcas internas (appProperties) para reconocerla: no se duplica si se corre otra vez.

Qué domingos: desde el primer domingo después del inicio de la cohorte (inicio más frecuente de sus grupos) hasta el
domingo de cierre (primer domingo en o después del último FECHA_FIN de sus grupos). Después de eso la cohorte no
genera más cortes. Nunca un domingo futuro.

Configuración: [db_formacion] carpeta_cortes = "<ID de la carpeta>" en los Secrets (o la variable
DB_FORMACION_CARPETA_CORTES). La carpeta debe estar en una UNIDAD COMPARTIDA (las cuentas de servicio no tienen cuota
en «Mi unidad») y la cuenta de servicio debe ser «Administrador de contenido» de esa unidad.

Se usa desde scripts/cortes_semanales.py (GitHub Actions del domingo / Panel) y desde la página «Bases de formación».
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import pandas as pd

from tcf10 import config as C
from tcf10 import db_formacion as D

DRIVE = "https://www.googleapis.com/drive/v3/files"
SHEETS = "https://sheets.googleapis.com/v4/spreadsheets"
ALCANCES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
TIPO = "corte_semanal_db_formacion"
_HOY_RE = re.compile(r"\b(TODAY|HOY)\(\s*\)", re.I)
_AHORA_RE = re.compile(r"\b(NOW|AHORA)\(\s*\)", re.I)


# ------------------------------------------------------------------ calendario
def ultimo_domingo(hoy) -> pd.Timestamp:
    """Domingo más reciente en o antes de `hoy` (si hoy es domingo, hoy). Aguanta que el cron arranque tarde."""
    d = pd.Timestamp(hoy).normalize()
    return d - pd.Timedelta(days=(d.weekday() + 1) % 7)


def primer_domingo_desde(fecha) -> pd.Timestamp:
    d = pd.Timestamp(fecha).normalize()
    return d + pd.Timedelta(days=(6 - d.weekday()) % 7)


@dataclass
class Cohorte:
    sheet_id: str
    titulo: str
    inicio: pd.Timestamp | None
    fin: pd.Timestamp | None
    personas: int = 0
    domingos: list[pd.Timestamp] = field(default_factory=list)

    @property
    def cierre(self) -> pd.Timestamp | None:
        return primer_domingo_desde(self.fin) if self.fin is not None else None

    def semana(self, corte) -> int:
        if self.inicio is None:
            return 1
        dias = (pd.Timestamp(corte).normalize() - self.inicio).days
        return int(min(C.SEMANAS_PLAN, max(1, dias // 7 + 1)))


def calendario(inicios: pd.Series, fines: pd.Series) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Inicio = el más frecuente de los grupos (como la semana de N3); fin = el último FECHA_FIN de sus grupos."""
    i = pd.to_datetime(inicios, errors="coerce").dropna().dt.normalize()
    f = pd.to_datetime(fines, errors="coerce").dropna().dt.normalize()
    if i.empty:
        return None, None
    inicio = i.mode().iloc[0]
    fin = f.max() if len(f) else inicio + pd.Timedelta(weeks=C.SEMANAS_PLAN) - pd.Timedelta(days=1)
    return inicio, fin


def domingos(inicio, fin, hasta) -> list[pd.Timestamp]:
    """Domingos de corte de la cohorte hasta `hasta` (incluido) y nunca después del domingo de cierre."""
    if inicio is None:
        return []
    ultimo = min(ultimo_domingo(hasta), primer_domingo_desde(fin)) if fin is not None else ultimo_domingo(hasta)
    return list(pd.date_range(primer_domingo_desde(inicio), ultimo, freq="7D")) if ultimo >= inicio else []


def nombre_corte(c: Cohorte, corte) -> str:
    corte = pd.Timestamp(corte)
    return f"{c.titulo} · Corte S{c.semana(corte)} · domingo {corte:%d-%m-%Y} 11.59 p. m."


# ------------------------------------------------------------------ configuración y Drive
def carpeta_cortes() -> str:
    env = os.getenv("DB_FORMACION_CARPETA_CORTES", "").strip()
    if env:
        return env
    try:
        import streamlit as st
        return str(st.secrets.get("db_formacion", {}).get("carpeta_cortes", "")).strip()
    except Exception:  # noqa: BLE001
        return ""


def conexiones():
    """(gspread client, sesión HTTP autorizada para Drive/Sheets) con la cuenta de servicio de la app."""
    import gspread
    from google.auth.transport.requests import AuthorizedSession
    from tcf10 import data
    cred = data._credenciales(ALCANCES)
    return gspread.authorize(cred), AuthorizedSession(cred)


def _ok(r):
    if r.status_code >= 400:
        detalle = r.text[:300]
        if r.status_code in (403, 404):
            detalle += (" · Revisa que la carpeta de cortes esté en una unidad compartida y que la cuenta de servicio "
                        "sea «Administrador de contenido» de esa unidad.")
        raise RuntimeError(f"Drive {r.status_code}: {detalle}")
    return r.json() if r.text else {}


def existentes(sesion, carpeta: str) -> dict[tuple[str, str], dict]:
    """Cortes ya generados en la carpeta: {(id del archivo original, AAAA-MM-DD): {id, name, webViewLink}}."""
    q = (f"'{carpeta}' in parents and trashed = false and "
         f"appProperties has {{ key='tcf10_tipo' and value='{TIPO}' }}")
    out, token = {}, None
    while True:
        params = {"q": q, "fields": "nextPageToken,files(id,name,webViewLink,createdTime,appProperties)",
                  "pageSize": 200, "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
                  "corpora": "allDrives"}
        if token:
            params["pageToken"] = token
        r = _ok(sesion.get(DRIVE, params=params, timeout=60))
        for f in r.get("files", []):
            p = f.get("appProperties", {})
            out[(p.get("tcf10_origen", ""), p.get("tcf10_corte", ""))] = f
        token = r.get("nextPageToken")
        if not token:
            return out


def _copiar(sesion, sheet_id: str, carpeta: str, nombre: str, props: dict, descripcion: str) -> dict:
    r = sesion.post(f"{DRIVE}/{sheet_id}/copy", params={"supportsAllDrives": "true", "fields": "id,name,webViewLink"},
                    json={"name": nombre, "parents": [carpeta], "appProperties": props, "description": descripcion},
                    timeout=120)
    return _ok(r)


def _papelera(sesion, file_id: str) -> None:
    _ok(sesion.patch(f"{DRIVE}/{file_id}", params={"supportsAllDrives": "true"}, json={"trashed": True}, timeout=60))


# ------------------------------------------------------------------ congelar la copia
def _fijar_hoy(formula: str, corte: pd.Timestamp) -> str:
    fecha = f"DATE({corte.year},{corte.month},{corte.day})"
    return _AHORA_RE.sub(f"({fecha}+TIME(23,59,0))", _HOY_RE.sub(fecha, formula))


def fijar_hoy_y_congelar(libro, corte: pd.Timestamp) -> list[str]:
    """Cambia HOY()/AHORA() por la fecha del corte y deja TODAS las pestañas en valores (con su formato).
    Devuelve avisos (p. ej. pestañas con IMPORTRANGE, que en una copia pueden salir #REF!)."""
    from gspread.utils import ValueRenderOption, rowcol_to_a1
    avisos, cambios = [], []
    for ws in libro.worksheets():
        formulas = ws.get_all_values(value_render_option=ValueRenderOption.formula)
        importrange = False
        for i, fila in enumerate(formulas):
            for j, v in enumerate(fila):
                if isinstance(v, str) and v.startswith("="):
                    importrange |= "IMPORTRANGE(" in v.upper()
                    nueva = _fijar_hoy(v, corte)
                    if nueva != v:
                        cambios.append({"range": f"'{ws.title}'!{rowcol_to_a1(i + 1, j + 1)}", "values": [[nueva]]})
        if importrange:
            avisos.append(f"«{ws.title}» usa IMPORTRANGE: en la copia puede quedar #REF! (revísala).")
    for k in range(0, len(cambios), 2000):
        libro.values_batch_update({"valueInputOption": "USER_ENTERED", "data": cambios[k:k + 2000]})
    # Pegar como valores sobre sí misma: conserva formatos, colores y anchos; quita las fórmulas.
    libro.batch_update({"requests": [{"copyPaste": {"source": {"sheetId": ws.id}, "destination": {"sheetId": ws.id},
                                                    "pasteType": "PASTE_VALUES"}} for ws in libro.worksheets()]})
    return avisos


# ------------------------------------------------------------------ generar
def cohortes(gc, hasta, log=print) -> list[Cohorte]:
    """Calendario y domingos de corte de cada archivo de cohorte, con los datos vigentes del tablero."""
    vivo = D.datos_app()
    out = []
    for sid in D.ids_archivos():
        libro = gc.open_by_key(sid)
        hu = D.documentos(D.hoja_seguimiento(libro))
        sub = vivo.loc[vivo.index.intersection(hu)]
        sub = sub[sub["en_sis"]]
        inicio, fin = calendario(sub["inicio"], sub["fin"])
        c = Cohorte(sid, libro.title, inicio, fin, int(len(hu)))
        c.domingos = domingos(inicio, fin, hasta)
        log(f"{c.titulo}: inicio {inicio:%d/%m/%Y} · cierre {c.cierre:%d/%m/%Y} · {len(c.domingos)} domingo(s) "
            "cumplidos" if inicio is not None else f"{c.titulo}: sin fechas de grupo, no hay cortes que generar")
        out.append(c)
    return out


def generar_uno(gc, sesion, c: Cohorte, corte: pd.Timestamp, app: pd.DataFrame, carpeta: str, log=print) -> dict:
    marca = pd.Timestamp.now(tz="America/Bogota").strftime("%Y-%m-%d %H:%M")
    nombre = nombre_corte(c, corte)
    props = {"tcf10_tipo": TIPO, "tcf10_origen": c.sheet_id, "tcf10_corte": f"{corte:%Y-%m-%d}"}
    copia = _copiar(sesion, c.sheet_id, carpeta, nombre, props,
                    f"Corte al domingo {corte:%d/%m/%Y} 11:59 p. m. (semana {c.semana(corte)}), reconstruido el "
                    f"{marca} con los datos del tablero TCF10. Archivo congelado en valores: no se actualiza.")
    try:
        libro = gc.open_by_key(copia["id"])
        res = D.escribir_seguimiento(D.hoja_seguimiento(libro), app, corte)
        D._control(libro, res.pop("_sin_cruce"), corte,
                   titulo=f"Corte al domingo {corte:%d/%m/%Y} 11:59 p. m. · semana {res['semana']} · generado {marca}")
        avisos = fijar_hoy_y_congelar(libro, corte)
    except Exception:
        _papelera(sesion, copia["id"])  # nunca dejar una copia a medias: la próxima corrida la vuelve a intentar
        raise
    for a in avisos:
        log(f"  AVISO {a}")
    log(f"  ✔ {nombre}: {res['personas']} personas, {res['sin_cruce']} sin cruce · {copia.get('webViewLink', '')}")
    return {"archivo": c.titulo, "corte": f"{corte:%Y-%m-%d}", "estado": "generado", "url": copia.get("webViewLink"),
            "semana": res["semana"], "sin_cruce": res["sin_cruce"], "avisos": avisos}


def generar(fecha=None, forzar: bool = False, solo: list[str] | None = None, hasta=None, log=print) -> list[dict]:
    """Genera los cortes que falten (o solo el domingo `fecha`). forzar=True reemplaza el corte si ya existía.
    solo: IDs de archivo de cohorte a procesar (por defecto, todos)."""
    from tcf10.ui import hoy_real
    carpeta = carpeta_cortes()
    if not carpeta:
        raise RuntimeError("Falta la carpeta de cortes: agrega [db_formacion] carpeta_cortes = \"<ID>\" en los Secrets "
                           "(o la variable DB_FORMACION_CARPETA_CORTES).")
    hasta = pd.Timestamp(hasta) if hasta is not None else hoy_real()
    gc, sesion = conexiones()
    hechos = existentes(sesion, carpeta)
    pendientes: dict[pd.Timestamp, list[Cohorte]] = {}
    resultados = []
    for c in cohortes(gc, hasta, log):
        if solo and c.sheet_id not in solo:
            continue
        fechas = c.domingos
        if fecha is not None:
            f = ultimo_domingo(fecha)
            if f not in fechas:
                resultados.append({"archivo": c.titulo, "corte": f"{f:%Y-%m-%d}", "estado": "fuera de la cohorte"})
                continue
            fechas = [f]
        for f in fechas:
            previo = hechos.get((c.sheet_id, f"{f:%Y-%m-%d}"))
            if previo and not forzar:
                resultados.append({"archivo": c.titulo, "corte": f"{f:%Y-%m-%d}", "estado": "ya existía",
                                   "url": previo.get("webViewLink")})
                continue
            pendientes.setdefault(f, []).append(c)
    for f in sorted(pendientes):
        log(f"Corte domingo {f:%d/%m/%Y}: reconstruyendo datos del tablero hasta ese día…")
        try:
            app = D.datos_app(f, al_corte=True)
        except Exception as e:  # noqa: BLE001
            resultados += [{"archivo": c.titulo, "corte": f"{f:%Y-%m-%d}", "error": f"{type(e).__name__}: {e}"}
                           for c in pendientes[f]]
            continue
        for c in pendientes[f]:
            previo = hechos.get((c.sheet_id, f"{f:%Y-%m-%d}"))
            try:
                r = generar_uno(gc, sesion, c, f, app, carpeta, log)
                if previo:  # forzar: la copia nueva ya quedó; la anterior va a la papelera
                    _papelera(sesion, previo["id"])
                    r["estado"] = "reemplazado"
                resultados.append(r)
            except Exception as e:  # noqa: BLE001 -- un corte con problemas no detiene los demás
                msg = f"{type(e).__name__}: {str(e)[:400]}"
                log(f"  ERROR {c.titulo} · {f:%d/%m/%Y}: {msg}")
                resultados.append({"archivo": c.titulo, "corte": f"{f:%Y-%m-%d}", "error": msg})
    return resultados


def estado(hasta=None, log=lambda *_: None) -> tuple[list[Cohorte], dict]:
    """Para la página: cohortes con sus domingos y los cortes ya generados en la carpeta."""
    from tcf10.ui import hoy_real
    gc, sesion = conexiones()
    carpeta = carpeta_cortes()
    return cohortes(gc, pd.Timestamp(hasta) if hasta is not None else hoy_real(), log), \
        (existentes(sesion, carpeta) if carpeta else {})
