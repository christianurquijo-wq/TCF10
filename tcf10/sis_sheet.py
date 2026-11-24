"""
Fuente del SIS desde la copia en Google Sheets de las vistas VTD10 (sin BigQuery).

Una pestaña por vista, con los mismos nombres de columna que en BigQuery. Este módulo replica en pandas lo que hacen
queries/avance_sis.sql, base_sis.sql, asistencia_sesiones.sql y progreso_cursos.sql.

Privacidad: de cada pestaña se conservan solo las columnas necesarias. Nombre, documento, correo y teléfono se
descartan al leer; del nombre solo quedan las iniciales.
"""
from __future__ import annotations

import re

import pandas as pd

PESTANAS = {
    "asis_det": "VTD10_student_attendance_detail",
    "asis_res": "VTD10_student_attendance_per_group_summary",
    "basica": "VTD10_student_basic_info",
    "login": "VTD10_student_login_activity",
    "prog_det": "VTD10_student_progress_detail",
    "prog_cur": "VTD10_student_progress_per_course_summary",
}
# Horas_Plataforma_Acreditadas = pedagogical_time (segundos) de VTD10_student_progress_detail / 3600, sumado por
# persona. Es la fuente oficial de las horas en plataforma (nov-2026); course_time_view queda solo como respaldo si
# la pestaña de detalle aún no trae esa columna.
COL_PEDAGOGICO = "pedagogical_time"
# Pestaña con el resultado de BigQuery vinculado (Connected Sheets): una fila por estudiante, grupo y materia, con
# horas_plataforma_acreditadas ya calculadas (regla de Looker) sobre el 100 % de VTD10_student_progress_detail.
# Si existe, es la fuente principal de horas en plataforma y de la última lección.
PESTANA_EST = ("Consulta por estudiante", "VTD10_student_progress_by_student")
COLUMNAS_EST = ["incremental", "horas_plataforma_acreditadas", "ultima_fecha_completada", "ultima_leccion",
                "ultimo_curso", "last_updated_statistics"]
VERSION = "2026-11-24 franjas +5h"  # cambia la llave del caché cuando cambia la preparación
# columnas que se conservan de cada pestaña (las demás, incluidos datos personales, se descartan)
COLUMNAS = {
    "asis_det": ["incremental", "group_name", "session_id", "session_number", "session_date", "attended",
                 "not_attended", "not_registered", "is_past_session", "last_updated_class_session"],
    "asis_res": ["incremental", "program_name", "group_name", "total_sessions", "attended_sessions",
                 "not_attended_sessions", "total_sessions_to_date",
                 "last_attendance_date", "last_updated_class_session"],
    "basica": ["user_incremental", "user_full_name", "program_name", "level_name"],
    "login": ["incremental", "log_date", "time_view"],
    "prog_det": ["incremental", "completed_date", "last_updated_statistics", "lesson_name", "course_name"],
    "prog_cur": ["incremental", "group_name", "group_start_date", "group_end_date", "course_name",
                 "course_completed_status", "lessons_active", "lessons_completed", "course_time_view",
                 "progress_status"],
}
OPCIONALES = {"login", "prog_det"}
SEGUNDOS_POR_HORA = 3600  # sin estas pestañas la app funciona (con menos precisión en «última actividad»)


class FaltaEstructura(Exception):
    pass


# ------------------------------------------------------------------ conversiones tolerantes
def _num(s: pd.Series) -> pd.Series:
    if s.dtype == object:
        s = s.map(lambda v: v.replace(",", ".") if isinstance(v, str) and v.count(",") == 1 and "." not in v else v)
    return pd.to_numeric(s, errors="coerce")


_DMY = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}")


def _una_fecha(v, a_bogota: bool = True) -> pd.Timestamp:
    if v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and not v.strip()):
        return pd.NaT
    try:
        if isinstance(v, (int, float)):
            return (pd.Timestamp("1899-12-30") + pd.to_timedelta(float(v), unit="D")
                    if 20000 <= v <= 80000 else pd.NaT)
        txt = str(v).strip()
        ts = pd.to_datetime(txt, dayfirst=True) if _DMY.match(txt) else pd.Timestamp(txt)
    except (ValueError, TypeError, OverflowError):
        return pd.NaT
    if ts.tzinfo is not None:  # TIMESTAMP de BigQuery (UTC) → hora de Bogotá, sin zona
        ts = ts.tz_convert("America/Bogota").tz_localize(None) if a_bogota else ts.tz_localize(None)
    return ts


