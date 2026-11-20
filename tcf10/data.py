"""
Carga de datos de TCF10.

  beneficiarios + cohortes  Google Sheet operativo (base entregada por Atenea + estado operativo que
                            actualiza el equipo: grupo, docente, gestor, franja, retiros, certificación,
                            situación laboral). Pestañas BENEFICIARIOS y COHORTES.
  avance                    Vistas VTD10 del SIS (DVTD_SIS) en BigQuery (queries/avance_sis.sql), cruzadas
                            por ID SIS = incremental: sincrónicas = sesiones asistidas × horas_por_sesion;
                            asincrónicas = Horas_Plataforma_Acreditadas (pedagogical_time de
                            VTD10_student_progress_detail ÷ 3600; respaldo: course_time_view).

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
    from tcf10 import config as C
    df["franja"] = df["franja"].map(C.etiqueta_franja)  # «Mañana» → «Mañana · 8:00 a. m.»
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
    if "sesiones_registradas" not in df and "sesiones_sin_registro" in df:  # consulta de BigQuery
        df["sesiones_registradas"] = (pd.to_numeric(df["sesiones_a_la_fecha"], errors="coerce")
                                      - pd.to_numeric(df["sesiones_sin_registro"], errors="coerce"))
    for c in ("sesiones_asistidas", "sesiones_registradas", "sesiones_a_la_fecha"):
        df[c] = pd.to_numeric(df[c], errors="coerce") if c in df else float("nan")
    return df[["id_sis", "horas_sinc", "horas_asinc", "ultima_actividad", "grupo_sis", "actualizado_sis",
               "sesiones_asistidas", "sesiones_registradas", "sesiones_a_la_fecha"]]


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
        return "gcp_service_account" in st.secrets or "gcp_service_account_bq" in st.secrets
    except Exception:  # noqa: BLE001
        return False


def modo() -> str:
    """'demo' sin credenciales · 'sis' con datos del SIS pero sin Sheet operativo · 'completo' con ambos."""
    cfg = _cfg()
    if not (_hay_sa() and (cfg.get("sis_sheet_id") or cfg.get("sis_dataset"))):
        return "demo"
    return "completo" if cfg.get("sheet_id") else "sis"


def _horas_por_sesion() -> float:
    """4 h por sesión asistida (config.HORAS_POR_SESION). No se lee de los Secrets: allí quedó 3.0 de la configuración
    inicial y pisaba el valor confirmado."""
    from tcf10 import config as C
    return float(C.HORAS_POR_SESION)


def fuente_sis() -> str:
    """'bq' si [tcf10] trae sis_dataset (BigQuery directo, tiene prioridad); 'sheet' si solo trae sis_sheet_id."""
    return "bq" if _cfg().get("sis_dataset") else "sheet"


def origen_horas() -> str:
    """Texto corto con el origen de las horas (para mostrar en la ficha)."""
    from tcf10 import config as C
    sinc = f"Con docente: {str(C.HORAS_POR_SESION).replace('.0', '')} h por sesión asistida"
    if modo() == "demo":
        return sinc
    from tcf10 import sis_sheet
    try:
        t = _sis_sheet(_esquema_sis())
        fuente = sis_sheet.fuente_plataforma(t)
        m = t["meta"].iloc[0].to_dict()
    except Exception:  # noqa: BLE001
        return sinc
    plat = {"consulta_por_estudiante": f"hoja «{m.get('est_pestana', 'Consulta por estudiante')}» "
                                       f"(horas_plataforma_acreditadas, {m.get('est_ids', 0)} estudiantes)",
            "pedagogical_time": "pedagogical_time del detalle (recursos completados)",
            "pedagogical_time_sin_filtro": "pedagogical_time del detalle (sin filtro)",
            }.get(fuente, "course_time_view (respaldo)")
    return f"{sinc} · Plataforma: {plat}"


def aviso_plataforma() -> str:
    """Texto de aviso si las horas de plataforma NO salen de Horas_Plataforma_Acreditadas (pedagogical_time)."""
    if modo() == "demo":
        return ""
    from tcf10 import sis_sheet
    try:
        fuente = sis_sheet.fuente_plataforma(_sis_sheet(_esquema_sis()))
    except Exception:  # noqa: BLE001 - el error de lectura ya se muestra en otra parte
        return ""
    meta = _sis_sheet(_esquema_sis()).get("meta")
    m = meta.iloc[0].to_dict() if meta is not None and len(meta) else {}
    if fuente == "consulta_por_estudiante":
        if m.get("est_tipo") == "DATA_SOURCE" and m.get("est_filas", 0) <= 500:
            return (f"La pestaña «{m.get('est_pestana')}» es una hoja conectada a BigQuery y por API solo entrega "
                    f"una vista previa ({m.get('est_filas')} filas). Usa «Extraer» del conector para copiar el "
                    "resultado a una pestaña normal y dale ese nombre.")
        return ""
    if m.get("est_pestana"):
        motivo = (m.get("est_error") or
                  (f"es una hoja conectada a BigQuery ({m.get('est_tipo')}) y no entregó filas por API"
                   if m.get("est_tipo") == "DATA_SOURCE" else
                   f"se leyeron {m.get('est_filas', 0)} filas pero faltan las columnas incremental u "
                   "horas_plataforma_acreditadas"))
        return (f"No se pudieron usar las horas de «{m.get('est_pestana')}»: {motivo}. Si es una hoja conectada, "
                "usa «Extraer» del conector para copiar el resultado a una pestaña normal.")
    if fuente == "pedagogical_time":
        return ("No encontré la pestaña «Consulta por estudiante» en el Sheet del SIS; las horas en plataforma se "
                f"calculan con el detalle exportado (puede estar incompleto). Pestañas: {m.get('pestanas', '')}.")
    if fuente == "pedagogical_time_sin_filtro":
        return ("Las horas en plataforma suman todo el pedagogical_time: la pestaña «VTD10_student_progress_detail» "
                "no trae component_category o is_completed, así que no se puede limitar a recursos completados "
                "(regla de Looker Studio). Agrega esas dos columnas al Sheet.")
    return ("Las horas en plataforma se están calculando con course_time_view porque la pestaña "
            "«VTD10_student_progress_detail» del Sheet del SIS no trae la columna pedagogical_time. Agrégala para "
            "usar Horas_Plataforma_Acreditadas.")


def _esquema_sis() -> str:
    """Huella de las columnas que se leen del SIS: si cambian en el código, la caché anterior se descarta sola
    (sin esto, tras un push la app podía seguir con tablas viejas a las que les faltaban columnas)."""
    import hashlib
    from tcf10 import sis_sheet
    return hashlib.md5(repr((sis_sheet.COLUMNAS, sis_sheet.COL_PEDAGOGICO, sis_sheet.VERSION, fuente_sis(),
                             _cfg().get("sis_dataset"))).encode()).hexdigest()[:8]


@st.cache_data(ttl=900, show_spinner="Cargando datos…")
def _sis_sheet(esquema: str = "") -> dict[str, pd.DataFrame]:
    """Tablas del SIS (vistas VTD10) livianas y sin datos personales (solo ID SIS e iniciales).

    Origen: BigQuery directo si hay `sis_dataset` en [tcf10]; si no, la copia en Google Sheets (`sis_sheet_id`).
    Ambos caminos entregan las mismas tablas crudas a sis_sheet.preparar(), así que el resto de la app no cambia."""
    if fuente_sis() == "bq":
        return _sis_bigquery()
    import gspread
    from gspread.utils import DateTimeOption, ValueRenderOption
    from tcf10 import sis_sheet
    gc = gspread.authorize(_credenciales(["https://www.googleapis.com/auth/spreadsheets.readonly"]))
    try:
        libro = gc.open_by_key(_cfg()["sis_sheet_id"])
    except gspread.exceptions.APIError as e:
        raise ErrorConfiguracion(
            f"No se pudo abrir el Sheet del SIS ({e.response.status_code}). Compártelo como Lector con "
            f"{st.secrets['gcp_service_account'].get('client_email', 'la cuenta de servicio')}.") from e
    por_plano = {_plano(w.title): w for w in libro.worksheets()}
    crudas = {}
    titulos = dict(sis_sheet.PESTANAS)
    titulos["prog_est"] = next((t for t in sis_sheet.PESTANA_EST if _plano(t) in por_plano), sis_sheet.PESTANA_EST[0])
    diag = {"est_pestana": "", "est_tipo": "", "est_filas": 0, "est_error": "",
            "pestanas": " · ".join(w.title for w in libro.worksheets())}
    for clave, titulo in titulos.items():
        ws = por_plano.get(_plano(titulo))
        if ws is None:
            continue
        if clave == "prog_est":
            diag["est_pestana"] = ws.title
            diag["est_tipo"] = str(getattr(ws, "_properties", {}).get("sheetType", ""))
        try:
            v = ws.get_all_values(value_render_option=ValueRenderOption.unformatted,
                                  date_time_render_option=DateTimeOption.formatted_string)
        except Exception as e:  # noqa: BLE001
            if clave != "prog_est":
                raise
            diag["est_error"] = f"{type(e).__name__}: {str(e)[:200]}"
            continue
        if clave == "prog_est":
            diag["est_filas"] = max(0, len(v) - 1)
        if v:
            ancho = len(v[0])
            crudas[clave] = pd.DataFrame([(f + [""] * ancho)[:ancho] for f in v[1:]],
                                         columns=[str(c).strip() for c in v[0]])
    try:
        t = sis_sheet.preparar(crudas)
        for k, val in diag.items():
            t["meta"][k] = val
        t["meta"]["est_ids"] = int(t["prog_est"]["id_sis"].nunique()) if len(t["prog_est"]) else 0
        return t
    except sis_sheet.FaltaEstructura as e:
        raise ErrorConfiguracion(f"{e} Pestañas encontradas: {', '.join(w.title for w in libro.worksheets())}.") from e


def modo_demo() -> bool:
    return modo() == "demo"


def _credenciales(scopes: list[str], seccion: str = "gcp_service_account"):
    from google.oauth2.service_account import Credentials
    return Credentials.from_service_account_info(dict(st.secrets[seccion]), scopes=scopes)


def _seccion_bq() -> str:
    """BigQuery puede usar su propia cuenta de servicio: [gcp_service_account_bq]. Si no existe, usa la general
    ([gcp_service_account], la que lee los Google Sheets)."""
    try:
        return "gcp_service_account_bq" if "gcp_service_account_bq" in st.secrets else "gcp_service_account"
    except Exception:  # noqa: BLE001
        return "gcp_service_account"


@st.cache_data(ttl=900, show_spinner="Cargando datos…")
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


def _formalizacion_cruda() -> pd.DataFrame:
    """Base «DB Formalización TCF10» tal cual (con datos personales). No se cachea: quien la llame decide qué
    columnas conserva."""
    import gspread
    from tcf10 import base_atenea
    cfg = _cfg()
    gc = gspread.authorize(_credenciales(["https://www.googleapis.com/auth/spreadsheets.readonly"]))
    try:
        libro = gc.open_by_key(cfg["sheet_id"])
    except gspread.exceptions.APIError as e:
        raise ErrorConfiguracion(
            f"No se pudo abrir la base de Formalización ({e.response.status_code}). Compártela como Lector con "
            f"{st.secrets['gcp_service_account'].get('client_email', 'la cuenta de servicio')}.") from e
    hojas = libro.worksheets()
    pedida = cfg.get("pestana_beneficiarios")
    ws = (next((w for w in hojas if _plano(w.title) == _plano(pedida)), None) if pedida else
          next((w for w in hojas if "formalizacion" in _plano(w.title)), None))
    if ws is None:
        raise ErrorConfiguracion(f"No encontré la pestaña de la base ({pedida or 'Formalización TCF10'}). "
                                 f"Pestañas: {', '.join(w.title for w in hojas)}.")
    valores = ws.get_all_values()
    if not base_atenea.es_formalizacion(valores):
        raise ErrorConfiguracion(f"La pestaña «{ws.title}» no tiene la columna NUMERO_DOCUMENTO.")
    return base_atenea.a_dataframe(valores)


@st.cache_data(ttl=900, show_spinner="Cargando datos…")
def _base_formalizacion() -> pd.DataFrame:
    """Base de Formalización SIN datos personales (huella del documento, iniciales y columnas del contrato)."""
    from tcf10 import base_atenea
    crudo = _formalizacion_cruda()
    t = _sis_sheet(_esquema_sis())
    mapa = dict(zip(t["docs"]["huella"], t["docs"]["id_sis"].astype(int)))
    try:
        return base_atenea.limpiar(crudo, mapa)
    except ValueError as e:
        raise ErrorConfiguracion(str(e)) from e


def _cliente_bq():
    from google.cloud import bigquery
    creds = _credenciales(["https://www.googleapis.com/auth/bigquery"], _seccion_bq())
    # Sin bq_project, las consultas corren (y se cobran) en el proyecto de la propia cuenta de servicio.
    return bigquery.Client(credentials=creds, project=_cfg().get("bq_project") or creds.project_id)


def _consulta(cliente, sql: str, nombre: str) -> pd.DataFrame:
    """Corre una consulta y devuelve un DataFrame; los errores se muestran en pantalla con una pista."""
    try:
        return cliente.query(sql).to_dataframe(create_bqstorage_client=False)
    except Exception as e:  # noqa: BLE001 -- Streamlit Cloud oculta el mensaje original: se muestra en pantalla
        codigo = getattr(e, "code", None)
        ds = _cfg().get("sis_dataset", "")
        pista = {
            403: f"La cuenta de servicio de [{_seccion_bq()}] no tiene permiso. Necesita «BigQuery Job User» en el proyecto "
                 f"«{cliente.project}» y «BigQuery Data Viewer» sobre el dataset «{ds}».",
            404: f"No se encontró la vista o el dataset. Revisa `sis_dataset` en los Secrets (hoy: «{ds}»).",
            400: "La consulta tiene un error (columna o tipo de dato distinto al esperado en la vista).",
        }.get(codigo, "Error al consultar BigQuery.")
        detalle = getattr(e, "message", None) or str(e)
        raise ErrorConfiguracion(f"{pista}\n\nConsulta: {nombre} · Código: {codigo}\n\n"
                                 f"Detalle de BigQuery: {detalle[:600]}") from e


def _como_texto(df: pd.DataFrame) -> pd.DataFrame:
    """Deja cada valor como texto, igual que llega de Google Sheets: así sis_sheet.preparar() trata las dos fuentes
    igual (fechas UTC → Bogotá, números, verdadero/falso)."""
    def t(v):
        try:
            if v is None or pd.isna(v):
                return ""
        except (TypeError, ValueError):
            pass
        return str(v)
    return pd.DataFrame({c: df[c].astype(object).map(t) for c in df.columns})


# columnas extra que se piden si la vista las tiene (documento para cruzar con Formalización, hora de inicio)
EXTRAS_BQ = {"asis_det": ["student_doc", "session_start_date"], "asis_res": ["student_doc"],
             "prog_cur": ["student_doc"], "prog_det": ["student_doc"]}

SQL_POR_ESTUDIANTE = """
SELECT
  incremental,
  ROUND(SUM(IF(LOWER(TRIM(CAST(component_category AS STRING))) = 'resource'
               AND LOWER(CAST(is_completed AS STRING)) IN ('true', '1'),
               SAFE_CAST(pedagogical_time AS FLOAT64), 0)) / 3600, 4)            AS horas_plataforma_acreditadas,
  MAX(completed_date)                                                           AS ultima_fecha_completada,
  ARRAY_AGG(IF(completed_date IS NULL, NULL, STRUCT(lesson_name, course_name))
            IGNORE NULLS ORDER BY completed_date DESC LIMIT 1)[SAFE_OFFSET(0)].lesson_name AS ultima_leccion,
  ARRAY_AGG(IF(completed_date IS NULL, NULL, STRUCT(lesson_name, course_name))
            IGNORE NULLS ORDER BY completed_date DESC LIMIT 1)[SAFE_OFFSET(0)].course_name AS ultimo_curso,
  MAX(last_updated_statistics)                                                  AS last_updated_statistics
