"""
Base de beneficiarios TCF10: «DB Formalización TCF10» (Google Sheet en vivo, [tcf10] sheet_id).

Formato real de la hoja (pestaña «Formalización TCF10»):
  - La fila 1 trae marcas («Actualizar»); los encabezados están en la fila que contiene NUMERO_DOCUMENTO.
  - No trae ID SIS: el cruce con el SIS es por NUMERO_DOCUMENTO = student_doc de las vistas VTD10.
  - COHORTE: «Cohorte 1», «Cohorte 2» o «No aplica» (no formalizados).
  - RESULTADO OPERADOR: Formalizado / No Formalizado / Desistido.

Privacidad: la hoja trae nombres, documentos, correos, teléfonos, dirección y discapacidad. Aquí solo se
conservan las columnas que usa el tablero; del nombre quedan las iniciales y el documento se usa solo para
cruzar con el SIS y se descarta enseguida.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

# columna interna -> encabezados aceptados (comparados sin tildes, mayúsculas ni espacios)
COLUMNAS = {
    "documento": ["NUMERO_DOCUMENTO"],
    "cohorte": ["COHORTE"],
    "resultado": ["RESULTADO OPERADOR - Formalizado. - No formalizado. - Desistido", "RESULTADO OPERADOR"],
    "tematica": ["TEMÁTICA", "NOMBRE_CURSO_ASIGNADO", "NOMBRE_CURSO_INSCRITO"],
    "nivel": ["NIVEL_CURSO_ASIGNADO", "NIVEL_CURSO_INSCRITO"],
    "trabajando": ["SDIS_TRABAJANDO"],
    "fecha_desistimiento": ["FECHA DESISTIMIENTO (Cuando Aplique)", "FECHA DESISTIMIENTO"],
    "primer_nombre": ["PRIMER_NOMBRE"],
    "primer_apellido": ["PRIMER_APELLIDO"],
    "segundo_apellido": ["SEGUNDO_APELLIDO"],
    # caracterización (nov-2026); discapacidad = dato sensible: solo filtros y conteos agregados
    "sexo": ["SDIS_SEXO", "SEXO"],
    "estrato": ["SDIS_ESTRATO", "ESTRATO"],
    "nivel_educativo": ["SDIS_NIVEL_EDUCATIVO", "NIVEL_EDUCATIVO", "NIVEL EDUCATIVO"],
    "discapacidad": ["TG_24_PRESENTA_DISCAPACIDAD", "PRESENTA_DISCAPACIDAD", "DISCAPACIDAD"],
    "tipo_discapacidad": ["TG_31_TIP_DISCAPACIDAD", "TIPO_DISCAPACIDAD"],
}
OBLIGATORIAS = ["documento", "cohorte", "resultado"]


def _plano(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def es_formalizacion(valores: list[list[str]]) -> bool:
    return any("numero documento" in {_plano(c) for c in fila} for fila in valores[:5])


def a_dataframe(valores: list[list[str]]) -> pd.DataFrame:
    """Usa como encabezado la primera fila que contenga NUMERO_DOCUMENTO (la fila 1 trae «Actualizar»)."""
    i = next(i for i, fila in enumerate(valores[:5]) if "numero documento" in {_plano(c) for c in fila})
    enc = [str(c).strip() for c in valores[i]]
    ancho = len(enc)
    filas = [(list(f) + [""] * ancho)[:ancho] for f in valores[i + 1:]]
    return pd.DataFrame(filas, columns=enc)


def doc_normalizado(s: pd.Series) -> pd.Series:
    """Solo dígitos (quita puntos, espacios y .0 de Excel) para cruzar documentos de dos fuentes."""
    t = s.astype("string").str.strip().str.replace(r"\.0$", "", regex=True).str.replace(r"\D", "", regex=True)
    return t.where(t.str.len() > 0)


def huella(docs: pd.Series) -> pd.Series:
    """Huella SHA-256 del documento normalizado: el cruce Formalización ↔ SIS se hace sin guardar documentos."""
    import hashlib
    return doc_normalizado(docs).map(lambda d: hashlib.sha256(d.encode()).hexdigest()[:20] if isinstance(d, str)
                                     else None)


def tematica_corta(t) -> str:
    t = str(t or "")
    if "marketing" in t.lower():
        return "Marketing y finanzas"
    if "auxiliar" in t.lower():
        return "Auxiliar y servicio al cliente"
    return t.strip() or "Sin dato"


def _iniciales(*partes) -> str:
    palabras = [p for x in partes for p in re.findall(r"[^\W\d_]+", str(x or ""))]
    return "".join(p[0].upper() + "." for p in palabras[:4])


SIN_INFO = "Sin información"


def _texto_caract(s: pd.Series) -> pd.Series:
    """«BASICA SECUNDARIA Y MEDIA» → «Basica secundaria y media»; vacíos y «SIN INFORMACION» → «Sin información»."""
    t = s.astype("string").fillna("").str.strip()
    t = t.str.capitalize()
    return t.mask(t.eq("") | t.map(_plano).isin(["sin informacion", "nan", "none", "no reporta"]), SIN_INFO)


def caracterizacion(col: dict) -> dict:
    """Sexo, estrato, nivel educativo y discapacidad (Sí/No + tipo) con valores homogéneos."""
    sexo = _texto_caract(col["sexo"])
    disc_raw = col["discapacidad"].map(_plano)
    discapacidad = pd.Series(SIN_INFO, index=disc_raw.index).mask(disc_raw.isin(["si", "s"]), "Sí") \
        .mask(disc_raw.isin(["no", "n"]), "No")
    tipo = _texto_caract(col["tipo_discapacidad"])
    tipo = tipo.where(discapacidad.eq("Sí"), "No aplica").mask(discapacidad.eq("Sí") & tipo.isin(
        [SIN_INFO, "No aplica"]), SIN_INFO)
    return {"sexo": sexo, "estrato": _texto_caract(col["estrato"]),
            "nivel_educativo": _texto_caract(col["nivel_educativo"]),
            "discapacidad": discapacidad, "tipo_discapacidad": tipo}


def limpiar(crudo: pd.DataFrame, huella_a_id: dict[str, int]) -> pd.DataFrame:
    """Devuelve la base en el formato interno del tablero (mismo esquema que limpiar_beneficiarios)."""
    por_plano = {_plano(c): c for c in crudo.columns}
    origen = {k: next((por_plano[_plano(a)] for a in alias if _plano(a) in por_plano), None)
              for k, alias in COLUMNAS.items()}
    faltan = [COLUMNAS[k][0] for k in OBLIGATORIAS if origen[k] is None]
    if faltan:
        raise ValueError("A la base de Formalización le faltan columnas: " + ", ".join(faltan))
    col = {k: (crudo[v] if v is not None else pd.Series([""] * len(crudo), index=crudo.index)).astype("string")
           .fillna("").str.strip() for k, v in origen.items()}

    doc = huella(col["documento"])
    validas = doc.notna()
    resultado = col["resultado"].str.lower()
    desistido = resultado.str.contains("desist")
    formalizado = resultado.str.startswith("formalizado")
    trabajando = col["trabajando"].str.upper()

    ids = doc.map(huella_a_id)
    # Personas sin usuario en el SIS: se conservan (cuentan como entregadas/formalizadas) con un ID negativo
    # interno que nunca se muestra.
    sin_sis = ids.isna()
    ids = ids.where(~sin_sis, -pd.Series(range(1, len(ids) + 1), index=ids.index))

    cohorte = col["cohorte"].where(col["cohorte"] != "", "Sin cohorte")
    cohorte = cohorte.where(~cohorte.str.lower().eq("no aplica"), "No formalizados")
    df = pd.DataFrame({
        "id_sis": pd.array(ids, dtype="Int64"),
        "documento": None,                                  # no se guarda
        "nombre": [_iniciales(a, b, c) for a, b, c in zip(col["primer_nombre"], col["primer_apellido"],
                                                            col["segundo_apellido"])],
        "cohorte": cohorte,
        "poblacion": "Sin dato",                            # la base no distingue convocatoria abierta/cerrada
        "perfil": col["tematica"].map(tematica_corta),
        "nivel": col["nivel"].where(col["nivel"] != "", "Sin dato"),
        "grupo": "Sin dato", "docente": "Sin dato", "gestor": "Sin dato", "franja": "Sin dato",
        "enrolado": (formalizado | desistido),
        "estado": pd.Series("Enrolado", index=crudo.index).where(formalizado, "No formalizado")
                    .where(~desistido, "Retirado"),
        "lab_inicio": trabajando.map(lambda v: "Desempleado" if v.endswith("NO") else
                                     ("Trabajando" if v.endswith("SI") else "")),
        "en_sis": ~sin_sis,
        "huella": doc,                                      # para buscar por cédula sin guardar la cédula
        "fuente": "formalizacion",
        **caracterizacion(col),
    })[validas]
    df["certificado"] = pd.Series([None] * len(df), index=df.index, dtype=object)
    df["formal_t3"] = pd.Series([None] * len(df), index=df.index, dtype=object)
    return df.drop_duplicates("id_sis").reset_index(drop=True)


def calendario(benef: pd.DataFrame, grupos_sis: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """La base no trae fechas: cada persona toma grupo y calendario de su grupo en el SIS, y cada cohorte va
    del primer inicio al último fin de sus grupos. grupos_sis: id_sis, grupo, fecha_inicio, fecha_fin."""
    g = grupos_sis.dropna(subset=["id_sis"]).drop_duplicates("id_sis")
    g = {int(k): v for k, v in zip(g["id_sis"], zip(g["grupo"], g["fecha_inicio"], g["fecha_fin"]))}
    b = benef.copy()
    # Diccionarios en vez de map(): según la versión de pandas, map() sobre un ID «Int64» sin coincidencias devolvía
    # una columna numérica y luego no aceptaba texto (TypeError «Invalid value … for dtype Int64»).
    ids = [int(i) if pd.notna(i) else None for i in b["id_sis"]]
    b["grupo"] = [g[i][0] if i in g and pd.notna(g[i][0]) else actual for i, actual in zip(ids, b["grupo"])]
    b["fi_grupo"] = pd.to_datetime(pd.Series([g[i][1] if i in g else None for i in ids], index=b.index),
                                   errors="coerce")
    b["ff_grupo"] = pd.to_datetime(pd.Series([g[i][2] if i in g else None for i in ids], index=b.index),
                                   errors="coerce")
    coh = (b[b["enrolado"]].groupby("cohorte", as_index=False)
             .agg(fecha_inicio=("fi_grupo", "min"), fecha_fin=("ff_grupo", "max")))
    faltan = sorted(set(b["cohorte"]) - set(coh["cohorte"]))
    if faltan:
        coh = pd.concat([coh, pd.DataFrame({"cohorte": faltan})], ignore_index=True)
    return b, coh.sort_values("fecha_inicio", na_position="last").reset_index(drop=True)


# ------------------------------------------------------------------ Asignación docente (programa, nivel y grupo)
ORDEN_NIVEL = ["Básico", "Intermedio", "Avanzado"]


def asignacion(valores: list[list[str]]) -> pd.DataFrame:
    """Pestaña «Base de estudiantes» del Sheet «Asignación docente · Talento Capital Formación»: una fila por
    estudiante con documento, grupo, Programa, Nivel, Jornada, Docente asignado y Gestor. Devuelve, SIN el documento
    (solo su huella): huella, grupo, perfil, nivel, franja, docente, gestor."""
    i = next((i for i, f in enumerate(valores[:5]) if "documento" in {_plano(c) for c in f}), None)
    if i is None:
        raise ValueError("La pestaña de asignación no tiene la columna «documento».")
    enc = [_plano(c) for c in valores[i]]
    filas = valores[i + 1:]

    def col(*nombres):
        for n in nombres:
            if n in enc:  # la primera aparición (la pestaña repite «Nivel»)
                j = enc.index(n)
                return pd.Series([str(f[j]).strip() if j < len(f) else "" for f in filas], dtype="string")
        return pd.Series([""] * len(filas), dtype="string")

    jornada = col("jornada")
    df = pd.DataFrame({
        "huella": huella(col("documento")),
        "grupo": col("grupo"),
        "perfil": col("programa", "curso").map(lambda t: tematica_corta(t) if t else ""),
        "nivel": col("nivel").str.title(),
        "franja": jornada.str.title(),
        "docente": col("docente asignado", "docente"),
        "gestor": col("gestor"),
    })
    df = df[df["huella"].notna() & df["grupo"].ne("")]
    return df.drop_duplicates("huella").reset_index(drop=True)


def aplicar_asignacion(benef: pd.DataFrame, asig: pd.DataFrame, etiqueta_franja) -> pd.DataFrame:
    """Programa, nivel, grupo, jornada, docente y gestor de la Asignación docente mandan sobre Formalización/SIS
    (nov-2026). El grupo principal del SIS sigue disponible en «grupo_sis» (viene del avance) para comparar."""
    b = benef.copy()
    if asig is None or asig.empty or "huella" not in b:
        return b
    a = asig.set_index("huella")
    for col in ("grupo", "perfil", "nivel", "docente", "gestor", "franja"):
        mapa = a[col].replace("", pd.NA).dropna().to_dict()
        nuevo = [mapa.get(h) for h in b["huella"]]
        if col == "franja":
            nuevo = [etiqueta_franja(v) if v else None for v in nuevo]
        b[col] = [n if n else actual for n, actual in zip(nuevo, b[col])]
    b["en_asignacion"] = b["huella"].isin(a.index)
    return b
