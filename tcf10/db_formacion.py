"""Actualiza la «DB Formación TCF10» de cada cohorte (pestaña «Seg.Formación TCF10 C1/C2») con los datos de la app.

Columnas que escribe (el resto del archivo —fórmulas de ICP y ESTADO_ESTUDIANTE, abandono, constancias— no se toca):
    GRUPO DE FORMACIÓN · FECHA_INICIO_FORMACIÓN · FECHA_FIN_FORMACIÓN      ← grupo y calendario del grupo (SIS / Asignación)
    SÍNCRONO (35%) · ASÍNCRONO (65%)                                       ← horas completadas de cada modalidad
                                                                              (cada una hasta su tope: 31,5 h y 58,5 h)
    PORCENTAJE_AVANCE_FORMACIÓN                                            ← horas completadas ÷ 90 h (0-100 %)
    N3 (SEMANA)                                                            ← semana actual de la cohorte (1-8)

Son exactamente las cifras del tablero (mismo cálculo: tcf10.data + tcf10.metrics), cruzadas por NUMERO_DOCUMENTO.
Quien no cruza con el SIS queda con grupo y fechas vacíos y 0 h / 0 %, y se lista en la pestaña «Control
actualización».

Fuentes de los IDs: [db_formacion] ids = ["…", "…"] en los Secrets (o la variable DB_FORMACION_IDS separada por
comas). La cuenta de servicio [gcp_service_account] debe ser EDITOR de cada archivo.

Se usa desde scripts/actualizar_db_formacion.py (GitHub Actions / panel de operaciones) y desde el botón de la
vista interna («Bases de formación»).
"""
from __future__ import annotations

import os
import unicodedata

import pandas as pd

from tcf10 import config as C

IDS_DEFECTO = ["1VwnTf11X3ji39iWjCL9U-5iIrS5rGpoL_Fmfsa05VEA", "1zzKjwqQ_KpJVWKD6QUmWTQ9b2VKHpyAmQ0FlcC3m5VI"]
PESTANA_CONTROL = "Control actualización"
COLUMNAS = {  # clave interna -> encabezado en la fila de títulos (comparado sin tildes, espacios ni saltos)
    "documento": "NUMERO_DOCUMENTO",
    "grupo": "GRUPO DE FORMACIÓN",
    "inicio": "FECHA_INICIO_FORMACIÓN",
    "fin": "FECHA_FIN_FORMACIÓN",
    "sinc": "SÍNCRONO (35%)",
    "asinc": "ASÍNCRONO (65%)",
    "pct": "PORCENTAJE_AVANCE_FORMACIÓN",
}
ESCRIBE = ["grupo", "inicio", "fin", "sinc", "asinc", "pct"]


def _plano(t) -> str:
    t = "".join(c for c in unicodedata.normalize("NFKD", str(t or "")) if not unicodedata.combining(c))
    return "".join(t.upper().split())


def ids_archivos() -> list[str]:
    env = os.getenv("DB_FORMACION_IDS", "").strip()
    if env:
        return [x.strip() for x in env.split(",") if x.strip()]
    try:
        import streamlit as st
        ids = list(st.secrets.get("db_formacion", {}).get("ids", []))
        if ids:
            return ids
    except Exception:  # noqa: BLE001
        pass
    return list(IDS_DEFECTO)


def datos_app(hoy: pd.Timestamp | None = None, al_corte: bool = False) -> pd.DataFrame:
    """Una fila por persona con huella del documento, grupo, fechas del grupo y horas completadas (como el tablero).
    al_corte=True: horas, asistencia y retiros reconstruidos hasta el día `hoy` incluido (cortes semanales)."""
    from tcf10 import data, metrics
    from tcf10.ui import hoy_real
    hoy = hoy or hoy_real()
    benef, avance, cohortes, _ = data.cargar(hoy if al_corte else None)
    df = metrics.preparar(benef, avance, cohortes, hoy)
    if "huella" not in df:
        raise RuntimeError("La app está en modo demostración o sin la base de Formalización: no hay documentos para "
                           "cruzar. Revisa [tcf10] sheet_id y [gcp_service_account] en los Secrets.")
    out = pd.DataFrame({
        "huella": df["huella"],
        "grupo": df["grupo"].where(df["grupo"].astype(str).ne("Sin dato"), None),
        "inicio": pd.to_datetime(df.get("fi_grupo"), errors="coerce"),
        "fin": pd.to_datetime(df.get("ff_grupo"), errors="coerce"),
        "sinc": df["horas_sinc_val"].astype(float),
        "asinc": df["horas_asinc_val"].astype(float),
        "en_sis": df.get("en_sis", pd.Series(True, index=df.index)).astype(bool),
    })
    out["pct"] = ((out["sinc"] + out["asinc"]) / C.HORAS_TOTALES).clip(0, 1)
    return out.dropna(subset=["huella"]).drop_duplicates("huella").set_index("huella")