def _fecha(s: pd.Series, a_bogota: bool = True) -> pd.Series:
    """Acepta serial de Sheets, ISO con o sin zona horaria (2026-11-13 08:00:00 UTC) o día/mes/año.
    Los DATETIME del SIS ya vienen en hora de Bogotá; los TIMESTAMP (UTC) se convierten a Bogotá."""
    valores = s.tolist()
    cache = {}
    for v in valores:  # las fechas se repiten mucho: se convierte cada valor distinto una sola vez
        k = (type(v), v) if not (isinstance(v, float) and pd.isna(v)) else ("nan",)
        if k not in cache:
            cache[k] = _una_fecha(v, a_bogota)
    convertidas = [cache[(type(v), v) if not (isinstance(v, float) and pd.isna(v)) else ("nan",)] for v in valores]
    return pd.to_datetime(pd.Series(convertidas, index=s.index, dtype=object),
                          errors="coerce").astype("datetime64[ns]")


def _bool(s: pd.Series) -> pd.Series:
    return pd.Series([v is True or (isinstance(v, (int, float)) and v == 1)
                      or (isinstance(v, str) and v.strip().upper() in {"TRUE", "VERDADERO", "1", "SI", "SÍ"})
                      for v in s.tolist()], index=s.index, dtype=bool)


def iniciales(nombre) -> str:
    partes = re.findall(r"[^\W\d_]+", str(nombre or ""))
    return "".join(p[0].upper() + "." for p in partes[:4])


