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
    if f["cohorte_cerrada"]:
        return "No culminó"
    ritmo = f["ritmo"] if f["avance_esperado_h"] >= C.RIESGO_MIN_ESPERADO_H else np.nan
    inactivo = f["dias_sin_actividad"] if f["dias_desde_inicio"] >= C.RIESGO_GRACIA_DIAS else 0
    a, m = C.RIESGO["alto"], C.RIESGO["medio"]
    if (pd.notna(ritmo) and ritmo < a["ritmo_menor_a"]) or inactivo >= a["dias_sin_actividad"]:
        return "Alto"
    if (pd.notna(ritmo) and ritmo < m["ritmo_menor_a"]) or inactivo >= m["dias_sin_actividad"]:
        return "Medio"
    return "Bajo"


def motivo_riesgo(f: pd.Series) -> str:
    partes = []
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
    denominador = min(C.CUPOS_CONTRATADOS, entregados) or C.CUPOS_CONTRATADOS
    todas_iniciadas = bool(len(df)) and bool(df["cohorte_iniciada"].all())
    todas_cerradas = bool(len(df)) and bool(df["cohorte_cerrada"].all())
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
    g["excede_30"] = g["activos"] > C.MAX_ACTIVOS_POR_GRUPO
    return g.sort_values(["cohorte", "grupo"])


def docentes(df: pd.DataFrame) -> pd.DataFrame:
    """Carga por docente en cada cohorte en curso (los grupos simultáneos son los de la misma cohorte)."""
    base = df[df["enrolado"] & ~df["retirado"]]
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
    for _, r in g[g["excede_30"]].iterrows():
        msgs.append(f"Grupo {r['grupo']} ({r['cohorte']}) tiene {r['activos']} activos: máximo "
                    f"{C.MAX_ACTIVOS_POR_GRUPO} por docente sin aprobación de Atenea.")
    for _, r in d[d["alerta"] != ""].iterrows():
        msgs.append(f"{r['docente']} · {r['cohorte']}: {r['alerta'].lower()}.")
    base = df[df["enrolado"] & ~df["retirado"]]
    for coh, s in base.groupby("cohorte")["franja"]:
        if s.nunique() < C.MIN_FRANJAS:
            msgs.append(f"{coh}: {s.nunique()} franja(s) horaria(s); el contrato pide mínimo {C.MIN_FRANJAS}.")
    return msgs