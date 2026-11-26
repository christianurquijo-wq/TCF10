"""Tablas para el Looker Studio de Atenea («Seguimiento de asistencia TCF-10»), calculadas con el MISMO código de la
vista Atenea del Streamlit (tcf10.data + tcf10.metrics). Así el Looker y la app muestran las mismas cifras: el Looker
solo suma y filtra, no recalcula.

Pestañas que escribe en el Google Sheet [looker] sheet_id (o variable LOOKER_SHEET_ID):
  personas          una fila por persona de la base de Formalización (mismo universo de la app): identidad, cohorte,
                    programa, nivel, grupo, franja, estado (5 estados por ICP + estado final), ICP, sesiones,
                    horas sincrónicas / asincrónicas / completadas, avances a 63 h y 90 h y caracterización
                    (sin discapacidad: es dato sensible y va solo agregado en «discapacidad»).
  grupos            una fila por grupo: participantes por estado, horas y asistencia (sumas para promediar bien).
  asistencia        una fila por grupo × sesión: asistieron, no asistieron y sin registro (las de las últimas 24 h
                    sin marcar no cuentan como «sin registro», igual que la app).
  actividades       recursos y lecciones completados por día × grupo × curso × lección (= horas asincrónicas).
  cursos            avance por grupo × curso de la plataforma (completado / en progreso / sin iniciar).
  discapacidad      conteos por cohorte × programa × formalizado × discapacidad × tipo (sin nombres ni grupos).
  historico         foto diaria por grupo × estado (se acumula: una vez por día, la última corrida del día manda).
  actualizacion     fecha de corte, hora de actualización y filas por pestaña.

Lo corre scripts/actualizar_db_formacion.py (cron L-S 7:05 a. m. y botón del panel) después de la DB Formación.
"""
from __future__ import annotations

import os
import re
import unicodedata

import numpy as np
import pandas as pd

from tcf10 import config as C

FILAS_LOTE = 10_000
EXTRAS_FORMALIZACION = {  # columna interna -> encabezado en «Formalización TCF10»
    "localidad": "SDIS_LOCALIDAD", "zona": "SDIS_ZONA", "estado_civil": "SDIS_ESTADO_CIVIL",
    "tiene_hijos": "SDIS_TIENE_HIJOS", "rol_cuidado": "SDIS_CUIDADOR/A", "estudia": "SDIS_ESTUDIA_ACTUALMENTE",
    "trabaja": "SDIS_TRABAJANDO", "fecha_nacimiento": "SDIS_FEC_NACIMIENTO",
    "medio_internet": "SDIS_MEDIO_CONEXION_INTERNET", "dispositivo_internet": "SDIS_DISPOSITIVO_INTERNET",
}


