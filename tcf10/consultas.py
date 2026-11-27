"""
Asistente de datos de la vista interna (nov-2026): consultas puntuales del equipo con cifra y CSV.

Sin IA: el equipo elige un atajo (consulta frecuente) o arma la suya en el constructor (qué quiere + filtros). Todo
sale de la misma tabla que usa la vista interna (ui._preparado → metrics.preparar/tipificar/feedback), así que las
cifras coinciden con las páginas. Este módulo no usa Streamlit: se prueba con pytest (tests/test_consultas.py).

Tipos de consulta
  lista        una fila por persona (cifra + CSV con contacto)
  faltas       una fila por persona × sesión a la que no asistió, en un rango de fechas
  asis_grupos  asistencia por grupo × sesión (tabla)
  resumen      una fila por cohorte / grupo / docente / franja / programa y nivel / gestor
  distribucion conteo cruzado de una dimensión por estado, ruta o Feedbacks

Privacidad: la discapacidad es un dato sensible. Con un filtro o una dimensión sensible solo se permiten conteos
agregados (resumen o distribución) y los conteos de 1 a 4 se muestran como «< 5»; nunca listas de personas.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from tcf10 import config as C

MIN_CELDA_SENSIBLE = 5
SENSIBLES = ("discapacidad", "tipo_discapacidad")

# ------------------------------------------------------------------ columnas (nombre interno → encabezado del CSV)
CAMPOS = {
    "documento": "Documento", "tipo_documento": "Tipo de documento", "nombre_completo": "Nombre",
    "telefono": "Teléfono", "correo": "Correo",
    "cohorte": "Cohorte", "perfil": "Programa", "nivel": "Nivel", "grupo": "Grupo", "franja": "Franja",
    "docente": "Docente", "gestor": "Gestor",
    "riesgo": "Estado", "icp_pct": "ICP (%)", "horas_validas": "Horas completadas",
    "horas_sinc_val": "Horas en clases (sincrónico)", "horas_asinc_val": "Horas en plataforma (asincrónico)",
    "sesiones_asistidas": "Clases asistidas", "sesiones_a_la_fecha": "Clases dictadas a la fecha",
    "sesiones_restantes": "Clases que quedan", "tipo_ruta": "Ruta para aprobar", "clases_faltantes": "Clases que le faltan",
    "faltan_plataforma_h": "Horas de plataforma que le faltan", "faltan_h": "Horas que le faltan para 63 h",
    "ultima_actividad": "Última actividad", "dias_sin_actividad": "Días sin actividad",
    "ultima_plataforma": "Último ingreso a plataforma", "dias_sin_plataforma": "Días sin entrar a plataforma",
    "critico": "Caso crítico", "motivo_critico": "Motivo del caso crítico",
    "feedbacks_hechos": "Feedbacks hechos", "feedbacks_meta": "Feedbacks esperados a hoy",
    "estado_feedback": "Estado de Feedbacks", "sexo": "Sexo", "estrato": "Estrato", "nivel_educativo": "Nivel educativo",
    # faltas
    "sesion": "Sesión", "fecha": "Fecha de la sesión", "estado_asistencia": "Asistencia",
}
CONTACTO = ["documento", "tipo_documento", "nombre_completo", "telefono", "correo"]
UBICACION = ["cohorte", "perfil", "nivel", "grupo", "franja", "docente", "gestor"]
AVANCE = ["riesgo", "icp_pct", "horas_validas", "horas_sinc_val", "horas_asinc_val", "sesiones_asistidas",
          "ultima_actividad", "dias_sin_actividad"]
COLUMNAS_LISTA = [c for c in CAMPOS if c not in ("sesion", "fecha", "estado_asistencia")]
COLUMNAS_BASE = CONTACTO + UBICACION + AVANCE   # columnas por defecto de una lista del constructor

# ------------------------------------------------------------------ universos y filtros
UNIVERSOS = {
    "en_curso": "En curso (grupo iniciado, sin aprobar aún)",
    "activos": "Formalizados activos (no retirados)",
    "formalizados": "Todos los formalizados (incluye retirados)",
    "todos": "Toda la base (incluye no formalizados)",
}
FILTROS_CAT = [("cohorte", "Cohorte"), ("perfil", "Programa"), ("nivel", "Nivel"), ("grupo", "Grupo"),
               ("franja", "Franja"), ("docente", "Docente"), ("gestor", "Gestor"), ("riesgo", "Estado"),
               ("tipo_ruta", "Ruta para aprobar"), ("estado_feedback", "Feedbacks"), ("sexo", "Sexo"),
               ("estrato", "Estrato"), ("nivel_educativo", "Nivel educativo"), ("discapacidad", "Discapacidad")]
FILTROS_BOOL = [("critico", "Caso crítico"), ("sin_plataforma", f"Sin uso de plataforma ({C.DIAS_SIN_PLATAFORMA}+ días)"),
                ("no_alcanza", "No alcanza el 70 %"), ("critico_feedback", "Atrasado en Feedbacks"),
                ("sin_sis", "Sin usuario en el SIS")]
FILTROS_RANGO = [("horas_validas", "Horas completadas", 0.0, float(C.HORAS_TOTALES)),
                 ("horas_sinc_val", "Horas en clases", 0.0, float(C.HORAS_SINCRONICAS)),
                 ("horas_asinc_val", "Horas en plataforma", 0.0, float(C.HORAS_ASINCRONICAS)),
                 ("icp_pct", "ICP (%)", 0.0, 200.0),
                 ("sesiones_asistidas", "Clases asistidas", 0.0, 20.0),
                 ("dias_sin_actividad", "Días sin actividad", 0.0, 120.0),
                 ("dias_sin_plataforma", "Días sin entrar a plataforma", 0.0, 120.0),
                 ("faltan_h", "Horas que le faltan para 63 h", 0.0, float(C.HORAS_CULMINACION))]
FILTROS_FECHA = [("ultima_actividad", "Última actividad"), ("ultima_plataforma", "Último ingreso a plataforma")]
ETIQUETA = dict(FILTROS_CAT + [(k, v) for k, v in FILTROS_BOOL] + [(k, v) for k, v, *_ in FILTROS_RANGO]
                + FILTROS_FECHA)

POR_RESUMEN = {"cohorte": ["cohorte"], "programa_nivel": ["perfil", "nivel"], "grupo": ["cohorte", "grupo"],
               "docente": ["docente"], "gestor": ["gestor"], "franja": ["franja"]}
ETIQ_RESUMEN = {"cohorte": "Cohorte", "programa_nivel": "Programa y nivel", "grupo": "Grupo", "docente": "Docente",
                "gestor": "Gestor", "franja": "Franja"}
DIM_DISTRIBUCION = ["cohorte", "perfil", "nivel", "grupo", "franja", "docente", "gestor", "sexo", "estrato",
                    "nivel_educativo", "discapacidad"]
COL_DISTRIBUCION = {"riesgo": "Estado", "tipo_ruta": "Ruta para aprobar", "estado_feedback": "Feedbacks"}
ORDEN_RUTA = ["Solo plataforma", "1 clase + plataforma", "2 clases + plataforma", "No alcanza", "Ya aprobó"]
ORDEN_FEEDBACK = ["Al día", "1 pendiente", "2 pendientes", "3 o más pendientes", "Aún no aplica"]


@dataclass
class Filtros:
    universo: str = "en_curso"
    cat: dict[str, list[str]] = field(default_factory=dict)       # columna → valores aceptados
    si: dict[str, bool] = field(default_factory=dict)              # columna booleana → True / False
    rango: dict[str, tuple[float, float]] = field(default_factory=dict)
    fecha: dict[str, tuple[str, object]] = field(default_factory=dict)  # columna → ("antes" | "desde", fecha)

    def sensible(self) -> bool:
        return any(self.cat.get(c) for c in SENSIBLES)


# ------------------------------------------------------------------ preparación y filtrado
def preparar_base(df: pd.DataFrame) -> pd.DataFrame:
    """Columnas derivadas que usa el asistente (ICP en %, sin usuario en el SIS) y columnas faltantes vacías."""
    df = df.copy()
    df["icp_pct"] = (pd.to_numeric(df.get("pct_esperado"), errors="coerce") * 100).round(0)
    df["sin_sis"] = (df["en_sis"].eq(False) & df["enrolado"] & ~df["retirado"]) if "en_sis" in df \
        else pd.Series(False, index=df.index)
    for c in COLUMNAS_LISTA:
        if c not in df and c not in CONTACTO:
            df[c] = np.nan
    for c, *_ in FILTROS_BOOL:
        df[c] = df[c].fillna(False).astype(bool) if c in df else False
    return df


def universo(df: pd.DataFrame, clave: str) -> pd.DataFrame:
    if clave == "todos":
        return df
    if clave == "formalizados":
        return df[df["enrolado"]]
    activos = df[df["enrolado"] & ~df["retirado"]]
    if clave == "activos":
        return activos
    return activos[activos["cohorte_iniciada"] & ~activos["cohorte_cerrada"] & ~activos["culmino"]]


def aplicar(df: pd.DataFrame, f: Filtros) -> pd.DataFrame:
    """Universo + todos los filtros (se combinan con «y»; dentro de un filtro de lista, con «o»)."""
    d = universo(df, f.universo)
    for col, valores in f.cat.items():
        if valores and col in d:
            d = d[d[col].astype(str).isin([str(v) for v in valores])]
    for col, valor in f.si.items():
        if col in d and valor is not None:
            d = d[d[col].fillna(False).astype(bool) == bool(valor)]
    for col, (lo, hi) in f.rango.items():
        if col in d:
            v = pd.to_numeric(d[col], errors="coerce")
            d = d[v.between(lo, hi)]
    for col, (modo, dia) in f.fecha.items():
        if col in d and dia is not None:
            v = pd.to_datetime(d[col], errors="coerce").dt.normalize()
            dia = pd.Timestamp(dia).normalize()
            # «antes»: sin actividad desde ese día (última antes del día, o nunca); «desde»: con actividad desde ese día
            d = d[v.isna() | (v < dia)] if modo == "antes" else d[v >= dia]
    return d


def describir(f: Filtros) -> str:
    """Filtros en texto (para el pie del resultado, el nombre del registro y la bitácora de descargas)."""
    partes = [UNIVERSOS.get(f.universo, f.universo).split(" (")[0]]
    for col, valores in f.cat.items():
        if valores:
            partes.append(f"{ETIQUETA.get(col, col)}: {', '.join(map(str, valores))}")
    for col, valor in f.si.items():
        if valor is not None:
            partes.append(ETIQUETA.get(col, col) if valor else f"No: {ETIQUETA.get(col, col).lower()}")
    for col, (lo, hi) in f.rango.items():
        partes.append(f"{ETIQUETA.get(col, col)} entre {_num(lo)} y {_num(hi)}")
    for col, (modo, dia) in f.fecha.items():
        if dia is not None:
            texto = "sin registro desde" if modo == "antes" else "desde"
            partes.append(f"{ETIQUETA.get(col, col)}: {texto} el {pd.Timestamp(dia):%d/%m/%Y}")
    return " · ".join(partes)


def _num(x: float) -> str:
    return (f"{x:,.1f}".rstrip("0").rstrip(".") if x % 1 else f"{x:,.0f}").replace(",", "X").replace(".", ",") \
        .replace("X", ".")


# ------------------------------------------------------------------ resultados
def lista(d: pd.DataFrame, columnas: list[str], orden: list[str] | None = None, asc: bool | list[bool] = True
          ) -> pd.DataFrame:
    """Personas con las columnas pedidas (en ese orden), ordenadas. Columnas que no existan se omiten."""
    cols = [c for c in columnas if c in d]
    orden = [c for c in (orden or []) if c in d]
    if orden:
        d = d.sort_values(orden, ascending=asc if isinstance(asc, bool) else asc[:len(orden)], na_position="last")
    return d[cols].reset_index(drop=True)


def resumen(d: pd.DataFrame, por: str) -> pd.DataFrame:
    """Una fila por grupo de la dimensión elegida, con las cifras clave (mismas definiciones de la vista interna)."""
    llaves = POR_RESUMEN[por]
    if d.empty:
        return pd.DataFrame(columns=[CAMPOS.get(k, k) for k in llaves])
    x = d.copy()
    x["_activo"] = x["enrolado"] & ~x["retirado"]
    x["_en_curso"] = x["_activo"] & x["cohorte_iniciada"] & ~x["cohorte_cerrada"] & ~x["culmino"]
    x["_icp"] = pd.to_numeric(x["pct_esperado"], errors="coerce").where(x["_en_curso"])
    for k in llaves:
        x[k] = x[k].fillna("Sin dato").astype(str)
    g = x.groupby(llaves, dropna=False)
    t = pd.DataFrame({
        "Personas": g.size(),
        "Formalizados activos": g["_activo"].sum(),
        "En curso": g["_en_curso"].sum(),
        "Aprobados": g["culmino"].sum(),
        "Casos críticos": g["critico"].sum(),
        "Horas completadas (promedio)": g["horas_validas"].mean().round(1),
        "Horas en plataforma (promedio)": g["horas_asinc_val"].mean().round(1),
        "ICP promedio en curso (%)": (g["_icp"].mean() * 100).round(0),
        "% asistencia": (g["sesiones_asistidas"].sum() / g["sesiones_registradas"].sum().where(
            g["sesiones_registradas"].sum() > 0) * 100).round(1),
    }).reset_index()
    t = t.rename(columns={k: CAMPOS.get(k, k) for k in llaves})
    for c in ("Formalizados activos", "En curso", "Aprobados", "Casos críticos"):
        t[c] = t[c].astype(int)
    total = {CAMPOS.get(llaves[0], llaves[0]): "Total"}
    total.update({c: int(t[c].sum()) for c in ("Personas", "Formalizados activos", "En curso", "Aprobados",
                                               "Casos críticos")})
    total["Horas completadas (promedio)"] = round(float(x["horas_validas"].mean()), 1)
    total["Horas en plataforma (promedio)"] = round(float(x["horas_asinc_val"].mean()), 1)
    icp = x["_icp"].mean()
    total["ICP promedio en curso (%)"] = None if pd.isna(icp) else round(float(icp) * 100)
    reg = x["sesiones_registradas"].sum()
    total["% asistencia"] = round(float(x["sesiones_asistidas"].sum() / reg * 100), 1) if reg else None
    return pd.concat([t, pd.DataFrame([total])], ignore_index=True)


def distribucion(d: pd.DataFrame, dim: str, por: str, sensible: bool = False) -> pd.DataFrame:
    """Conteo de personas por `dim` (filas) y `por` (columnas: estado, ruta o Feedbacks), con totales.
    Si es sensible (dimensión o filtro de discapacidad), los conteos de 1 a 4 se muestran como «< 5»."""
    sensible = sensible or dim in SENSIBLES
    x = d.copy()
    x[dim] = x[dim].fillna("Sin dato").astype(str)
    x[por] = x[por].fillna("Sin dato").astype(str)
    t = pd.crosstab(x[dim], x[por])
    orden = {"riesgo": C.ORDEN_ESTADOS, "tipo_ruta": ORDEN_RUTA, "estado_feedback": ORDEN_FEEDBACK}.get(por, [])
    t = t[[c for c in orden if c in t] + [c for c in t.columns if c not in orden]]
    t["Total"] = t.sum(axis=1)
    t.loc["Total"] = t.sum()
    t.index.name = CAMPOS.get(dim, dim)
    t = t.reset_index()
    t.columns.name = None
    if sensible:
        for c in t.columns[1:]:
            t[c] = [f"< {MIN_CELDA_SENSIBLE}" if 0 < int(v) < MIN_CELDA_SENSIBLE else int(v) for v in t[c]]
    return t


def faltas(det: pd.DataFrame, personas: pd.DataFrame, desde, hasta, sesiones: list | None = None,
           incluir_sin_registro: bool = False) -> pd.DataFrame:
    """Una fila por persona × sesión a la que no asistió entre `desde` y `hasta` (incluidos), solo de `personas`
    (ya filtradas). det: data.asistencia_detalle (id_sis, grupo, sesion, fecha, estado_asistencia)."""
    estados = ["No asistió"] + (["Sin registro"] if incluir_sin_registro else [])
    x = det[det["id_sis"].isin(personas["id_sis"].dropna().astype(int))].copy()
    fecha = pd.to_datetime(x["fecha"], errors="coerce").dt.normalize()
    x = x[fecha.between(pd.Timestamp(desde).normalize(), pd.Timestamp(hasta).normalize())
          & x["estado_asistencia"].isin(estados)]
    if sesiones:
        x = x[x["sesion"].isin(sesiones)]
    info = personas.drop(columns=[c for c in ("grupo",) if c in personas]).drop_duplicates("id_sis")
    return x.merge(info, on="id_sis", how="left").sort_values(["grupo", "fecha", "sesion"])


def asistencia_grupos(asis: pd.DataFrame, grupos: set, desde, hasta) -> pd.DataFrame:
    """Asistencia por grupo × sesión (data.agregados) entre dos fechas, para los grupos del filtro."""
    a = asis[asis["grupo"].isin(grupos)].copy()
    fecha = pd.to_datetime(a["fecha"], errors="coerce").dt.normalize()
    a = a[fecha.between(pd.Timestamp(desde).normalize(), pd.Timestamp(hasta).normalize())]
    reg = (a["asistieron"] + a["no_asistieron"]).where(lambda s: s > 0)
    t = pd.DataFrame({"Grupo": a["grupo"], "Sesión": a["sesion"], "Fecha": pd.to_datetime(a["fecha"]).dt.date,
                      "Convocados": a["convocados"], "Asistieron": a["asistieron"],
                      "No asistieron": a["no_asistieron"], "Sin registro": a["sin_registro"],
                      "% asistencia (de los registrados)": (a["asistieron"] / reg * 100).round(1)})
    return t.sort_values(["Grupo", "Fecha", "Sesión"]).reset_index(drop=True)


# ------------------------------------------------------------------ exportación
def para_csv(t: pd.DataFrame) -> pd.DataFrame:
    """Encabezados legibles, Sí/No en vez de True/False, fechas dd/mm/aaaa y decimales a 1 cifra."""
    t = t.copy()
    for c in t.columns:
        s = t[c]
        if s.dtype == bool or (s.dtype == object and s.dropna().map(type).eq(bool).all() and s.notna().any()):
            t[c] = s.map({True: "Sí", False: "No"})
        elif pd.api.types.is_datetime64_any_dtype(s):
            t[c] = s.dt.strftime("%d/%m/%Y")
        elif pd.api.types.is_float_dtype(s):
            t[c] = s.round(1)
    return t.rename(columns={c: CAMPOS.get(c, c) for c in t.columns})


def a_csv(t: pd.DataFrame) -> bytes:
    """CSV que Excel en español abre bien: «;» como separador, coma decimal y UTF-8 con BOM (tildes)."""
    return t.to_csv(sep=";", index=False, decimal=",").encode("utf-8-sig")


# ------------------------------------------------------------------ atajos (consultas frecuentes)
@dataclass
class Atajo:
    clave: str
    grupo: str
    titulo: str
    pregunta: str          # cómo lo pediría el equipo (se muestra como el mensaje del usuario)
    tipo: str              # lista | faltas | asis_grupos | resumen | distribucion
    definicion: str
    filtros: Filtros = field(default_factory=Filtros)
    columnas: list[str] = field(default_factory=lambda: list(COLUMNAS_BASE))
    orden: list[str] = field(default_factory=list)
    asc: bool | list[bool] = True
    parametro: str = ""    # dato extra que pide el atajo: fecha_sin_actividad | estados | feedbacks | rango_fechas | por | dim


_RUTA_COLS = CONTACTO + UBICACION + ["tipo_ruta", "clases_faltantes", "faltan_plataforma_h", "horas_validas",
                                     "horas_sinc_val", "horas_asinc_val", "sesiones_asistidas", "sesiones_restantes",
                                     "ultima_plataforma", "dias_sin_plataforma", "riesgo", "icp_pct"]


def _ruta(clave: str, ruta: str, titulo: str, definicion: str) -> Atajo:
    return Atajo(clave, "Listas de seguimiento", titulo, f"Necesito la lista de estudiantes en «{ruta}»", "lista",
                 definicion, Filtros("en_curso", cat={"tipo_ruta": [ruta]}), _RUTA_COLS,
                 ["faltan_plataforma_h", "grupo"])


ATAJOS: list[Atajo] = [
    _ruta("solo_plataforma", "Solo plataforma", "Solo les falta plataforma",
          "En curso que ya asistieron a 2 clases o más: completando la plataforma (58,5 h) llegan a las 63 h del 70 %. "
          "Ordenados de menor a mayor por las horas de plataforma que les faltan."),
    _ruta("una_clase", "1 clase + plataforma", "Les falta 1 clase + plataforma",
          "En curso que han asistido a 1 clase: necesitan 1 clase más y completar la plataforma para llegar a 63 h."),
    _ruta("dos_clases", "2 clases + plataforma", "Les faltan 2 clases + plataforma",
          "En curso sin clases asistidas: necesitan 2 clases y completar la plataforma para llegar a 63 h."),
    Atajo("no_alcanza", "Listas de seguimiento", "No alcanzan el 70 %",
          "¿Quiénes ya no alcanzan a aprobar?", "lista",
          "En curso a los que les faltan más clases de las que quedan en su grupo: aunque completen la plataforma no "
          "llegan a 63 h.", Filtros("en_curso", si={"no_alcanza": True}),
          CONTACTO + UBICACION + ["clases_faltantes", "sesiones_restantes", "horas_validas", "horas_sinc_val",
                                  "horas_asinc_val", "riesgo", "icp_pct", "ultima_actividad"], ["grupo"]),
    Atajo("criticos", "Listas de seguimiento", "Casos críticos y su motivo",
          "Dame los casos críticos con el motivo", "lista",
          f"En curso con al menos una alerta: {C.DIAS_SIN_PLATAFORMA}+ días sin plataforma (o 0 h), no alcanza el 70 % o "
          f"{C.FEEDBACK_ATRASO_CRITICO}+ Feedbacks pendientes. Igual que «Grupos y casos críticos».",
          Filtros("en_curso", si={"critico": True}),
          CONTACTO + UBICACION + ["motivo_critico", "riesgo", "icp_pct", "horas_validas", "horas_asinc_val",
                                  "dias_sin_plataforma", "feedbacks_hechos", "feedbacks_meta"], ["grupo"]),
    Atajo("sin_actividad", "Listas de seguimiento", "Sin actividad desde una fecha",
          "¿Quiénes no han tenido actividad desde…?", "lista",
          "En curso cuya última actividad (clase o plataforma) es anterior a la fecha que elijas, o que nunca han "
          "tenido actividad.", Filtros("en_curso"),
          CONTACTO + UBICACION + ["ultima_actividad", "dias_sin_actividad", "ultima_plataforma", "horas_validas",
                                  "riesgo", "icp_pct"], ["dias_sin_actividad"], False, "fecha_sin_actividad"),
    Atajo("sin_sis", "Listas de seguimiento", "Formalizados sin usuario en el SIS",
          "¿Quiénes están formalizados pero no tienen usuario en la plataforma?", "lista",
          "Formalizados activos cuyo documento no aparece en el SIS: no pueden registrar asistencia ni avance.",
          Filtros("activos", si={"sin_sis": True}), CONTACTO + UBICACION, ["cohorte", "grupo"]),
    Atajo("por_estado", "Listas de seguimiento", "Lista por estado",
          "Necesito la lista de los que están en un estado", "lista",
          "Estado del participante igual al de la vista interna: 5 estados de formación según el ICP (grupo en "
          "curso) o estado final (Aprobado, No aprobado, Abandono), Por iniciar o No formalizado.",
          Filtros("todos"), CONTACTO + UBICACION + AVANCE, ["riesgo", "grupo"], parametro="estados"),
    Atajo("feedbacks", "Listas de seguimiento", "Feedbacks pendientes",
          "¿Quiénes deben Feedbacks?", "lista",
          "En curso con Feedbacks pendientes frente a uno por clase dictada a su grupo (la clase de hoy aún no se "
          "exige).", Filtros("en_curso"),
          CONTACTO + UBICACION + ["estado_feedback", "feedbacks_hechos", "feedbacks_meta", "riesgo"],
          ["estado_feedback", "grupo"], False, "feedbacks"),
    Atajo("faltas", "Asistencia y sesiones", "Quién faltó a clase",
          "¿Quién faltó a clase en estas fechas?", "faltas",
          "Una fila por persona y sesión a la que no asistió en el rango de fechas (opcional: incluir las sesiones sin "
          "registro del docente). Puedes acotar por grupo, franja, docente… en «Más filtros».",
          Filtros("activos"), [], parametro="rango_fechas"),
    Atajo("asis_grupos", "Asistencia y sesiones", "Asistencia por grupo y fecha",
          "Muéstrame la asistencia por grupo y fecha", "asis_grupos",
          "Cada sesión de cada grupo con convocados, asistentes, inasistentes y sin registro. El % es sobre los "
          "registrados.", Filtros("activos"), [], parametro="rango_fechas"),
    Atajo("resumen", "Cifras y tablas", "Resumen por cohorte, grupo, docente…",
          "Dame las cifras por grupo", "resumen",
          "Personas, formalizados activos, en curso, aprobados, casos críticos, horas promedio, ICP promedio y "
          "% de asistencia, con fila de total.", Filtros("todos"), [], parametro="por"),
    Atajo("distribucion", "Cifras y tablas", "Distribución por estado o ruta",
          "¿Cuántos hay en cada estado por cohorte?", "distribucion",
          "Conteo cruzado: filas por la dimensión que elijas y columnas por estado, ruta o Feedbacks. En "
          "discapacidad los conteos menores de 5 se muestran como «< 5».", Filtros("formalizados"), [], parametro="dim"),
]
POR_CLAVE = {a.clave: a for a in ATAJOS}
