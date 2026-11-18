"""pytest -q  · reglas del contrato sobre datos sintéticos mínimos."""
import pandas as pd
import pytest

from tcf10 import config as C
from tcf10 import metrics as M


def _base(n_culm=0, n_activos=0, n_sin=0, cerrada=False):
    filas, avance = [], []
    i = 0
    for tipo, n in (("culm", n_culm), ("act", n_activos), ("sin", n_sin)):
        for _ in range(n):
            i += 1
            filas.append({"id_sis": i, "documento": str(i), "nombre": "Ana Pérez", "cohorte": "Cohorte 1",
                          "poblacion": "Abierta", "perfil": "Auxiliar", "nivel": "A1", "grupo": "G1",
                          "docente": "D1", "gestor": "Ge1", "franja": "Mañana", "enrolado": tipo != "sin",
                          "estado": "Activo" if tipo != "sin" else "Entregado", "lab_inicio": "Desempleado",
                          "certificado": None, "formal_t3": None})
            if tipo == "culm":
                avance.append({"id_sis": i, "horas_sinc": 31.5, "horas_asinc": 40, "sesiones_asistidas": 10,
                               "ultima_actividad": pd.Timestamp("2026-11-10")})
            elif tipo == "act":
                avance.append({"id_sis": i, "horas_sinc": 5, "horas_asinc": 5, "sesiones_asistidas": 2,
                               "ultima_actividad": pd.Timestamp("2026-11-12")})
    fin = "2026-11-10" if cerrada else "2026-12-30"
    coh = pd.DataFrame([{"cohorte": "Cohorte 1", "fecha_inicio": pd.Timestamp("2026-09-21"),
                         "fecha_fin": pd.Timestamp(fin), "tipo": "Cerrada"}])
    return M.preparar(pd.DataFrame(filas), pd.DataFrame(avance), coh, pd.Timestamp("2026-11-13"))


def test_redondeo_tipo_excel():
    assert M._redondear_pct(0.975) == 98
    assert M._redondear_pct(0.9749) == 97
    assert M._redondear_pct(None) is None


def test_culminacion_respeta_topes():
    df = _base(n_culm=1)
    # asincrónicas topadas en 58.5 no aplica; 31.5 + 40 = 71.5 ≥ 63
    assert bool(df["culmino"].iloc[0])
    assert df["horas_validas"].iloc[0] == pytest.approx(71.5)


def test_horas_de_mas_no_compensan():
    df = _base(n_culm=1)
    df2 = M.preparar(df[["id_sis", "documento", "nombre", "cohorte", "poblacion", "perfil", "nivel", "grupo",
                         "docente", "gestor", "franja", "enrolado", "estado", "lab_inicio", "certificado",
                         "formal_t3"]],
                     pd.DataFrame([{"id_sis": 1, "horas_sinc": 0, "horas_asinc": 200, "sesiones_asistidas": 0,
                                    "ultima_actividad": pd.Timestamp("2026-11-12")}]),
                     pd.DataFrame([{"cohorte": "Cohorte 1", "fecha_inicio": pd.Timestamp("2026-09-21"),
                                    "fecha_fin": pd.Timestamp("2026-12-30"), "tipo": "Cerrada"}]),
                     pd.Timestamp("2026-11-13"))
    assert df2["horas_validas"].iloc[0] == pytest.approx(C.HORAS_ASINCRONICAS)
    assert not bool(df2["culmino"].iloc[0])


def test_enrolamiento_en_curso_no_es_incumplido():
    df = _base(n_activos=50, n_sin=50)
    p = {x["clave"]: x for x in M.pagos(df)}["enrolamiento"]
    assert p["estado"] in {"En curso", "No cumplido"}
    assert p["alcanzado_pct"] == 50
    assert p["faltan"] == 50  # 100 % ofertado sobre 100 entregados


def test_pago_culminacion_por_persona():
    df = _base(n_culm=10, n_activos=5)
    p = {x["clave"]: x for x in M.pagos(df)}["culminacion"]
    assert p["culminados"] == 10
    assert p["monto_actual"] == pytest.approx(10 * C.VALOR_POR_CULMINADO)


def test_activo_rezagado_es_riesgo_alto():
    df = _base(n_activos=1)
    assert df["riesgo"].iloc[0] == "Alto"  # 10 h cuando se esperaban ~60


def test_cohortes_agrupan_grupos_de_la_misma_semana():
    from tcf10.data import agrupar_cohortes
    s = pd.Series(pd.to_datetime(["2026-11-10", "2026-11-11", "2026-11-17", "2026-11-18", "2027-02-01", None]))
    c = agrupar_cohortes(s).tolist()
    assert c[0] == c[3] == "Cohorte 1 · 10–18 nov 2026"
    assert c[4] == "Cohorte 2 · 1 feb 2027"
    assert c[5] == "Sin grupo con fecha"


def test_riesgo_fase_inicial_por_asistencia():
    base = dict(retirado=False, enrolado=True, culmino=False, cohorte_iniciada=True, cohorte_cerrada=False,
                dias_desde_inicio=8, dias_sin_actividad=2, ritmo=0.1, avance_esperado_h=12)
    f = pd.Series({**base, "sesiones_registradas": 3, "sesiones_asistidas": 0, "horas_asinc": 0})
    assert M._riesgo(f) == "Alto"
    f = pd.Series({**base, "sesiones_registradas": 4, "sesiones_asistidas": 1, "horas_asinc": 0.5})
    assert M._riesgo(f) == "Medio"
    f = pd.Series({**base, "sesiones_registradas": 4, "sesiones_asistidas": 3, "horas_asinc": 0})
    assert M._riesgo(f) == "Bajo"   # ritmo bajo no cuenta en la fase inicial
