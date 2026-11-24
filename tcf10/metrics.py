"""
Reglas de negocio de TCF10 (sin Streamlit: se prueban con pytest).

Tablas de entrada (ver tcf10/data.py y README):
  beneficiarios  una fila por persona entregada por Atenea (base + estado operativo).
  avance         horas sincrónicas (asistencia) y asincrónicas (plataforma) por id_sis, desde el SIS.
  cohortes       fechas de inicio y fin de cada cohorte.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tcf10 import config as C

NIVELES_RIESGO = ["Alto", "Medio", "Bajo"]
# Cambia cuando cambian las columnas que calcula preparar(): forma parte de la llave del caché de ui._preparado, así
# un despliegue nuevo no reutiliza tablas viejas (nov-2026: «KeyError: 'critico'» tras agregar la tipificación).
VERSION = "2026-11-24 feedbacks"


def _n(x) -> str:
    """Entero con separador de miles colombiano (1.743)."""
    return f"{x:,.0f}".replace(",", ".")


def _marcados(df: pd.DataFrame, col: str) -> pd.Series:
    """True/False por fila sin depender del dtype (object, boolean o Arrow). Vacío cuenta como False."""
    if col not in df:
        return pd.Series(False, index=df.index)
    def es_si(v) -> bool:
        if isinstance(v, (bool, np.bool_)):
            return bool(v)
        return isinstance(v, str) and v.strip().upper() in {"SI", "SÍ", "TRUE", "1", "X", "VERDADERO"}
    return pd.Series([es_si(v) for v in df[col].tolist()], index=df.index, dtype=bool)


def _hay_dato(df: pd.DataFrame, col: str) -> bool:
    return col in df and any(v is not None and v is not pd.NA and not (isinstance(v, float) and np.isnan(v)) for v in df[col].tolist())


def _redondear_pct(x: float | None) -> int | None:
    """Nota general 3 del ET: el índice se redondea a entero (REDONDEAR(n; 0) de Excel)."""
    if x is None or pd.isna(x):
        return None
    return int(np.floor(x * 100 + 0.5))  # Excel redondea .5 hacia arriba (Python usaría banker's rounding)


# ------------------------------------------------------------------ avance y riesgo
def preparar(benef: pd.DataFrame, avance: pd.DataFrame, cohortes: pd.DataFrame,
             hoy: pd.Timestamp) -> pd.DataFrame:
    """Une base + avance + calendario y calcula horas válidas, culminación, ritmo y riesgo."""
    df = benef.merge(avance, on="id_sis", how="left").merge(cohortes, on="cohorte", how="left")
    for c in ("horas_sinc", "horas_asinc"):
        df[c] = pd.to_numeric(df.get(c), errors="coerce").fillna(0.0)
    # Cada componente cuenta hasta su tope (31,5 h y 58,5 h): horas de más no compensan el otro.
    df["horas_sinc_val"] = df["horas_sinc"].clip(upper=C.HORAS_SINCRONICAS)
    df["horas_asinc_val"] = df["horas_asinc"].clip(upper=C.HORAS_ASINCRONICAS)
    df["horas_validas"] = df["horas_sinc_val"] + df["horas_asinc_val"]
    df["pct_avance"] = df["horas_validas"] / C.HORAS_TOTALES
    df["enrolado"] = df["enrolado"].astype(bool)
    df["retirado"] = df["estado"].eq("Retirado")
    df["culmino"] = df["enrolado"] & ~df["retirado"] & (
        (df["horas_validas"] >= C.HORAS_CULMINACION - 1e-9) | df["estado"].eq("Culminado"))

    inicio = pd.to_datetime(df["fecha_inicio"])
    fin = pd.to_datetime(df["fecha_fin"])
    if "fi_grupo" in df:  # sin base de Atenea: cada persona con el calendario de su grupo
        inicio = pd.to_datetime(df["fi_grupo"]).fillna(inicio)
        fin = pd.to_datetime(df["ff_grupo"]).fillna(fin)
    for c in ("sesiones_asistidas", "sesiones_registradas", "sesiones_a_la_fecha", "sesiones_totales"):
        df[c] = pd.to_numeric(df[c], errors="coerce") if c in df else np.nan
    duracion = (fin - inicio).dt.days.clip(lower=1)
    transcurrido = ((hoy - inicio).dt.days / duracion).clip(lower=0, upper=1)
    df["avance_esperado_h"] = C.HORAS_TOTALES * transcurrido
    df["ritmo"] = np.where(df["avance_esperado_h"] > 0, df["horas_validas"] / df["avance_esperado_h"], np.nan)
    ultima = pd.to_datetime(df.get("ultima_actividad"), errors="coerce")
    referencia = ultima.fillna(inicio)
    df["dias_sin_actividad"] = (hoy - referencia).dt.days.clip(lower=0)
    df["dias_desde_inicio"] = (hoy - inicio).dt.days
    df["cohorte_iniciada"] = inicio <= hoy
    df["cohorte_cerrada"] = fin < hoy

    df["riesgo"] = df.apply(_riesgo, axis=1)
    df = tipificar(df, hoy)
    df["prob_culminar"] = np.select(
        [df["culmino"], df["riesgo"].isin(C.PROB_CULMINAR)],
        [1.0, df["riesgo"].map(C.PROB_CULMINAR).fillna(0)], default=0.0)
    return df


def _riesgo(f: pd.Series) -> str:
    if f["retirado"]:
        return "Retirado"
    if not f["enrolado"]:
        return "Sin enrolar"
    if f["culmino"]:
        return "Culminó"
    if not f["cohorte_iniciada"]:
        return "Sin iniciar"
    if f.get("en_sis") in (False,):  # formalizado sin usuario en la plataforma: no puede estudiar
        return "Alto"
    if f["cohorte_cerrada"]:
        return "No culminó"
    inactivo = f["dias_sin_actividad"] if f["dias_desde_inicio"] >= C.RIESGO_GRACIA_DIAS else 0
    a, m = C.RIESGO["alto"], C.RIESGO["medio"]
    # Fase inicial: manda la asistencia (el ritmo de horas aún no es representativo).
    if pd.notna(f["dias_desde_inicio"]) and f["dias_desde_inicio"] < C.RIESGO_FASE_INICIAL_DIAS:
        reg, asis = f.get("sesiones_registradas"), f.get("sesiones_asistidas")
        if pd.notna(reg) and reg >= C.RIESGO_MIN_SESIONES:
            if asis == 0 and f["horas_asinc"] <= 0:
                return "Alto"
            if asis / reg < C.RIESGO_ASISTENCIA_MEDIO:
                return "Medio"
        return "Medio" if inactivo >= m["dias_sin_actividad"] else "Bajo"
    ritmo = f["ritmo"] if f["avance_esperado_h"] >= C.RIESGO_MIN_ESPERADO_H else np.nan
    if (pd.notna(ritmo) and ritmo < a["ritmo_menor_a"]) or inactivo >= a["dias_sin_actividad"]:
        return "Alto"
    if (pd.notna(ritmo) and ritmo < m["ritmo_menor_a"]) or inactivo >= m["dias_sin_actividad"]:
        return "Medio"
    return "Bajo"


def motivo_riesgo(f: pd.Series) -> str:
    partes = []
    if f.get("en_sis") in (False,):
        return "formalizado pero sin usuario en el SIS"
    if (pd.notna(f.get("dias_desde_inicio")) and f["dias_desde_inicio"] < C.RIESGO_FASE_INICIAL_DIAS
            and pd.notna(f.get("sesiones_registradas")) and f["sesiones_registradas"] >= C.RIESGO_MIN_SESIONES):
        asis, reg = int(f["sesiones_asistidas"] or 0), int(f["sesiones_registradas"])
        if asis == 0:
            partes.append(f"no asistió a ninguna de {reg} sesiones" + ("" if f["horas_asinc"] > 0 else
                                                                         " ni avanzó en plataforma"))
        elif asis / reg < C.RIESGO_ASISTENCIA_MEDIO:
            partes.append(f"asistió a {asis} de {reg} sesiones")
        if f.get("dias_sin_actividad", 0) >= C.RIESGO["medio"]["dias_sin_actividad"]:
            partes.append(f"{int(f['dias_sin_actividad'])} días sin actividad")
        return "; ".join(partes)
    if pd.notna(f.get("ritmo")) and f["ritmo"] < C.RIESGO["medio"]["ritmo_menor_a"]:
        partes.append(f"va al {f['ritmo']:.0%} del ritmo esperado")
    if f.get("dias_sin_actividad", 0) >= C.RIESGO["medio"]["dias_sin_actividad"]:
        partes.append(f"{int(f['dias_sin_actividad'])} días sin actividad")
    return "; ".join(partes)


# ------------------------------------------------------------------ pagos e índices
def pagos(df: pd.DataFrame) -> list[dict]:
    """Estado actual y proyección de los 4 pagos. Cada dict trae: clave, nombre, actual, meta, cumple,
    monto_maximo, monto_actual, monto_proyectado, detalle, medible."""
    salida = []
    entregados = len(df)
    enrolados = int(df["enrolado"].sum())
    solo_sis = "fuente" in df and bool(df["fuente"].eq("sis").all())
    # sin la base de Atenea (modo solo SIS) no se sabe cuántos se entregaron: se compara contra los cupos
    denominador = C.CUPOS_CONTRATADOS if solo_sis else (min(C.CUPOS_CONTRATADOS, entregados) or C.CUPOS_CONTRATADOS)
    todas_iniciadas = bool(len(df)) and bool(df["cohorte_iniciada"].all())
    todas_cerradas = bool(len(df)) and bool(df["cohorte_cerrada"].all())
    if solo_sis:
        # El índice es enrolados ÷ personas entregadas por Atenea: sin esa base no se puede calcular.
        # El SIS puede tener más estudiantes que cupos (reemplazos, pruebas), así que no se compara contra cupos.
        salida.append(_indice("enrolamiento", enrolados, C.CUPOS_CONTRATADOS, medible=False,
                              detalle=f"{_n(enrolados)} estudiantes en el SIS frente a {_n(C.CUPOS_CONTRATADOS)} "
                                      "cupos. Se mide con la base que entrega Atenea."))
    else:
        salida.append(_indice("enrolamiento", enrolados, denominador, medible=entregados > 0, final=todas_iniciadas,
                              detalle=f"{_n(enrolados)} enrolados de {_n(denominador)} "
                                      f"({'cupos' if denominador == C.CUPOS_CONTRATADOS else 'entregados por Atenea'})"))

    culminados = int(df["culmino"].sum())
    proyectados = float(df.loc[df["enrolado"] & ~df["retirado"], "prob_culminar"].sum())
    tope = min(C.CUPOS_CONTRATADOS, max(enrolados, 1))
    maximo = C.VALOR_POR_CULMINADO * C.CUPOS_CONTRATADOS
    salida.append({
        "clave": "culminacion", "nombre": C.PAGOS["culminacion"]["nombre"],
        "actual": culminados / tope if enrolados else None, "meta": None, "cumple": None,
        "monto_maximo": maximo,
        "monto_actual": C.VALOR_POR_CULMINADO * min(culminados, C.CUPOS_CONTRATADOS),
        "monto_proyectado": C.VALOR_POR_CULMINADO * min(proyectados, C.CUPOS_CONTRATADOS),
        "culminados": culminados, "proyectados": proyectados,
        "detalle": f"{_n(culminados)} culminaron · proyección {_n(proyectados)}",
        "medible": enrolados > 0, "estado": "En curso" if enrolados else "Sin datos",
    })

    certificados = int(_marcados(df, "certificado").sum())
    hay_cert = _hay_dato(df, "certificado")
    salida.append(_indice("exito", certificados, culminados, medible=bool(hay_cert and culminados),
                          final=todas_cerradas,
                          detalle=f"{_n(certificados)} certificados de {_n(culminados)} que culminaron"))

    base_tml = df[df["poblacion"].eq("Abierta") & df["culmino"]
                  & df["lab_inicio"].isin(["Desempleado", "No formal"])]
    formales = int(_marcados(base_tml, "formal_t3").sum())
    hay_pila = _hay_dato(df, "formal_t3")
    salida.append(_indice("tml", formales, len(base_tml), medible=bool(hay_pila and len(base_tml)),
                          final=todas_cerradas,
                          detalle=f"{_n(formales)} formales en PILA de {_n(len(base_tml))} (convocatoria abierta)"))
    return salida


def _indice(clave: str, numerador: int, denominador: int, medible: bool, detalle: str,
            final: bool = False) -> dict:
    """final=True cuando el índice ya se puede liquidar (todas las cohortes enroladas o cerradas).
    Antes de eso el valor es parcial: el estado es «En curso», no «No cumplido»."""
    p = C.PAGOS[clave]
    valor = numerador / denominador if denominador else None
    alcanzado = _redondear_pct(valor) if medible else None
    meta = int(round(p["indice_ofertado"] * 100))
    logrado = medible and alcanzado is not None and alcanzado >= meta
    cumple = True if logrado else (False if (medible and final) else None)
    estado = ("Cumplido" if logrado else "No cumplido" if cumple is False
              else "En curso" if medible else "Sin datos")
    monto = p["pct_contrato"] * C.VALOR_CONTRATO
    faltan = None
    if denominador and not cumple:
        faltan = max(0, int(np.ceil((meta - 0.5) / 100 * denominador)) - numerador)
    return {"clave": clave, "nombre": p["nombre"], "actual": valor, "alcanzado_pct": alcanzado,
            "meta": p["indice_ofertado"], "cumple": cumple, "monto_maximo": monto,
            "monto_actual": monto if cumple else 0.0, "monto_proyectado": None,
            "faltan": faltan, "detalle": detalle, "medible": medible, "estado": estado}


def resumen_dinero(lista: list[dict]) -> dict:
    total = sum(p["monto_maximo"] for p in lista)
    asegurado = sum(p["monto_actual"] for p in lista)
    return {"total": total, "asegurado": asegurado, "en_juego": total - asegurado}


# ------------------------------------------------------------------ cohortes y equipo
def por_cohorte(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("cohorte").agg(
        entregados=("id_sis", "size"), enrolados=("enrolado", "sum"), retirados=("retirado", "sum"),
        culminados=("culmino", "sum"), horas_promedio=("horas_validas", "mean"),
        riesgo_alto=("riesgo", lambda s: int(s.eq("Alto").sum())),
        riesgo_medio=("riesgo", lambda s: int(s.eq("Medio").sum())),
        fecha_inicio=("fecha_inicio", "first"), fecha_fin=("fecha_fin", "first")).reset_index()
    g["pct_enrolados"] = g["enrolados"] / g["entregados"]
    g["pct_culminados"] = np.where(g["enrolados"] > 0, g["culminados"] / g["enrolados"], np.nan)
    g["desercion"] = np.where(g["enrolados"] > 0, g["retirados"] / g["enrolados"], np.nan)
    return g


def activos(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["enrolado"] & df["estado"].isin(C.ESTADOS_ACTIVOS) & ~df["culmino"]]


def grupos(df: pd.DataFrame) -> pd.DataFrame:
    base = df[df["enrolado"] & ~df["retirado"]]
    g = base.groupby(["cohorte", "grupo", "perfil", "nivel", "docente", "gestor", "franja"], dropna=False).agg(
        integrantes=("id_sis", "size"),
        activos=("estado", lambda s: int(s.isin(C.ESTADOS_ACTIVOS).sum())),
        culminados=("culmino", "sum"), horas_promedio=("horas_validas", "mean"),
        riesgo_alto=("riesgo", lambda s: int(s.eq("Alto").sum()))).reset_index()
    g["excede_maximo"] = g["activos"] > C.MAX_ACTIVOS_POR_GRUPO
    return g.sort_values(["cohorte", "grupo"])


def docentes(df: pd.DataFrame) -> pd.DataFrame:
    """Carga por docente en cada cohorte en curso (los grupos simultáneos son los de la misma cohorte)."""
    base = df[df["enrolado"] & ~df["retirado"] & df["docente"].ne("Sin dato")]
    d = base.groupby(["docente", "cohorte"]).agg(
        grupos=("grupo", "nunique"), gestores=("gestor", "nunique"), franjas=("franja", "nunique"),
        activos=("estado", lambda s: int(s.isin(C.ESTADOS_ACTIVOS).sum()))).reset_index()
    d["alerta"] = np.select(
        [d["grupos"] > C.MAX_GRUPOS_POR_DOCENTE, d["gestores"] < C.MIN_GESTORES_POR_DOCENTE],
        [f"Más de {C.MAX_GRUPOS_POR_DOCENTE} grupos simultáneos", "Sin gestor asignado"], default="")
    return d.sort_values(["cohorte", "docente"])


def alertas_equipo(df: pd.DataFrame) -> list[str]:
    msgs = []
    g, d = grupos(df), docentes(df)
    for _, r in g[g["excede_maximo"]].iterrows():
        msgs.append(f"Grupo {r['grupo']} ({r['cohorte']}) tiene {r['activos']} activos: máximo "
                    f"{C.MAX_ACTIVOS_POR_GRUPO} por grupo acordado con Atenea ({r['activos'] - C.MAX_ACTIVOS_POR_GRUPO} de más).")
    for _, r in d[d["alerta"] != ""].iterrows():
        msgs.append(f"{r['docente']} · {r['cohorte']}: {r['alerta'].lower()}.")
    if "en_sis" in df:
        sin = int((df["enrolado"] & ~df["retirado"] & ~df["en_sis"].astype(bool)).sum())
        if sin:
            msgs.insert(0, f"{sin} personas formalizadas no tienen usuario en el SIS (no se encontró su documento): "
                           "no pueden registrar asistencia ni avance.")
    base = df[df["enrolado"] & ~df["retirado"] & df["franja"].ne("Sin dato")]
    for coh, s in base.groupby("cohorte")["franja"]:
        if s.nunique() < C.MIN_FRANJAS:
            msgs.append(f"{coh}: {s.nunique()} franja(s) horaria(s); el contrato pide mínimo {C.MIN_FRANJAS}.")
    return msgs


# ------------------------------------------------------------------ tipificación y casos críticos (vista interna)
def tipificar(df: pd.DataFrame, hoy: pd.Timestamp) -> pd.DataFrame:
    """Ruta mínima de cada estudiante para llegar al 70 % (63 h) y marca de caso crítico.

    Premisa (Kuepa, nov-2026): con la plataforma al 100 % (58,5 h) faltan 4,5 h sincrónicas; cada clase vale 4 h,
    así que hacen falta 2 clases en total (8 h → 66,5 h). Por eso:
      ≥ 2 clases asistidas → «Solo plataforma» · 1 clase → «1 clase + plataforma» · 0 → «2 clases + plataforma».
    «No alcanza»: le faltan más clases de las que quedan en su grupo, o el grupo ya cerró sin que llegara.
    «Ya aprobó»: ya tiene 63 h válidas.
    Columnas nuevas: clases_faltantes, tipo_ruta, faltan_h, faltan_plataforma_h, sesiones_restantes,
    max_alcanzable_h, sin_plataforma, no_alcanza, critico, motivo_critico.
    """
    df = df.copy()
    sinc, asinc = df["horas_sinc_val"], df["horas_asinc_val"]
    falta_sinc = (C.HORAS_CULMINACION - C.HORAS_ASINCRONICAS - sinc).clip(lower=0)  # horas con docente mínimas
    df["clases_faltantes"] = np.ceil(falta_sinc / C.HORAS_POR_SESION - 1e-9).astype(int)
    restantes = (df["sesiones_totales"] - df["sesiones_a_la_fecha"]).clip(lower=0) \
        if "sesiones_totales" in df else pd.Series(np.nan, index=df.index)
    restantes = restantes.where(~df["cohorte_cerrada"], 0)  # grupo cerrado: ya no quedan clases
    df["sesiones_restantes"] = restantes
    sinc_max = (sinc + restantes.fillna(np.inf) * C.HORAS_POR_SESION).clip(upper=C.HORAS_SINCRONICAS)
    df["max_alcanzable_h"] = np.where(restantes.notna(), sinc_max + C.HORAS_ASINCRONICAS, np.nan)
    df["faltan_h"] = (C.HORAS_CULMINACION - df["horas_validas"]).clip(lower=0).round(1)
    sinc_meta = (sinc + df["clases_faltantes"] * C.HORAS_POR_SESION).clip(upper=C.HORAS_SINCRONICAS)
    df["faltan_plataforma_h"] = (C.HORAS_CULMINACION - sinc_meta - asinc).clip(lower=0,
                                                                              upper=C.HORAS_ASINCRONICAS).round(1)
    activo = df["enrolado"] & ~df["retirado"] & ~df["culmino"]
    df["no_alcanza"] = activo & (df["cohorte_cerrada"] | (restantes.notna() & (df["clases_faltantes"] > restantes)))
    df["tipo_ruta"] = np.select(
        [df["culmino"], df["no_alcanza"], df["clases_faltantes"] >= 2, df["clases_faltantes"] == 1],
        ["Ya aprobó", "No alcanza", "2 clases + plataforma", "1 clase + plataforma"], default="Solo plataforma")
    df.loc[~df["enrolado"] | df["retirado"], "tipo_ruta"] = None

    # Sin uso de plataforma: 0 h con el grupo iniciado hace 7+ días, o 7+ días sin ingresar a la plataforma.
    en_curso = activo & df["cohorte_iniciada"] & ~df["cohorte_cerrada"]
    ultima_plat = pd.to_datetime(df["ultima_plataforma"], errors="coerce") if "ultima_plataforma" in df \
        else pd.Series(pd.NaT, index=df.index)
    dias_plat = (hoy - ultima_plat).dt.days
    cero = (df["horas_asinc"] <= 0) & (df["dias_desde_inicio"] >= C.DIAS_SIN_PLATAFORMA)
    inactivo = dias_plat >= C.DIAS_SIN_PLATAFORMA
    df["dias_sin_plataforma"] = dias_plat
    df["sin_plataforma"] = en_curso & (cero | inactivo.fillna(False))
    # Crítico = aún se puede actuar: grupos en curso (los cerrados quedan como «No alcanza», sin alerta).
    df["critico"] = df["sin_plataforma"] | (df["no_alcanza"] & ~df["cohorte_cerrada"])

    def motivo(f: pd.Series) -> str:
        partes = []
        if f["no_alcanza"]:
            partes.append(f"su grupo cerró con {f['horas_validas']:.1f} h".replace(".", ",") if f["cohorte_cerrada"]
                          else f"le faltan {int(f['clases_faltantes'])} clases y quedan {int(f['sesiones_restantes'])}")
        if f["sin_plataforma"]:
            if f["horas_asinc"] <= 0:
                partes.append("0 h en plataforma")
            elif pd.notna(f["dias_sin_plataforma"]):
                partes.append(f"{int(f['dias_sin_plataforma'])} días sin entrar a la plataforma")
        return "; ".join(partes)
    df["motivo_critico"] = df.apply(motivo, axis=1) if len(df) else pd.Series(dtype=str)
    return df


def feedback(df: pd.DataFrame, fb: pd.DataFrame, asis: pd.DataFrame, hoy: pd.Timestamp) -> pd.DataFrame:
    """Seguimiento de Feedbacks: un Feedback por clase dictada al grupo (máximo C.FEEDBACKS_TOTAL).

    fb: Feedbacks completados (id_sis, n). asis: sesiones por grupo (grupo, session_id, fecha) de data.agregados.
    Meta del grupo = clases dictadas antes de hoy (la de hoy todavía no se exige). Columnas nuevas: fb_1…fb_8,
    feedbacks_hechos, feedbacks_meta, feedbacks_atraso, estado_feedback, critico_feedback; además suma el atraso de
    C.FEEDBACK_ATRASO_CRITICO o más a «critico» y a «motivo_critico».
    """
    df = df.copy()
    tot = C.FEEDBACKS_TOTAL
    hechos_por_id: dict[int, set] = {}
    for i, n in zip(fb["id_sis"], fb["n"]):
        if pd.notna(i):
            hechos_por_id.setdefault(int(i), set()).add(int(n))
    ids = [int(i) if pd.notna(i) else None for i in df["id_sis"]]
    for n in range(1, tot + 1):
        df[f"fb_{n}"] = [i is not None and n in hechos_por_id.get(i, ()) for i in ids]
    df["feedbacks_hechos"] = df[[f"fb_{n}" for n in range(1, tot + 1)]].sum(axis=1).astype(int)

    a = asis.copy()
    a["fecha"] = pd.to_datetime(a["fecha"], errors="coerce")
    clases = (a[a["fecha"] < pd.Timestamp(hoy).normalize()].groupby("grupo")["session_id"].nunique()
              .clip(upper=tot).to_dict())
    activo = df["enrolado"] & ~df["retirado"] & df["cohorte_iniciada"]
    meta = [float(clases.get(str(g), 0)) if ok else np.nan for g, ok in zip(df["grupo"].astype(str), activo)]
    df["feedbacks_meta"] = pd.Series(meta, index=df.index)
    df["feedbacks_atraso"] = (df["feedbacks_meta"] - df["feedbacks_hechos"]).clip(lower=0)
    at = df["feedbacks_atraso"]
    df["estado_feedback"] = np.select(
        [df["feedbacks_meta"].isna(), df["feedbacks_meta"].eq(0), at.eq(0), at.eq(1), at.eq(2)],
        [None, "Aún no aplica", "Al día", "1 pendiente", "2 pendientes"], default="3 o más pendientes")
    df.loc[df["feedbacks_meta"].isna(), "estado_feedback"] = None
    hay_datos = len(fb) > 0
    en_curso = activo & ~df["culmino"] & ~df["cohorte_cerrada"]
    df["critico_feedback"] = hay_datos & en_curso & (at >= C.FEEDBACK_ATRASO_CRITICO)
    if "critico" in df:
        df["critico"] = df["critico"] | df["critico_feedback"]
        extra = [f"{int(p)} feedbacks pendientes (lleva {h} de {int(m)})" if c else ""
                 for c, p, h, m in zip(df["critico_feedback"], at.fillna(0), df["feedbacks_hechos"],
                                       df["feedbacks_meta"].fillna(0))]
        df["motivo_critico"] = ["; ".join(x for x in (m, e) if x) for m, e in zip(df["motivo_critico"].fillna(""), extra)]
    return df
