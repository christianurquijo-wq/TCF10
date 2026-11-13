"""
Carga de datos de TCF10.

  beneficiarios + cohortes  Google Sheet operativo (base entregada por Atenea + estado operativo que
                            actualiza el equipo: grupo, docente, gestor, franja, retiros, certificación,
                            situación laboral). Pestañas BENEFICIARIOS y COHORTES.
  avance                    SIS de Kuepa en BigQuery (queries/avance_sis.sql), filtrado por los ID SIS
                            de la base: horas sincrónicas (asistencia) y asincrónicas (plataforma).

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
    texto = serie.astype("string").str.strip().str.upper()
    return texto.map(lambda v: None if pd.isna(v) or v == "" else v in {"SI", "SÍ", "TRUE", "1", "X", "VERDADERO"})


def limpiar_beneficiarios(crudo: pd.DataFrame) -> pd.DataFrame:
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
    return df[["id_sis", "horas_sinc", "horas_asinc", "ultima_actividad"]]


# ------------------------------------------------------------------ fuentes
def _cfg() -> dict:
    try:
        return dict(st.secrets.get("tcf10", {}))
    except Exception:  # noqa: BLE001 -- sin secrets.toml
        return {}


def modo_demo() -> bool:
    cfg = _cfg()
    try:
        hay_sa = "gcp_service_account" in st.secrets
    except Exception:  # noqa: BLE001
        hay_sa = False
    return not (cfg.get("sheet_id") and cfg.get("sis_dataset") and hay_sa)


def _credenciales(scopes: list[str]):
    from google.oauth2.service_account import Credentials
    return Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)


@st.cache_data(ttl=900, show_spinner="Leyendo la base de beneficiarios…")
def _leer_sheet(pestana: str) -> pd.DataFrame:
    import gspread
    gc = gspread.authorize(_credenciales(["https://www.googleapis.com/auth/spreadsheets.readonly"]))
    valores = gc.open_by_key(_cfg()["sheet_id"]).worksheet(pestana).get_all_values()
    return pd.DataFrame(valores[1:], columns=valores[0]) if valores else pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner="Consultando el avance en el SIS (BigQuery)…")
def _avance_bigquery(ids: tuple[int, ...]) -> pd.DataFrame:
    from google.cloud import bigquery
    cfg = _cfg()
    creds = _credenciales(["https://www.googleapis.com/auth/bigquery"])
    cliente = bigquery.Client(credentials=creds, project=cfg.get("bq_project", creds.project_id))
    sql = SQL_AVANCE.read_text(encoding="utf-8").replace("{dataset}", cfg["sis_dataset"])
    params = [bigquery.ArrayQueryParameter("ids_sis", "INT64", list(ids)),
              bigquery.ScalarQueryParameter("horas_sesion", "FLOAT64", float(cfg.get("horas_por_sesion", 3.0)))]
    return cliente.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).to_dataframe()


def cargar() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, bool]:
    """(beneficiarios, avance, cohortes, es_demo)."""
    if modo_demo():
        benef = limpiar_beneficiarios(pd.read_csv(DEMO / "beneficiarios.csv", dtype=str))
        avance = limpiar_avance(pd.read_csv(DEMO / "avance.csv"))
        cohortes = limpiar_cohortes(pd.read_csv(DEMO / "cohortes.csv", dtype=str))
        return benef, avance, cohortes, True
    cfg = _cfg()
    benef = limpiar_beneficiarios(_leer_sheet(cfg.get("pestana_beneficiarios", "BENEFICIARIOS")))
    cohortes = limpiar_cohortes(_leer_sheet(cfg.get("pestana_cohortes", "COHORTES")))
    ids = tuple(int(x) for x in benef["id_sis"].dropna().unique())
    avance = limpiar_avance(_avance_bigquery(ids)) if ids else pd.DataFrame(
        columns=["id_sis", "horas_sinc", "horas_asinc", "ultima_actividad"])
    return benef, avance, cohortes, False


def refrescar() -> None:
    _leer_sheet.clear()
    _avance_bigquery.clear()
