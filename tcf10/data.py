"""
Carga de datos de TCF10.

  beneficiarios + cohortes  Google Sheet operativo (base entregada por Atenea + estado operativo que
                            actualiza el equipo: grupo, docente, gestor, franja, retiros, certificación,
                            situación laboral). Pestañas BENEFICIARIOS y COHORTES.
  avance                    Vistas VTD10 del SIS (DVTD_SIS) en BigQuery (queries/avance_sis.sql), cruzadas
                            por ID SIS = incremental: sincrónicas = sesiones asistidas × horas_por_sesion;
                            asincrónicas = time_view a nivel de curso ÷ divisor_time_view.

Si faltan los secrets ([tcf10] y [gcp_service_account]) la app usa los datos de demostración de
data/demo/ y lo avisa con un banner: sirve para probar sin tocar datos reales.
Los encabezados del Sheet se aceptan sin importar mayúsculas, tildes o espacios.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
DEMO = RAIZ / "data" / "demo"
SQL_AVANCE = RAIZ / "queries" / "avance_sis.sql"

# columna interna -> nombres aceptados en el Sheet
COLUMNAS_BENEF = {
    "id_sis": ["id_sis", "id sis", "codigo sis"],
    "documento": ["documento", "numero documento", "no. documento", "cedula"],
    "nombre": ["nombre", "nombre completo", "nombres y apellidos"],
    "cohorte": ["cohorte"],
    "poblacion": ["poblacion", "tipo poblacion", "convocatoria"],
    "perfil": ["perfil"],
    "nivel": ["nivel"],
    "grupo": ["grupo"],
    "docente": ["docente"],
    "gestor": ["gestor", "gestor de acompanamiento"],
    "franja": ["franja", "franja horaria"],
    "enrolado": ["enrolado", "enrolamiento", "matriculado"],
    "estado": ["estado", "estado formacion"],
    "lab_inicio": ["situacion laboral inicio", "lab_inicio", "estado laboral inicial"],
    "certificado": ["certificado industria", "certificado", "certificacion de industria"],
    "formal_t3": ["formal t3", "formal_t3", "formal en pila t3"],
}
COLUMNAS_COHORTES = {"cohorte": ["cohorte"], "fecha_inicio": ["fecha inicio", "inicio"],
                     "fecha_fin": ["fecha fin", "fin"]}
OBLIGATORIAS = ["id_sis", "cohorte", "poblacion", "perfil", "nivel", "grupo", "docente", "enrolado", "estado"]


def _plano(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("_", " ").split())


def _normalizar(df: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    por_plano = {_plano(c): c for c in df.columns}
    salida = {}
    for interno, alias in mapa.items():
        origen = next((por_plano[_plano(a)] for a in alias if _plano(a) in por_plano), None)
        salida[interno] = df[origen] if origen is not None else pd.Series([None] * len(df), index=df.index)
    return pd.DataFrame(salida)


def _si(serie: pd.Series) -> pd.Series:
    """'SI', 'Sí', 'TRUE', '1', 'X' -> True; vacío -> None (sin dato); el resto -> False."""
    si = {"SI", "SÍ", "TRUE", "1", "X", "VERDADERO"}
    valores = [None if v is None or (not isinstance(v, str) and pd.isna(v)) or str(v).strip() == ""
               else str(v).strip().upper() in si for v in serie.tolist()]
    # dtype object explícito: con pandas 3 + pyarrow una columna toda vacía se volvía Arrow y fillna(False) fallaba
    return pd.Series(valores, index=serie.index, dtype=object)


def limpiar_beneficiarios(crudo: pd.DataFrame) -> pd.DataFrame:
    planos = {_plano(c) for c in crudo.columns}
    faltan = [c for c in OBLIGATORIAS if not any(_plano(a) in planos for a in COLUMNAS_BENEF[c])]
    if faltan:
        raise ErrorConfiguracion(
            "A la pestaña de beneficiarios le faltan columnas obligatorias: "
            + ", ".join(f"«{COLUMNAS_BENEF[c][0]}»" for c in faltan)
            + f". Columnas encontradas: {', '.join(map(str, crudo.columns)) or '(ninguna)'}.")
    df = _normalizar(crudo, COLUMNAS_BENEF)
    df["id_sis"] = pd.to_numeric(df["id_sis"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["id_sis"]).drop_duplicates("id_sis")
    df["enrolado"] = _si(df["enrolado"]).fillna(False).astype(bool)
    df["estado"] = df["estado"].fillna("").astype(str).str.strip().str.capitalize().replace("", "Enrolado")
    df["poblacion"] = df["poblacion"].fillna("").astype(str).str.strip().str.capitalize()
    for c in ("certificado", "formal_t3"):
        df[c] = _si(df[c])
    df["lab_inicio"] = df["lab_inicio"].fillna("").astype(str).str.strip().str.capitalize().replace(
        {"No Formal": "No formal", "Desempleada": "Desempleado"})
    for c in ("cohorte", "perfil", "nivel", "grupo", "docente", "gestor", "franja"):
        df[c] = df[c].fillna("Sin dato").astype(str).str.strip().replace("", "Sin dato")
    return df.reset_index(drop=True)


def limpiar_cohortes(crudo: pd.DataFrame) -> pd.DataFrame:
    df = _normalizar(crudo, COLUMNAS_COHORTES)
    for c in ("fecha_inicio", "fecha_fin"):
        iso = pd.to_datetime(df[c], format="%Y-%m-%d", errors="coerce")
        df[c] = iso.fillna(pd.to_datetime(df[c], dayfirst=True, errors="coerce", format="mixed"))
    return df.dropna(subset=["cohorte"])


def limpiar_avance(crudo: pd.DataFrame) -> pd.DataFrame:
    df = crudo.copy()
    df["id_sis"] = pd.to_numeric(df["id_sis"], errors="coerce").astype("Int64")
    df["ultima_actividad"] = pd.to_datetime(df["ultima_actividad"], errors="coerce")
    df.loc[df["ultima_actividad"].dt.year < 2000, "ultima_actividad"] = pd.NaT  # sin actividad (1970 en el SQL)
    for c in ("horas_sinc", "horas_asinc"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    # columnas opcionales (las trae el SIS real; el demo no)
    for c in ("grupo_sis", "actualizado_sis"):
        if c not in df:
            df[c] = None
    return df[["id_sis", "horas_sinc", "horas_asinc", "ultima_actividad", "grupo_sis", "actualizado_sis"]]


# ------------------------------------------------------------------ fuentes
class ErrorConfiguracion(Exception):
    """Error de datos o de Secrets que la app muestra en pantalla en lugar de un traceback."""


def _cfg() -> dict:
    try:
        return dict(st.secrets.get("tcf10", {}))
    except Exception:  # noqa: BLE001 -- sin secrets.toml
        return {}


def _hay_sa() -> bool:
    try:
        return "gcp_service_account" in st.secrets
    except Exception:  # noqa: BLE001
        return False


def modo() -> str:
    """'demo' sin credenciales · 'sis' con BigQuery pero sin Sheet · 'completo' con Sheet + BigQuery."""
    cfg = _cfg()
    if not (cfg.get("sis_dataset") and _hay_sa()):
        return "demo"
    return "completo" if cfg.get("sheet_id") else "sis"


def modo_demo() -> bool:
    return modo() == "demo"


def _credenciales(scopes: list[str]):
    from google.oauth2.service_account import Credentials
    return Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)


@st.cache_data(ttl=900, show_spinner="Leyendo la base de beneficiarios…")
def _leer_sheet(pestana: str) -> pd.DataFrame:
    import gspread
    gc = gspread.authorize(_credenciales(["https://www.googleapis.com/auth/spreadsheets.readonly"]))
    libro = gc.open_by_key(_cfg()["sheet_id"])
    disponibles = [w.title for w in libro.worksheets()]
    # tolera mayúsculas, tildes y espacios en el nombre de la pestaña
    hoja = next((t for t in disponibles if _plano(t) == _plano(pestana)), None)
    if hoja is None:
        raise ErrorConfiguracion(
            f"El Google Sheet no tiene la pestaña «{pestana}». Pestañas encontradas: "
            f"{', '.join(disponibles) or '(ninguna)'}. Renombra la pestaña o define "
            f"`pestana_beneficiarios` / `pestana_cohortes` en `[tcf10]` de los Secrets. "
            f"Si el Sheet aún no está listo, quita `sheet_id` y la app usa la base del SIS.")
    valores = libro.worksheet(hoja).get_all_values()
    return pd.DataFrame(valores[1:], columns=valores[0]) if valores else pd.DataFrame()


def _bq(archivo: str, ids: tuple[int, ...] | None = None, **escalares: float) -> pd.DataFrame:
    """Corre queries/<archivo>.sql con {dataset} reemplazado y parámetros @ids_sis / escalares FLOAT64."""
    from google.cloud import bigquery
    cfg = _cfg()
    creds = _credenciales(["https://www.googleapis.com/auth/bigquery"])
    cliente = bigquery.Client(credentials=creds, project=cfg.get("bq_project", creds.project_id))
    sql = (RAIZ / "queries" / f"{archivo}.sql").read_text(encoding="utf-8").replace("{dataset}", cfg["sis_dataset"])
    params = [] if ids is None else [bigquery.ArrayQueryParameter("ids_sis", "INT64", list(ids))]
    params += [bigquery.ScalarQueryParameter(k, "FLOAT64", float(v)) for k, v in escalares.items()]
    try:
        return cliente.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).to_dataframe()
    except Exception as e:  # noqa: BLE001 -- Streamlit Cloud oculta el mensaje original: se muestra en pantalla
        codigo = getattr(e, "code", None)
        pista = {
            403: f"La cuenta de servicio no tiene permiso. Necesita «BigQuery Job User» en el proyecto "
                 f"«{cliente.project}» y «BigQuery Data Viewer» sobre DVTD_SIS, DSTD_SIS y DSGE_SIS.",
            404: f"No se encontró la vista o el dataset. Revisa `sis_dataset` en los Secrets "
                 f"(hoy: «{cfg['sis_dataset']}») y la ubicación (región) del dataset.",
            400: "La consulta tiene un error (columna o tipo de dato distinto al esperado en la vista).",
        }.get(codigo, "Error al consultar BigQuery.")
        detalle = getattr(e, "message", None) or str(e)
        raise ErrorConfiguracion(f"{pista}\n\nConsulta: `queries/{archivo}.sql` · Código: {codigo}\n\n"
                                 f"Detalle de BigQuery: {detalle[:600]}") from e


@st.cache_data(ttl=3600, show_spinner="Consultando el avance en el SIS (BigQuery)…")
def _avance_bigquery(ids: tuple[int, ...]) -> pd.DataFrame:
    cfg = _cfg()
    return _bq("avance_sis", ids,
               horas_sesion=cfg.get("horas_por_sesion", 3.0),
               # time_view en segundos → 3600; en minutos → 60 (validar con queries/validar_unidades.sql)
               divisor_tiempo=cfg.get("divisor_time_view", 3600))


@st.cache_data(ttl=3600, show_spinner="Leyendo la base de estudiantes del SIS…")
def _base_sis() -> pd.DataFrame:
    return _bq("base_sis")


def base_desde_sis(crudo: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sin Sheet: todos los estudiantes del SIS son la base. La cohorte = fecha de inicio del grupo.
    Docente, gestor, franja, población, certificación y PILA quedan «Sin dato» hasta que exista el Sheet."""
    df = crudo.copy()
    df["id_sis"] = pd.to_numeric(df["id_sis"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["id_sis"]).drop_duplicates("id_sis")
    for c in ("fecha_inicio", "fecha_fin"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["cohorte"] = df["fecha_inicio"].dt.strftime("Inicio %d/%m/%Y").fillna("Sin fecha de inicio")
    cohortes = (df.groupby("cohorte", as_index=False)
                  .agg(fecha_inicio=("fecha_inicio", "min"), fecha_fin=("fecha_fin", "max"))
                  .sort_values("fecha_inicio"))
    benef = pd.DataFrame({
        "id_sis": df["id_sis"], "documento": None, "nombre": df["iniciales"].fillna(""),
        "cohorte": df["cohorte"], "poblacion": "Sin dato",
        "perfil": df["perfil"].fillna("Sin dato"), "nivel": df["nivel"].fillna("Sin dato"),
        "grupo": df["grupo"].fillna("Sin dato"), "docente": "Sin dato", "gestor": "Sin dato",
        "franja": "Sin dato", "enrolado": True, "estado": "Activo", "lab_inicio": "",
        "certificado": None, "formal_t3": None, "fuente": "sis",
    })
    benef["certificado"] = pd.Series([None] * len(benef), index=benef.index, dtype=object)
    benef["formal_t3"] = pd.Series([None] * len(benef), index=benef.index, dtype=object)
    return benef.reset_index(drop=True), cohortes.reset_index(drop=True)


def cargar() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bool]:
    """(beneficiarios, avance, cohortes, es_demo)."""
    m = modo()
    if m == "demo":
        benef = limpiar_beneficiarios(pd.read_csv(DEMO / "beneficiarios.csv", dtype=str))
        avance = limpiar_avance(pd.read_csv(DEMO / "avance.csv"))
        cohortes = limpiar_cohortes(pd.read_csv(DEMO / "cohortes.csv", dtype=str))
        return benef, avance, cohortes, True
    cfg = _cfg()
    if m == "sis":
        benef, cohortes = base_desde_sis(_base_sis())
    else:
        benef = limpiar_beneficiarios(_leer_sheet(cfg.get("pestana_beneficiarios", "BENEFICIARIOS")))
        cohortes = limpiar_cohortes(_leer_sheet(cfg.get("pestana_cohortes", "COHORTES")))
    ids = tuple(int(x) for x in benef["id_sis"].dropna().unique())
    avance = limpiar_avance(_avance_bigquery(ids)) if ids else pd.DataFrame(
        columns=["id_sis", "horas_sinc", "horas_asinc", "ultima_actividad", "grupo_sis", "actualizado_sis"])
    benef = _completar_grupo(benef, avance)
    return benef, avance, cohortes, False


# ------------------------------------------------------------------ agregados del SIS (página de asistencia)
@st.cache_data(ttl=3600, show_spinner="Consultando asistencia y avance por curso…")
def _agregados_bigquery(ids: tuple[int, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    return _bq("asistencia_sesiones", ids), _bq("progreso_cursos", ids)


def agregados(ids: tuple[int, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(asistencia por grupo × sesión, progreso por grupo × curso). En demo se generan sintéticos."""
    if modo_demo():
        return _agregados_demo(ids)
    asis, prog = _agregados_bigquery(ids)
    asis["fecha"] = pd.to_datetime(asis["fecha"], errors="coerce")
    return asis, prog


def _agregados_demo(ids: tuple[int, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    import numpy as np
    rng = np.random.default_rng(10)
    benef = limpiar_beneficiarios(pd.read_csv(DEMO / "beneficiarios.csv", dtype=str))
    benef = benef[benef["enrolado"]]
    cohortes = limpiar_cohortes(pd.read_csv(DEMO / "cohortes.csv", dtype=str)).set_index("cohorte")
    filas_a, filas_p = [], []
    for (coh, grupo), g in benef.groupby(["cohorte", "grupo"]):
        inicio = cohortes.loc[coh, "fecha_inicio"]
        n, calidad = len(g), rng.uniform(.55, .9)
        registro = rng.uniform(.75, 1)
        for k in range(1, 22):
            fecha = inicio + pd.Timedelta(days=int((k - 1) * 3.4))
            if fecha >= pd.Timestamp("2026-11-13"):
                break
            reg = int(n * (registro if rng.random() > .08 else 0))
            asis = int(reg * max(.2, calidad - k * .012 + rng.normal(0, .05)))
            filas_a.append({"grupo": grupo, "session_id": f"{grupo}-{k}", "sesion": k, "fecha": fecha,
                            "convocados": n, "asistieron": asis, "no_asistieron": reg - asis,
                            "sin_registro": n - reg, "actualizado": None})
        for c, curso in enumerate(["Inducción", "Módulo 1", "Módulo 2", "Módulo 3"]):
            comp = int(n * max(0, calidad - c * .25)); prog = int((n - comp) * .6)
            filas_p.append({"grupo": grupo, "curso": curso, "estudiantes": n, "completado": comp,
                            "en_progreso": prog, "sin_iniciar": n - comp - prog,
                            "avance_promedio": (comp + prog * .4) / n, "pct_lecciones": (comp + prog * .4) / n})
    return pd.DataFrame(filas_a), pd.DataFrame(filas_p)


def _completar_grupo(benef: pd.DataFrame, avance: pd.DataFrame) -> pd.DataFrame:
    """El Sheet manda; si el grupo viene vacío se usa el grupo principal del SIS."""
    grupos = avance.dropna(subset=["grupo_sis"]).set_index("id_sis")["grupo_sis"]
    vacio = benef["grupo"].eq("Sin dato")
    benef.loc[vacio, "grupo"] = benef.loc[vacio, "id_sis"].map(grupos).fillna("Sin dato")
    return benef


def refrescar() -> None:
    for f in (_leer_sheet, _avance_bigquery, _base_sis, _agregados_bigquery):
        f.clear()