def semana_cohorte(inicios: pd.Series, hoy: pd.Timestamp) -> int:
    """Semana (1-8) de la cohorte: desde el inicio más frecuente de sus grupos (la moda evita que un grupo tardío o
    adelantado mueva toda la hoja)."""
    s = pd.to_datetime(inicios, errors="coerce").dropna().dt.normalize()
    if s.empty:
        return 1
    inicio = s.mode().iloc[0]
    dias = (pd.Timestamp(hoy).normalize() - inicio).days
    return int(min(C.SEMANAS_PLAN, max(1, dias // 7 + 1)))


def _fila_titulos(valores: list[list[str]]) -> int:
    for i, fila in enumerate(valores[:20]):
        if _plano(COLUMNAS["documento"]) in {_plano(c) for c in fila}:
            return i
    raise ValueError("No encontré la fila de títulos (columna NUMERO_DOCUMENTO).")


def hoja_seguimiento(libro):
    ws = next((w for w in libro.worksheets() if _plano(w.title).startswith(_plano("Seg.Formación"))), None)
    if ws is None:
        raise ValueError(f"{libro.title}: no tiene una pestaña «Seg.Formación…».")
    return ws


def documentos(ws) -> pd.Series:
    """Huellas de los documentos de la pestaña Seg.Formación (para saber qué personas son de cada cohorte)."""
    from tcf10.base_atenea import huella
    valores = ws.get_all_values()
    t = _fila_titulos(valores)
    j = {_plano(c): k for k, c in enumerate(valores[t])}[_plano(COLUMNAS["documento"])]
    docs = pd.Series([f[j] for f in valores[t + 1:] if j < len(f) and str(f[j]).strip()])
    return huella(docs).dropna()


def actualizar_libro(gc, sheet_id: str, app: pd.DataFrame, hoy: pd.Timestamp, log=print) -> dict:
    libro = gc.open_by_key(sheet_id)
    ws = hoja_seguimiento(libro)
    res = escribir_seguimiento(ws, app, hoy)
    sin_cruce = res.pop("_sin_cruce")
    _control(libro, sin_cruce, hoy)
    res = {"archivo": libro.title, **res}
    log(f"{res['archivo']} · {res['pestana']}: {res['personas']} personas, {res['sin_cruce']} sin cruce, "
        f"semana {res['semana']}")
    return res


def escribir_seguimiento(ws, app: pd.DataFrame, hoy: pd.Timestamp) -> dict:
    """Escribe grupo, fechas, horas y % (N:S) y la semana (N3) en la pestaña Seg.Formación `ws`."""
    from gspread.utils import rowcol_to_a1
    from tcf10.base_atenea import huella
    valores = ws.get_all_values()
    t = _fila_titulos(valores)
    titulos = {_plano(c): j for j, c in enumerate(valores[t])}
    col = {k: titulos.get(_plano(v)) for k, v in COLUMNAS.items()}
    faltan = [COLUMNAS[k] for k, j in col.items() if j is None]
    if faltan:
        raise ValueError(f"{libro.title} / {ws.title}: faltan columnas {', '.join(faltan)}.")
    filas = valores[t + 1:]
    docs = pd.Series([f[col["documento"]] if col["documento"] < len(f) else "" for f in filas])
    h = huella(docs)
    datos, sin_cruce, inicios, bloque = [], [], [], []
    for k, (doc, hu) in enumerate(zip(docs, h)):
        fila_hoja = t + 2 + k
        actual = filas[k]
        if not str(doc).strip():  # fila sin documento: se deja como está
            bloque.append([actual[col[c]] if col[c] < len(actual) else "" for c in ESCRIBE])
            continue
        r = app.loc[hu] if isinstance(hu, str) and hu in app.index else None
        if r is None or not bool(r["en_sis"]):
            vals = {"grupo": "", "inicio": "", "fin": "", "sinc": 0, "asinc": 0, "pct": 0}
            sin_cruce.append([str(doc).strip(), "No está en la base del tablero" if r is None else "Sin usuario en el SIS"])
        else:
            if pd.notna(r["inicio"]):
                inicios.append(r["inicio"])
            vals = {"grupo": r["grupo"] or "",
                    "inicio": r["inicio"].strftime("%Y-%m-%d") if pd.notna(r["inicio"]) else "",
                    "fin": r["fin"].strftime("%Y-%m-%d") if pd.notna(r["fin"]) else "",
                    "sinc": round(float(r["sinc"]), 2), "asinc": round(float(r["asinc"]), 2),
                    "pct": round(float(r["pct"]), 4)}
            if not vals["grupo"]:
                sin_cruce.append([str(doc).strip(), "Sin grupo asignado"])
        bloque.append([vals[c] for c in ESCRIBE])
        for c in ESCRIBE:
            datos.append({"range": rowcol_to_a1(fila_hoja, col[c] + 1), "values": [[vals[c]]]})
    semana = semana_cohorte(pd.Series(inicios), hoy)
    indices = [col[c] for c in ESCRIBE]
    if bloque and indices == list(range(indices[0], indices[0] + len(indices))):
        # Columnas contiguas (N:S en ambos archivos): una sola escritura de todo el bloque
        ws.update(range_name=rowcol_to_a1(t + 2, indices[0] + 1), values=bloque, value_input_option="USER_ENTERED")
    else:
        for i in range(0, len(datos), 3000):
            ws.batch_update(datos[i:i + 3000], value_input_option="USER_ENTERED")
    ws.update(range_name="N3", values=[[semana]], value_input_option="USER_ENTERED")
    return {"pestana": ws.title, "personas": int(sum(1 for d in docs if str(d).strip())),
            "sin_cruce": len(sin_cruce), "semana": semana, "_sin_cruce": sin_cruce}


def _control(libro, sin_cruce: list[list[str]], hoy: pd.Timestamp, titulo: str | None = None) -> None:
    import gspread
    try:
        ws = libro.worksheet(PESTANA_CONTROL)
    except gspread.exceptions.WorksheetNotFound:
        ws = libro.add_worksheet(PESTANA_CONTROL, rows=max(100, len(sin_cruce) + 5), cols=3)
    ws.clear()
    marca = pd.Timestamp.now(tz="America/Bogota").strftime("%Y-%m-%d %H:%M")
    titulo = titulo or f"Actualizado {marca}"
    filas = [[f"{titulo} · {len(sin_cruce)} personas sin cruce (grupo y fechas vacíos, 0 h)", "", ""],
             ["NUMERO_DOCUMENTO", "Motivo", ""]] + [r + [""] for r in sin_cruce]
    ws.update(range_name="A1", values=filas, value_input_option="RAW")


def actualizar_todo(hoy: pd.Timestamp | None = None, log=print) -> list[dict]:
    import gspread
    from tcf10 import data
    from tcf10.ui import hoy_real
    hoy = hoy or hoy_real()
    app = datos_app(hoy)
    gc = gspread.authorize(data._credenciales(["https://www.googleapis.com/auth/spreadsheets"]))
    resultados = []
    for sid in ids_archivos():
        try:
            resultados.append(actualizar_libro(gc, sid, app, hoy, log))
        except Exception as e:  # noqa: BLE001 -- un archivo con problemas no detiene el otro
            msg = f"{type(e).__name__}: {str(e)[:300]}"
            if "403" in msg or "PERMISSION" in msg.upper():
                msg += " · Comparte el archivo como Editor con la cuenta de servicio de la app."
            log(f"ERROR {sid}: {msg}")
            resultados.append({"archivo": sid, "error": msg})
    return resultados