FROM `{ds}.VTD10_student_progress_detail`
WHERE SAFE_CAST(incremental AS INT64) NOT IN ({excl})
GROUP BY incremental
"""


def _sis_bigquery() -> dict[str, pd.DataFrame]:
    """Lee las vistas VTD10 directo de BigQuery (solo las columnas que usa la app; sin nombres ni correos salvo el
    nombre de la vista básica, que se reduce a iniciales en sis_sheet.preparar)."""
    from tcf10 import config as C
    from tcf10 import sis_sheet
    ds = _cfg()["sis_dataset"].strip().strip("`")
    excl = ", ".join(str(int(x)) for x in C.USUARIOS_PRUEBA) or "-1"
    cliente = _cliente_bq()
    vistas = list(sis_sheet.PESTANAS.values())
    proyecto, dataset = ds.split(".", 1) if "." in ds else (cliente.project, ds)
    info = _consulta(cliente, f"SELECT table_name, column_name FROM `{proyecto}.{dataset}`.INFORMATION_SCHEMA.COLUMNS "
                              f"WHERE table_name IN ({', '.join(repr(v) for v in vistas)})", "columnas de las vistas")
    disponibles = info.groupby("table_name")["column_name"].apply(set).to_dict()
    crudas = {}
    for clave, vista in sis_sheet.PESTANAS.items():
        if vista not in disponibles:
            continue  # sis_sheet.preparar() avisa si falta una vista obligatoria
        cols = [c for c in sis_sheet.COLUMNAS[clave] + EXTRAS_BQ.get(clave, []) if c in disponibles[vista]]
        idc = "user_incremental" if clave == "basica" else "incremental"
        filtro = f"SAFE_CAST({idc} AS INT64) NOT IN ({excl})"
        if clave == "prog_det":
            filtro += " AND completed_date IS NOT NULL"  # solo lecciones terminadas: lo único que se usa
        sql = f"SELECT {', '.join(f'`{c}`' for c in dict.fromkeys(cols))} FROM `{ds}.{vista}` WHERE {filtro}"
        crudas[clave] = _como_texto(_consulta(cliente, sql, vista))
    if "VTD10_student_progress_detail" in disponibles:
        crudas["prog_est"] = _como_texto(_consulta(cliente, SQL_POR_ESTUDIANTE.format(ds=ds, excl=excl),
                                                   "horas de plataforma por estudiante"))
    try:
        t = sis_sheet.preparar(crudas)
    except sis_sheet.FaltaEstructura as e:
        raise ErrorConfiguracion(f"{e} Vistas encontradas en {ds}: {', '.join(sorted(disponibles)) or '(ninguna)'}.") from e
    t["meta"]["est_pestana"] = "BigQuery"
    t["meta"]["est_ids"] = int(t["prog_est"]["id_sis"].nunique()) if len(t["prog_est"]) else 0
    return t


def agrupar_cohortes(inicios: pd.Series) -> pd.Series:
    """Sin la base de Atenea: los grupos que arrancan con menos de 3 semanas de diferencia forman una
    cohorte («Cohorte 1 · 10–18 nov 2026»). Antes salía una cohorte por cada fecha distinta."""
    from tcf10 import config as C
    meses = "ene feb mar abr may jun jul ago sep oct nov dic".split()
    fechas = sorted(pd.to_datetime(inicios.dropna().unique()))
    bloques, actual = [], []
    for f in fechas:
        if actual and (f - actual[-1]).days > C.COHORTE_SEPARACION_DIAS:
            bloques.append(actual); actual = []
        actual.append(f)
    if actual:
        bloques.append(actual)
    nombre = {}
    for i, b in enumerate(bloques, start=1):
        a, z = b[0], b[-1]
        if a == z:
            rango = f"{a.day} {meses[a.month - 1]} {a.year}"
        elif a.month == z.month:
            rango = f"{a.day}–{z.day} {meses[a.month - 1]} {a.year}"
        else:
            rango = f"{a.day} {meses[a.month - 1]} – {z.day} {meses[z.month - 1]} {z.year}"
        for f in b:
            nombre[f] = f"Cohorte {i} · {rango}"
    return pd.to_datetime(inicios).map(nombre).fillna("Sin grupo con fecha")


def base_desde_sis(crudo: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sin Sheet: todos los estudiantes del SIS son la base. La cohorte = fecha de inicio del grupo.
    Docente, gestor, franja, población, certificación y PILA quedan «Sin dato» hasta que exista el Sheet."""
    df = crudo.copy()
    df["id_sis"] = pd.to_numeric(df["id_sis"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["id_sis"]).drop_duplicates("id_sis")
    for c in ("fecha_inicio", "fecha_fin"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["cohorte"] = agrupar_cohortes(df["fecha_inicio"])
    cohortes = (df.groupby("cohorte", as_index=False)
                  .agg(fecha_inicio=("fecha_inicio", "min"), fecha_fin=("fecha_fin", "max"))
                  .sort_values("fecha_inicio", na_position="last"))
    benef = pd.DataFrame({
        "id_sis": df["id_sis"], "documento": None, "nombre": df["iniciales"].fillna(""),
        "cohorte": df["cohorte"], "poblacion": "Sin dato",
        "perfil": df["perfil"].fillna("Sin dato"), "nivel": df["nivel"].fillna("Sin dato"),
        "grupo": df["grupo"].fillna("Sin dato"), "docente": "Sin dato", "gestor": "Sin dato",
        "franja": "Sin dato", "enrolado": True, "estado": "Activo", "lab_inicio": "",
        "certificado": None, "formal_t3": None, "fuente": "sis",
        # calendario propio del grupo: el ritmo esperado se mide con las fechas del grupo, no de la cohorte
        "fi_grupo": df["fecha_inicio"], "ff_grupo": df["fecha_fin"],
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
    from tcf10 import sis_sheet
    if m == "sis":
        benef, cohortes = base_desde_sis(sis_sheet.base(_sis_sheet(_esquema_sis())))
    elif cfg.get("sheet_id"):
        # Base real: «DB Formalización TCF10» cruzada por documento con el SIS; grupo y fechas salen del SIS.
        from tcf10 import base_atenea
        benef, cohortes = base_atenea.calendario(_base_formalizacion(), sis_sheet.base(_sis_sheet(_esquema_sis())))
        franjas = _sis_sheet(_esquema_sis()).get("franjas")
        if franjas is not None and len(franjas):
            mapa = franjas.set_index("grupo")["franja"]
            benef["franja"] = benef["grupo"].map(mapa).fillna(benef["franja"])
    else:
        benef = limpiar_beneficiarios(_leer_sheet(cfg.get("pestana_beneficiarios", "BENEFICIARIOS")))
        cohortes = limpiar_cohortes(_leer_sheet(cfg.get("pestana_cohortes", "COHORTES")))
    ids = tuple(int(x) for x in benef["id_sis"].dropna().unique() if int(x) > 0)  # negativos = sin usuario SIS
    avance = limpiar_avance(sis_sheet.avance(_sis_sheet(_esquema_sis()), ids, _horas_por_sesion(),
                                             float(cfg.get("divisor_time_view", 3600))))
    benef = _completar_grupo(benef, avance)
    return benef, avance, cohortes, False


# ------------------------------------------------------------------ vista Atenea (detrás de login)
@st.cache_data(ttl=900, show_spinner="Cargando datos…")
def identidades() -> pd.DataFrame:
    """Nombre completo y documento por huella, SOLO para la app de Atenea (detrás de login con correos de
    Atenea y Kuepa). Atenea es la dueña de la base: aquí no se agrega información que no tenga."""
    from tcf10 import base_atenea as B
    if modo_demo():
        demo = pd.read_csv(DEMO / "beneficiarios.csv", dtype=str)
        return pd.DataFrame({"id_sis": pd.to_numeric(demo["ID SIS"]).astype("Int64"),
                             "nombre_completo": demo["Nombre"], "tipo_documento": "CC",
                             "documento": demo["Documento"]})
    crudo = _formalizacion_cruda()
    por_plano = {B._plano(c): c for c in crudo.columns}
    col = lambda *n: next((crudo[por_plano[B._plano(x)]] for x in n if B._plano(x) in por_plano),  # noqa: E731
                          pd.Series([""] * len(crudo), index=crudo.index)).astype("string").fillna("").str.strip()
    nombre = (col("PRIMER_NOMBRE") + " " + col("SEGUNDO_NOMBRE") + " " + col("PRIMER_APELLIDO") + " "
              + col("SEGUNDO_APELLIDO")).str.replace(r"\s+", " ", regex=True).str.strip().str.title()
    out = pd.DataFrame({"huella": B.huella(col("NUMERO_DOCUMENTO")), "nombre_completo": nombre,
                        "tipo_documento": col("TIPO_DOCUMENTO").str.title(),
                        "documento": B.doc_normalizado(col("NUMERO_DOCUMENTO"))})
    return out.dropna(subset=["huella"]).drop_duplicates("huella")


def detalle_persona(id_sis: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(sesiones, cursos) de una persona para la ficha de la app de Atenea."""
    if modo_demo() or id_sis is None or int(id_sis) <= 0:
        return pd.DataFrame(), pd.DataFrame()
    t = _sis_sheet(_esquema_sis())
    s = t["asis_det"][t["asis_det"]["id_sis"] == int(id_sis)].copy()
    s["Asistencia"] = s.apply(lambda r: "Asistió" if r["attended"] else ("No asistió" if r["not_attended"] else
                              ("Sin registro" if r["is_past_session"] else "Programada")), axis=1)
    ses = (s.sort_values("session_date")[["session_date", "session_number", "group_name", "Asistencia"]]
            .rename(columns={"session_date": "Fecha", "session_number": "Sesión", "group_name": "Grupo"}))
    c = t["prog_cur"][t["prog_cur"]["id_sis"] == int(id_sis)].copy()
    cur = pd.DataFrame({"Curso": c["course_name"], "Avance": c["course_completed_status"] / 100,
                        "Lecciones": c["lessons_completed"].fillna(0).astype(int).astype(str) + " de "
                                     + c["lessons_active"].fillna(0).astype(int).astype(str),
                        "Estado": c["progress_status"].map({"completado": "Completado", "en_progreso": "En progreso",
                                                            "sin_iniciar": "Sin iniciar"})})
    return ses.reset_index(drop=True), cur.reset_index(drop=True)


# ------------------------------------------------------------------ agregados del SIS (página de asistencia)
def agregados(ids: tuple[int, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(asistencia por grupo × sesión, progreso por grupo × curso). En demo se generan sintéticos."""
    if modo_demo():
        return _agregados_demo(ids)
    from tcf10 import sis_sheet
    asis, prog = sis_sheet.agregados(_sis_sheet(_esquema_sis()), ids)
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
    for f in (_leer_sheet, _sis_sheet, _base_formalizacion,
              identidades):
        f.clear()