def _plano(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


SHEET_ID_DEFECTO = "1UtoFKBu_4M63myDcd6MeZA1BZbPuwN8i1hQ7kYrclCU"  # «TCF10 · Datos Looker Atenea»


def sheet_id() -> str:
    env = os.getenv("LOOKER_SHEET_ID", "").strip()
    if env:
        return env
    try:
        import streamlit as st
        return str(st.secrets.get("looker", {}).get("sheet_id", "")).strip() or SHEET_ID_DEFECTO
    except Exception:  # noqa: BLE001
        return SHEET_ID_DEFECTO


def tipo_estado(e: str) -> str:
    if e in C.EN_CURSO:
        return "En curso"
    if e in C.ESTADOS_FINALES:
        return "Estado final"
    return e or C.SIN_INFO


def rango_edad(edad) -> str:
    if edad is None or pd.isna(edad):
        return C.SIN_INFO
    edad = int(edad)
    if edad < 18:
        return "Menor de 18"
    if edad <= 24:
        return "18 a 24"
    if edad <= 29:
        return "25 a 29"
    return "30 o más"


def _texto(s: pd.Series) -> pd.Series:
    t = s.astype("string").fillna("").str.strip()
    return t.where(t.ne(""), C.SIN_INFO)


def _valor(v) -> str:
    """Respuesta homogénea: «2. NO» → «NO», «1. SI» → «SI», vacío / «SIN INFORMACION» → «Sin información»."""
    t = re.sub(r"^\s*\d+\s*[.)]\s*", "", str(v if v is not None else "")).strip().upper()
    t = " ".join(t.split())
    if not t or _plano(t) in ("sin informacion", "nan", "none", "na", "n a"):
        return C.SIN_INFO
    return {"SÍ": "SI"}.get(t, t)


def caracterizacion_extra(crudo: pd.DataFrame, hoy: pd.Timestamp) -> pd.DataFrame:
    """Campos de caracterización de la base de Formalización que la app no muestra (localidad, edad, zona…), por
    huella del documento. Mismo universo y misma base que la app."""
    from tcf10 import base_atenea as B
    por_plano = {_plano(c): c for c in crudo.columns}
    out = pd.DataFrame({"huella": B.huella(crudo[por_plano[_plano("NUMERO_DOCUMENTO")]])})
    for interna, encabezado in EXTRAS_FORMALIZACION.items():
        col = por_plano.get(_plano(encabezado))
        out[interna] = crudo[col].values if col else ""
    nac = pd.to_datetime(out["fecha_nacimiento"].astype(str).str.strip(), errors="coerce", dayfirst=True)
    serial = pd.to_numeric(out["fecha_nacimiento"], errors="coerce")
    serial = serial.where(serial.between(3000, 60000))  # serial de Sheets/Excel (1908-2064); lo demás no es fecha
    nac = nac.fillna(pd.to_datetime("1899-12-30") + pd.to_timedelta(serial, unit="D"))
    edad = ((pd.Timestamp(hoy) - nac).dt.days // 365.25)
    out["edad"] = edad.where(edad.between(10, 100))
    out["rango_edad"] = out["edad"].map(rango_edad)
    for c in EXTRAS_FORMALIZACION:
        if c != "fecha_nacimiento":
            out[c] = out[c].map(_valor)
    return out.drop(columns=["fecha_nacimiento"]).dropna(subset=["huella"]).drop_duplicates("huella")


def tablas(hoy: pd.Timestamp | None = None, permitir_demo: bool = False) -> dict[str, pd.DataFrame]:
    """Todas las pestañas para el Looker, con las cifras de la vista Atenea a la fecha `hoy` (por defecto, hoy)."""
    from tcf10 import data, metrics, sis_sheet
    from tcf10.ui import hoy_real
    hoy = pd.Timestamp(hoy or hoy_real()).normalize()
    corte = hoy if hoy < hoy_real() else None  # fecha pasada: se reconstruye a ese día, como el filtro de la app
    benef, avance, cohortes, demo = data.cargar(corte)
    df = metrics.preparar(benef, avance, cohortes, hoy)
    if (demo or "huella" not in df) and not permitir_demo:
        raise RuntimeError("La app está en modo demostración: no hay datos reales para el Looker.")
    df["estado"] = df["riesgo"]  # mismo estado de la vista Atenea (comun.estado)

    # ---------------- personas
    ident = data.identidades()
    # Igual que la app (comun.con_identidad): si la base ya trae alguna de estas columnas, el merge las renombraría
    # a documento_x / documento_y y la columna «documento» quedaría vacía.
    df = df.drop(columns=[c for c in ("nombre_completo", "tipo_documento", "documento") if c in df])
    if demo:  # pruebas con datos sintéticos: sin base cruda ni huella
        p = df.merge(ident, on="id_sis", how="left")
    else:
        extra = caracterizacion_extra(data._formalizacion_cruda(), hoy)
        p = (df.merge(ident.drop(columns=[c for c in ("id_sis",) if c in ident]), on="huella", how="left")
               .merge(extra, on="huella", how="left"))
    reg = pd.to_numeric(p["sesiones_registradas"], errors="coerce").fillna(0)
    asis = pd.to_numeric(p["sesiones_asistidas"], errors="coerce").fillna(0)
    personas = pd.DataFrame({
        "id_sis": pd.to_numeric(p["id_sis"], errors="coerce").where(lambda s: s > 0),
        "documento": p.get("documento"), "tipo_documento": p.get("tipo_documento"),
        "nombre": p.get("nombre_completo"),
        "cohorte": p["cohorte"], "programa": p["perfil"], "nivel": p["nivel"], "grupo": p["grupo"],
        "franja": p.get("franja", C.SIN_INFO),
        "formalizado": np.where(p["enrolado"], "Sí", "No"),
        "personas": 1, "formalizados": p["enrolado"].astype(int),
        "estado": p["estado"], "tipo_estado": p["estado"].map(tipo_estado),
        "orden_estado": p["estado"].map({e: i + 1 for i, e in enumerate(C.ORDEN_ESTADOS)}),
        "icp": pd.to_numeric(p["pct_esperado"], errors="coerce").round(4),
        "sesiones_asistidas": asis.astype(int), "sesiones_registradas": reg.astype(int),
        "pct_asistencia": (asis / reg.where(reg > 0)).round(4),
        "horas_sincronico": p["horas_sinc_val"].round(2), "horas_asincronico": p["horas_asinc_val"].round(2),
        "horas_completadas": p["horas_validas"].round(2),
        "avance_63h": (p["horas_validas"] / C.HORAS_CULMINACION).clip(upper=1).round(4),
        "avance_90h": (p["horas_validas"] / C.HORAS_TOTALES).clip(upper=1).round(4),
        "aprobo_63h": np.where(p["horas_validas"] >= C.HORAS_CULMINACION, "Sí", "No"),
        "ultima_actividad": pd.to_datetime(p.get("ultima_actividad"), errors="coerce").dt.strftime("%Y-%m-%d"),
        "sexo": p.get("sexo"), "estrato": p.get("estrato"), "nivel_educativo": p.get("nivel_educativo"),
        **{c: p.get(c) for c in ("edad", "rango_edad", "localidad", "zona", "estado_civil", "tiene_hijos",
                                 "rol_cuidado", "estudia", "trabaja", "medio_internet", "dispositivo_internet")},
    })
    personas = personas.sort_values(["cohorte", "grupo", "nombre"], na_position="last").reset_index(drop=True)

    # ---------------- grupos (sumas, para que el Looker promedie bien con SUM(x)/SUM(y))
    g = df.assign(_asis=asis.values, _reg=reg.values)
    grupos = (g.groupby(["cohorte", "perfil", "nivel", "grupo"], dropna=False)
               .agg(franja=("franja", "first") if "franja" in g else ("grupo", "first"),
                    personas=("id_sis", "size"), formalizados=("enrolado", "sum"),
                    horas_completadas_suma=("horas_validas", "sum"), horas_sinc_suma=("horas_sinc_val", "sum"),
                    horas_asinc_suma=("horas_asinc_val", "sum"), sesiones_asistidas=("_asis", "sum"),
                    sesiones_registradas=("_reg", "sum"))
               .reset_index().rename(columns={"perfil": "programa"}))
    conteo = pd.crosstab(g["grupo"], g["estado"]).reindex(columns=C.ORDEN_ESTADOS, fill_value=0)
    grupos = grupos.merge(conteo, left_on="grupo", right_index=True, how="left")
    grupos["horas_promedio"] = (grupos["horas_completadas_suma"] / grupos["personas"]).round(2)
    grupos["pct_asistencia"] = (grupos["sesiones_asistidas"]
                                / grupos["sesiones_registradas"].where(grupos["sesiones_registradas"] > 0)).round(4)

    # ---------------- asistencia por sesión (mismo cálculo de la página Asistencia)
    ids = tuple(sorted(int(x) for x in df["id_sis"].dropna().unique() if int(x) > 0))
    a, prog = data.agregados(ids, corte)
    a = a[a["grupo"].isin(set(df["grupo"]))].copy()
    from datetime import datetime
    from tcf10.ui import TZ
    limite = (min(pd.Timestamp(datetime.now(TZ).replace(tzinfo=None)), hoy + pd.Timedelta(days=1))
              - pd.Timedelta(hours=C.REGISTRO_GRACIA_HORAS)).normalize()
    a.loc[pd.to_datetime(a["fecha"]) >= limite, "sin_registro"] = 0
    info = df.drop_duplicates("grupo").set_index("grupo")
    asistencia = pd.DataFrame({
        "fecha": pd.to_datetime(a["fecha"]).dt.strftime("%Y-%m-%d"), "grupo": a["grupo"],
        "cohorte": a["grupo"].map(info["cohorte"]), "programa": a["grupo"].map(info["perfil"]),
        "nivel": a["grupo"].map(info["nivel"]),
        "franja": a["grupo"].map(info["franja"]) if "franja" in info else C.SIN_INFO,
        "sesion": a["sesion"], "session_id": a["session_id"], "convocados": a["convocados"],
        "asistieron": a["asistieron"].astype(int), "no_asistieron": a["no_asistieron"].astype(int),
        "sin_registro": a["sin_registro"].astype(int)})
    asistencia["registradas"] = asistencia["asistieron"] + asistencia["no_asistieron"]
    asistencia = asistencia.sort_values(["fecha", "grupo"]).reset_index(drop=True)

    # ---------------- cursos (avance en la plataforma por grupo × curso)
    prog = prog[prog["grupo"].isin(set(df["grupo"]))].copy()
    cursos = pd.DataFrame({"grupo": prog["grupo"], "cohorte": prog["grupo"].map(info["cohorte"]),
                           "programa": prog["grupo"].map(info["perfil"]), "nivel": prog["grupo"].map(info["nivel"]),
                           "curso": prog["curso"], "inscritos": prog["estudiantes"],
                           "completado": prog["completado"], "en_progreso": prog["en_progreso"],
                           "sin_iniciar": prog["sin_iniciar"],
                           "avance_promedio": prog["avance_promedio"].round(4),
                           "pct_lecciones": prog["pct_lecciones"].round(4)})

    # ---------------- actividades completadas (recursos = horas asincrónicas; lecciones)
    d = (pd.DataFrame(columns=["id_sis", "completed_date", "course_name", "lesson_name"]) if demo
         else data._sis_sheet(data._esquema_sis())["prog_det"])
    d = d[d["id_sis"].isin(set(ids))].copy()
    if corte is not None:
        d = d[d["completed_date"].isna() | (pd.to_datetime(d["completed_date"]).dt.normalize() <= corte)]
    if "is_completed" in d:
        d = d[d["is_completed"] | d["completed_date"].notna()]
    grupo_de = df.dropna(subset=["id_sis"]).drop_duplicates("id_sis").set_index("id_sis")["grupo"]
    d["grupo"] = d["id_sis"].map(grupo_de)
    d["categoria"] = (d["component_category"].astype(str).str.strip().str.lower()
                      if "component_category" in d else "lesson")
    d["horas"] = (d[sis_sheet.COL_PEDAGOGICO] / sis_sheet.SEGUNDOS_POR_HORA
                  if sis_sheet.COL_PEDAGOGICO in d else 0.0)
    d.loc[d["categoria"].ne("resource"), "horas"] = 0.0  # solo los recursos suman horas asincrónicas
    d["fecha"] = pd.to_datetime(d["completed_date"]).dt.strftime("%Y-%m-%d")
    act = (d.groupby(["fecha", "grupo", "course_name", "lesson_name", "categoria"], dropna=False)
             .agg(completados=("id_sis", "size"), personas=("id_sis", "nunique"), horas=("horas", "sum"))
             .reset_index().rename(columns={"course_name": "curso", "lesson_name": "leccion"}))
    act["categoria"] = act["categoria"].map({"resource": "Recurso", "lesson": "Lección"}).fillna(act["categoria"])
    act["cohorte"] = act["grupo"].map(info["cohorte"])
    act["programa"] = act["grupo"].map(info["perfil"])
    act["horas"] = act["horas"].round(3)
    actividades = act[["fecha", "cohorte", "programa", "grupo", "curso", "leccion", "categoria", "completados",
                       "personas", "horas"]].sort_values(["fecha", "grupo"], na_position="first")

    # ---------------- discapacidad (solo agregado)
    disc = df.assign(discapacidad=df["discapacidad"] if "discapacidad" in df else C.SIN_INFO,
                     tipo=df["tipo_discapacidad"] if "tipo_discapacidad" in df else C.SIN_INFO,
                     formalizado=np.where(df["enrolado"], "Sí", "No"))
    discapacidad = (disc.groupby(["cohorte", "perfil", "formalizado", "discapacidad", "tipo"], dropna=False).size()
                        .rename("personas").reset_index().rename(columns={"perfil": "programa",
                                                                          "tipo": "tipo_discapacidad"}))

    # ---------------- foto del día por grupo × estado
    historico = (g.groupby(["cohorte", "perfil", "nivel", "grupo", "estado"], dropna=False)
                  .agg(personas=("id_sis", "size"), horas_completadas_suma=("horas_validas", "sum"),
                       horas_sinc_suma=("horas_sinc_val", "sum"), horas_asinc_suma=("horas_asinc_val", "sum"),
                       sesiones_asistidas=("_asis", "sum"), sesiones_registradas=("_reg", "sum"))
                  .reset_index().rename(columns={"perfil": "programa"}))
    historico.insert(0, "fecha_foto", hoy.strftime("%Y-%m-%d"))
    historico["tipo_estado"] = historico["estado"].map(tipo_estado)

    return {"personas": personas, "grupos": grupos, "asistencia": asistencia, "actividades": actividades,
            "cursos": cursos, "discapacidad": discapacidad, "historico": historico}


# ------------------------------------------------------------------ escritura en el Sheet
def _celda(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA or v is pd.NaT:
        return ""
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return int(v) if float(v).is_integer() else round(float(v), 6)
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    return str(v)


def _escribir(libro, nombre: str, df: pd.DataFrame, log) -> None:
    import gspread
    filas = [list(map(str, df.columns))] + [[_celda(v) for v in f] for f in df.itertuples(index=False)]
    try:
        ws = libro.worksheet(nombre)
    except gspread.exceptions.WorksheetNotFound:
        ws = libro.add_worksheet(nombre, rows=len(filas) + 10, cols=max(len(df.columns), 1))
    if ws.row_count < len(filas) + 1 or ws.col_count < len(df.columns):
        ws.resize(rows=max(ws.row_count, len(filas) + 10), cols=max(ws.col_count, len(df.columns)))
    ws.clear()
    for i in range(0, len(filas), FILAS_LOTE):
        ws.update(range_name=f"A{i + 1}", values=filas[i:i + FILAS_LOTE], value_input_option="RAW")
    log(f"  {nombre}: {len(df)} filas")


def _historico(libro, foto: pd.DataFrame) -> pd.DataFrame:
    """Histórico acumulado: lo anterior (sin la fecha de hoy) + la foto de hoy."""
    import gspread
    try:
        previo = pd.DataFrame(libro.worksheet("historico").get_all_records())
    except gspread.exceptions.WorksheetNotFound:
        previo = pd.DataFrame()
    if len(previo) and "fecha_foto" in previo:
        previo = previo[previo["fecha_foto"].astype(str) != str(foto["fecha_foto"].iloc[0])]
        previo = previo.reindex(columns=foto.columns)
        return pd.concat([previo, foto], ignore_index=True)
    return foto


def actualizar(hoy: pd.Timestamp | None = None, log=print) -> dict:
    import gspread
    from tcf10 import data
    sid = sheet_id()
    if not sid:
        raise RuntimeError("Falta [looker] sheet_id en los Secrets (o LOOKER_SHEET_ID): el Sheet que lee el Looker.")
    tabs = tablas(hoy)
    gc = gspread.authorize(data._credenciales(["https://www.googleapis.com/auth/spreadsheets"]))
    try:
        libro = gc.open_by_key(sid)
    except gspread.exceptions.APIError as e:
        raise RuntimeError(f"No se pudo abrir el Sheet del Looker ({e.response.status_code}). Compártelo como Editor "
                           "con la cuenta de servicio de la app.") from e
    tabs["historico"] = _historico(libro, tabs["historico"])
    for nombre, df in tabs.items():
        _escribir(libro, nombre, df, log)
    marca = pd.Timestamp.now(tz="America/Bogota")
    resumen = pd.DataFrame({"campo": ["actualizado", "fecha_corte", "fuente"] + [f"filas_{k}" for k in tabs],
                            "valor": [marca.strftime("%Y-%m-%d %H:%M"), tabs["historico"]["fecha_foto"].iloc[-1],
                                      "Streamlit TCF10 · vista Atenea (tcf10.data + tcf10.metrics)"]
                                     + [len(v) for v in tabs.values()]})
    _escribir(libro, "actualizacion", resumen, log)
    return {"archivo": libro.title, **{k: len(v) for k, v in tabs.items()}}