# ------------------------------------------------------------------ lectura → tablas livianas (sin datos personales)
def preparar(crudas: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    faltan = [PESTANAS[k] for k in PESTANAS if k not in crudas and k not in OPCIONALES]
    if faltan:
        raise FaltaEstructura(f"Faltan pestañas del SIS en el Sheet: {', '.join(faltan)}.")
    t: dict[str, pd.DataFrame] = {}
    # Documento → ID SIS para cruzar con la base de Formalización. Se guarda solo la huella (hash) del documento.
    from tcf10.base_atenea import huella
    pares = []
    for clave in ("asis_res", "prog_cur", "asis_det", "prog_det", "prog_est"):
        df = crudas.get(clave)
        if df is not None and {"student_doc", "incremental"} <= set(df.columns):
            pares.append(pd.DataFrame({"huella": huella(df["student_doc"]),
                                       "id_sis": _num(df["incremental"])}).dropna().drop_duplicates())
    t["docs"] = (pd.concat(pares).drop_duplicates("huella") if pares
                 else pd.DataFrame(columns=["huella", "id_sis"]))
    # Franja de cada grupo: hora de inicio más frecuente de sus sesiones (columna opcional session_start_date).
    ad = crudas.get("asis_det")
    t["franjas"] = (franjas_por_grupo(ad["group_name"], ad["session_start_date"])
                    if ad is not None and {"group_name", "session_start_date"} <= set(ad.columns)
                    else pd.DataFrame(columns=["grupo", "franja"]))
    t["prog_ped"], filtrado = tiempo_pedagogico(crudas.get("prog_det"))
    t["prog_est"] = por_estudiante(crudas.get("prog_est"))
    t["meta"] = pd.DataFrame({"ped_filtrado": [filtrado]})
    for clave, cols in COLUMNAS.items():
        df = crudas.get(clave)
        if df is None:
            t[clave] = pd.DataFrame(columns=cols)
            continue
        sin = [c for c in cols if c not in df.columns]
        if sin:
            raise FaltaEstructura(f"A la pestaña «{PESTANAS[clave]}» le faltan columnas: {', '.join(sin)}.")
        t[clave] = df[cols].copy()

    b = t["basica"]
    b["iniciales"] = b.pop("user_full_name").map(iniciales)  # el nombre no sale de aquí
    b["id_sis"] = _num(b.pop("user_incremental")).astype("Int64")
    for k in ("asis_det", "asis_res", "login", "prog_det", "prog_cur", "prog_ped"):
        t[k]["id_sis"] = _num(t[k].pop("incremental")).astype("Int64")

    for c in ("session_date", "last_updated_class_session"):
        t["asis_det"][c] = _fecha(t["asis_det"][c])
    for c in ("attended", "not_attended", "not_registered", "session_number"):
        t["asis_det"][c] = _num(t["asis_det"][c]).fillna(0)
    t["asis_det"]["is_past_session"] = _bool(t["asis_det"]["is_past_session"])

    for c in ("last_attendance_date", "last_updated_class_session"):
        t["asis_res"][c] = _fecha(t["asis_res"][c])
    for c in ("total_sessions", "attended_sessions", "not_attended_sessions", "total_sessions_to_date"):
        t["asis_res"][c] = _num(t["asis_res"][c]).fillna(0)

    t["login"]["log_date"] = _fecha(t["login"]["log_date"])
    t["login"]["time_view"] = _num(t["login"]["time_view"]).fillna(0)
    for c in ("completed_date", "last_updated_statistics"):
        t["prog_det"][c] = _fecha(t["prog_det"][c])
    for c in ("group_start_date", "group_end_date"):
        t["prog_cur"][c] = _fecha(t["prog_cur"][c])
    for c in ("course_completed_status", "lessons_active", "lessons_completed", "course_time_view"):
        t["prog_cur"][c] = _num(t["prog_cur"][c])
    t["prog_cur"] = avance_por_lecciones(t["prog_cur"])
    t["prog_ped"][COL_PEDAGOGICO] = _num(t["prog_ped"][COL_PEDAGOGICO])
    return t


def avance_por_lecciones(pc: pd.DataFrame) -> pd.DataFrame:
    """Avance y estado de cada curso coherentes con las lecciones: completadas ÷ activas.

    nov-2026: course_completed_status del SIS podía marcar 100 % con 36 de 44 lecciones terminadas. Ahora el
    porcentaje (course_completed_status, 0-100) y progress_status se recalculan con las lecciones cuando
    lessons_active > 0; si el curso no reporta lecciones activas, se conserva lo que trae el SIS."""
    pc = pc.copy()
    act, comp = pc["lessons_active"], pc["lessons_completed"].fillna(0)
    con_lecciones = act.fillna(0) > 0
    pct = (comp / act.where(con_lecciones)).clip(0, 1) * 100
    pc["course_completed_status"] = pct.where(con_lecciones, pc["course_completed_status"].clip(0, 100))
    original = pc["progress_status"].astype("string").str.strip().str.lower()
    estado = pd.Series("sin_iniciar", index=pc.index, dtype="object")
    estado[(comp > 0) | original.isin(["en_progreso", "completado"]).fillna(False)] = "en_progreso"
    estado[comp >= act] = "completado"
    pc["progress_status"] = estado.where(con_lecciones, pc["progress_status"])
    return pc


def _col(df: pd.DataFrame, nombre: str):
    """Encabezado tolerante: «pedagogical_time», « Pedagogical_Time », «pedagogical time»…"""
    return next((c for c in df.columns if re.sub(r"[\s_]+", "_", str(c).strip().lower()) == nombre), None)


def tiempo_pedagogico(det: pd.DataFrame | None) -> tuple[pd.DataFrame, bool]:
    """Segundos acreditables por fila de VTD10_student_progress_detail, con la misma regla de Looker Studio:

        CASE WHEN component_category = "resource" AND is_completed = TRUE THEN pedagogical_time / 3600 ELSE 0 END

    Devuelve (incremental, pedagogical_time en segundos ya filtrado) y si se pudo aplicar el filtro (False si la
    pestaña no trae component_category o is_completed: entonces se suma todo el pedagogical_time y la app avisa)."""
    vacio = pd.DataFrame(columns=["incremental", COL_PEDAGOGICO])
    if det is None or "incremental" not in det.columns or _col(det, COL_PEDAGOGICO) is None:
        return vacio, False
    seg = _num(det[_col(det, COL_PEDAGOGICO)]).fillna(0)
    c_cat, c_comp = _col(det, "component_category"), _col(det, "is_completed")
    filtrado = c_cat is not None and c_comp is not None
    if filtrado:
        acreditable = det[c_cat].astype(str).str.strip().str.lower().eq("resource") & _bool(det[c_comp])
        seg = seg.where(acreditable, 0)
    return pd.DataFrame({"incremental": det["incremental"], COL_PEDAGOGICO: seg}), filtrado


def por_estudiante(est: pd.DataFrame | None) -> pd.DataFrame:
    """Pestaña «Consulta por estudiante»: solo las columnas que usa la app (nombre, documento, correo… se descartan)."""
    cols = ["id_sis", "horas", "ultima_fecha", "ultima_leccion", "ultimo_curso", "actualizado"]
    if est is None:
        return pd.DataFrame(columns=cols)
    origen = {c: _col(est, c) for c in COLUMNAS_EST}
    if origen["incremental"] is None or origen["horas_plataforma_acreditadas"] is None:
        return pd.DataFrame(columns=cols)
    g = lambda c: est[origen[c]] if origen[c] is not None else pd.Series([None] * len(est), index=est.index)  # noqa: E731
    df = pd.DataFrame({
        "id_sis": _num(g("incremental")).astype("Int64"),
        "horas": _num(g("horas_plataforma_acreditadas")).fillna(0),
        "ultima_fecha": _fecha(g("ultima_fecha_completada")),
        "ultima_leccion": g("ultima_leccion").astype("string").str.strip().replace("", pd.NA),
        "ultimo_curso": g("ultimo_curso").astype("string").str.strip().replace("", pd.NA),
        "actualizado": _fecha(g("last_updated_statistics")),
    })
    return df[df["id_sis"].notna()].reset_index(drop=True)


def ultima_leccion(t: dict[str, pd.DataFrame], pid: int):
    """(lección, fecha, curso) más reciente del participante, combinando la consulta por estudiante y el detalle."""
    cand = []
    e = t.get("prog_est")
    if e is not None and len(e):
        x = e[(e["id_sis"] == pid) & e["ultima_fecha"].notna()]
        cand += [(r.ultima_fecha, r.ultima_leccion, r.ultimo_curso) for r in x.itertuples()]
    d = t["prog_det"]
    x = d[(d["id_sis"] == pid) & d["completed_date"].notna()]
    cand += [(r["completed_date"], r.get("lesson_name"), r.get("course_name")) for _, r in x.iterrows()]
    if not cand:
        return None
    fecha, leccion, curso = max(cand, key=lambda c: c[0])
    texto = lambda v: "" if v is None or (not isinstance(v, str) and pd.isna(v)) else str(v)  # noqa: E731
    return (texto(leccion) or "Lección", fecha, texto(curso))


def horas_plataforma(t: dict[str, pd.DataFrame], ids, divisor_respaldo: float = SEGUNDOS_POR_HORA) -> pd.Series:
    """Horas_Plataforma_Acreditadas por ID SIS: suma de pedagogical_time (segundos) de VTD10_student_progress_detail
    en recursos completados (component_category = "resource" e is_completed = TRUE) / 3600.

    Si esa pestaña aún no trae pedagogical_time, usa el respaldo anterior
    (course_time_view de la pestaña por curso ÷ divisor_time_view)."""
    ids = set(int(i) for i in ids)
    est = t.get("prog_est")
    if est is not None and len(est):  # 1) consulta por estudiante (BigQuery vinculado, 100 % de los registros)
        x = est[est["id_sis"].isin(ids)]
        return x.groupby("id_sis")["horas"].sum(min_count=1).rename("horas_asinc")
    ped = t.get("prog_ped")
    if ped is not None and len(ped):  # 2) detalle exportado al Sheet
        x = ped[ped["id_sis"].isin(ids)]
        return (x.groupby("id_sis")[COL_PEDAGOGICO].sum(min_count=1) / SEGUNDOS_POR_HORA).rename("horas_asinc")
    pc = t["prog_cur"][t["prog_cur"]["id_sis"].isin(ids)]
    return (pc.groupby("id_sis")["course_time_view"].sum(min_count=1) / divisor_respaldo).rename("horas_asinc")


def fuente_plataforma(t: dict[str, pd.DataFrame]) -> str:
    est = t.get("prog_est")
    if est is not None and len(est):
        return "consulta_por_estudiante"
    ped = t.get("prog_ped")
    if ped is None or not len(ped):
        return "course_time_view"
    meta = t.get("meta")
    filtrado = bool(meta["ped_filtrado"].iloc[0]) if meta is not None and len(meta) else False
    return "pedagogical_time" if filtrado else "pedagogical_time_sin_filtro"


# ------------------------------------------------------------------ equivalentes de las consultas
def franja_de_hora(h: float) -> str:
    from tcf10 import config as C
    return "Sin dato" if pd.isna(h) else C.franja_de_hora(h)


def franjas_por_grupo(grupos: pd.Series, inicios: pd.Series) -> pd.DataFrame:
    """Franja oficial de cada grupo («Mañana · 8:00 a. m.», «Tarde · 1:00 p. m.», «Noche · 5:00 p. m.»), según la
    hora de inicio más común de sus sesiones (se asigna la franja oficial más cercana).
    La hora se toma tal como la muestra BigQuery (sin cambio de zona) y se corrige con C.DESFASE_HORA_SIS."""
    from tcf10 import config as C
    ini = _fecha(inicios, a_bogota=False) + pd.Timedelta(hours=C.DESFASE_HORA_SIS)
    df = pd.DataFrame({"grupo": grupos.astype("string"), "hora": ini.dt.strftime("%H:%M"),
                       "h": ini.dt.hour + ini.dt.minute / 60})
    df = df.dropna(subset=["grupo", "hora"])
    if df.empty:
        return pd.DataFrame(columns=["grupo", "franja"])
    moda = df.groupby(["grupo", "hora", "h"]).size().reset_index(name="n").sort_values("n", ascending=False)
    moda = moda.drop_duplicates("grupo")
    from tcf10 import config as C
    moda["franja"] = [C.etiqueta_franja(franja_de_hora(h)) for h in moda["h"]]
    return moda[["grupo", "franja"]].reset_index(drop=True)


def actualizado(t: dict[str, pd.DataFrame]) -> pd.Timestamp:
    """La fuente más antigua de las que alimentan la app (así no se sobreestima la frescura)."""
    progreso = [t["prog_det"]["last_updated_statistics"].max()]
    if t.get("prog_est") is not None and len(t["prog_est"]):
        progreso.append(t["prog_est"]["actualizado"].max())
    progreso = [m for m in progreso if pd.notna(m)]
    marcas = [t["asis_det"]["last_updated_class_session"].max(), max(progreso) if progreso else pd.NaT]
    marcas = [m for m in marcas if pd.notna(m)]
    return min(marcas) if marcas else pd.NaT


def avance(t: dict[str, pd.DataFrame], ids, horas_sesion: float, divisor_tiempo: float) -> pd.DataFrame:
    ids = set(int(i) for i in ids)
    ar = t["asis_res"][t["asis_res"]["id_sis"].isin(ids)]
    asis = ar.groupby("id_sis").agg(sesiones_asistidas=("attended_sessions", "sum"),
                                    sesiones_inasistidas=("not_attended_sessions", "sum"),
                                    sesiones_a_la_fecha=("total_sessions_to_date", "sum"),
                                    sesiones_totales=("total_sessions", "sum"),
                                    ultima_asistencia=("last_attendance_date", "max"))
    grupo = (ar.sort_values("total_sessions", ascending=False).dropna(subset=["group_name"])
               .drop_duplicates("id_sis").set_index("id_sis")["group_name"].rename("grupo_sis"))
    asinc = horas_plataforma(t, ids, divisor_tiempo)  # Horas_Plataforma_Acreditadas
    ult_comp = t["prog_det"][t["prog_det"]["id_sis"].isin(ids)].groupby("id_sis")["completed_date"].max()
    est = t.get("prog_est")
    if est is not None and len(est):
        ult_est = est[est["id_sis"].isin(ids)].groupby("id_sis")["ultima_fecha"].max()
        ult_comp = pd.concat([ult_comp, ult_est], axis=1).max(axis=1)
    ult_login = t["login"][t["login"]["id_sis"].isin(ids)].groupby("id_sis")["log_date"].max()

    df = pd.concat([asis, grupo, asinc, ult_comp.rename("ultimo_completado"),
                    ult_login.rename("ultimo_ingreso")], axis=1)
    df.index.name = "id_sis"
    df = df.reset_index()
    if df.empty:
        return pd.DataFrame(columns=["id_sis", "horas_sinc", "horas_asinc", "ultima_actividad", "grupo_sis",
                                     "actualizado_sis", "sesiones_asistidas", "sesiones_registradas",
                                     "sesiones_a_la_fecha", "sesiones_totales", "ultima_plataforma"])
    df["horas_sinc"] = (df["sesiones_asistidas"].fillna(0) * horas_sesion).round(2)
    df["horas_asinc"] = df["horas_asinc"].fillna(0).round(2)
    df["ultima_actividad"] = df[["ultima_asistencia", "ultimo_completado", "ultimo_ingreso"]].max(axis=1)
    df["ultima_plataforma"] = df[["ultimo_completado", "ultimo_ingreso"]].max(axis=1)  # sin contar clases
    df["actualizado_sis"] = actualizado(t)
    df["sesiones_asistidas"] = df["sesiones_asistidas"].fillna(0)
    df["sesiones_registradas"] = df["sesiones_asistidas"] + df["sesiones_inasistidas"].fillna(0)
    df["sesiones_a_la_fecha"] = df["sesiones_a_la_fecha"].fillna(0)
    return df[["id_sis", "horas_sinc", "horas_asinc", "ultima_actividad", "grupo_sis", "actualizado_sis",
               "sesiones_asistidas", "sesiones_registradas", "sesiones_a_la_fecha", "sesiones_totales",
               "ultima_plataforma"]]


def calendario_grupos(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Inicio y fin de cada grupo: fechas del grupo en el SIS; si faltan, primera y última sesión programada."""
    pc = t["prog_cur"].groupby("group_name").agg(ini=("group_start_date", "min"), fin=("group_end_date", "max"))
    ad = t["asis_det"].groupby("group_name").agg(ini_s=("session_date", "min"), fin_s=("session_date", "max"))
    cal = pc.join(ad, how="outer")
    cal["fecha_inicio"] = cal["ini"].fillna(cal["ini_s"]).dt.normalize()
    cal["fecha_fin"] = cal["fin"].fillna(cal["fin_s"]).dt.normalize()
    return cal[["fecha_inicio", "fecha_fin"]]


def base(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Mismo formato que queries/base_sis.sql: id_sis, iniciales, perfil, nivel, grupo, fecha_inicio, fecha_fin."""
    b = t["basica"].dropna(subset=["id_sis"]).drop_duplicates("id_sis").set_index("id_sis")
    otros = pd.Index(t["asis_res"]["id_sis"].dropna().unique()).union(t["prog_cur"]["id_sis"].dropna().unique())
    b = b.reindex(b.index.union(otros))
    prog = t["asis_res"].dropna(subset=["id_sis"]).drop_duplicates("id_sis").set_index("id_sis")["program_name"]
    b["program_name"] = b["program_name"].fillna(prog)
    av = avance(t, b.index, 0, 1).set_index("id_sis")
    reciente = (t["prog_cur"].sort_values("group_start_date", ascending=False).dropna(subset=["id_sis"])
                  .drop_duplicates("id_sis").set_index("id_sis")["group_name"])
    b["grupo"] = av["grupo_sis"].reindex(b.index).fillna(reciente.reindex(b.index))
    cal = calendario_grupos(t)
    b = b.join(cal, on="grupo")
    b.index.name = "id_sis"
    return (b.reset_index()
             .rename(columns={"program_name": "perfil", "level_name": "nivel"})
             [["id_sis", "iniciales", "perfil", "nivel", "grupo", "fecha_inicio", "fecha_fin"]])


def agregados(t: dict[str, pd.DataFrame], ids) -> tuple[pd.DataFrame, pd.DataFrame]:
    ids = set(int(i) for i in ids)
    d = t["asis_det"]
    d = d[d["is_past_session"] & d["id_sis"].isin(ids)]
    asis = (d.groupby(["group_name", "session_id"], as_index=False)
              .agg(sesion=("session_number", "first"), fecha=("session_date", "first"),
                   convocados=("id_sis", "nunique"), asistieron=("attended", "sum"),
                   no_asistieron=("not_attended", "sum"), sin_registro=("not_registered", "sum"),
                   actualizado=("last_updated_class_session", "max"))
              .rename(columns={"group_name": "grupo"}))
    p = t["prog_cur"][t["prog_cur"]["id_sis"].isin(ids)].copy()
    for e in ("completado", "en_progreso", "sin_iniciar"):
        p[e] = p["progress_status"].eq(e).astype(int)
    prog = (p.groupby(["group_name", "course_name"], as_index=False)
              .agg(estudiantes=("id_sis", "nunique"), completado=("completado", "sum"),
                   en_progreso=("en_progreso", "sum"), sin_iniciar=("sin_iniciar", "sum"),
                   avance_promedio=("course_completed_status", "mean"),
                   lecciones=("lessons_completed", "sum"), activas=("lessons_active", "sum"))
              .rename(columns={"group_name": "grupo", "course_name": "curso"}))
    prog["avance_promedio"] = prog["avance_promedio"] / 100
    prog["pct_lecciones"] = prog["lecciones"] / prog["activas"].where(prog["activas"] > 0)
    return asis, prog.drop(columns=["lecciones", "activas"])
