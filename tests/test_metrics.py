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


def _persona(i, sinc_clases, asinc, a_la_fecha, totales, ult_plat, inicio="2026-11-01", fin="2026-12-30"):
    benef = {"id_sis": i, "documento": str(i), "nombre": "X", "cohorte": "Cohorte 1", "poblacion": "Abierta",
             "perfil": "Auxiliar", "nivel": "A1", "grupo": "G1", "docente": "D1", "gestor": "Ge1",
             "franja": "Mañana", "enrolado": True, "estado": "Activo", "lab_inicio": "", "certificado": None,
             "formal_t3": None}
    av = {"id_sis": i, "horas_sinc": sinc_clases * C.HORAS_POR_SESION, "horas_asinc": asinc,
          "sesiones_asistidas": sinc_clases, "sesiones_registradas": a_la_fecha, "sesiones_a_la_fecha": a_la_fecha,
          "sesiones_totales": totales, "ultima_plataforma": pd.Timestamp(ult_plat) if ult_plat else pd.NaT,
          "ultima_actividad": pd.Timestamp("2026-11-12")}
    return benef, av


def _tipificados(personas, hoy="2026-11-20", fin="2026-12-30"):
    b, a = zip(*personas)
    coh = pd.DataFrame([{"cohorte": "Cohorte 1", "fecha_inicio": pd.Timestamp("2026-11-01"),
                         "fecha_fin": pd.Timestamp(fin), "tipo": "Cerrada"}])
    return M.preparar(pd.DataFrame(b), pd.DataFrame(a), coh, pd.Timestamp(hoy)).set_index("id_sis")


def test_tipificacion_por_clases_asistidas():
    df = _tipificados([_persona(1, 2, 10, 4, 15, "2026-11-19"),     # 8 h: con plataforma al 100 % llega
                       _persona(2, 1, 10, 4, 15, "2026-11-19"),     # 4 h + 58,5 = 62,5: le falta 1 clase
                       _persona(3, 0, 10, 4, 15, "2026-11-19"),     # 0 clases: le faltan 2
                       _persona(4, 0, 10, 14, 15, "2026-11-19"),    # le faltan 2 y solo queda 1 clase
                       _persona(5, 8, 58.5, 10, 15, "2026-11-19")]) # 32 h (31,5 tope) + 58,5 → ya aprobó
    assert df.loc[1, "tipo_ruta"] == "Solo plataforma" and df.loc[1, "clases_faltantes"] == 0
    assert df.loc[2, "tipo_ruta"] == "1 clase + plataforma"
    assert df.loc[3, "tipo_ruta"] == "2 clases + plataforma"
    assert df.loc[4, "tipo_ruta"] == "No alcanza" and bool(df.loc[4, "critico"])
    assert df.loc[5, "tipo_ruta"] == "Ya aprobó" and df.loc[5, "faltan_h"] == 0
    # horas: persona 1 tiene 8 + 10 = 18 h → faltan 45; en plataforma le faltan 63 - 8 - 10 = 45
    assert df.loc[1, "faltan_h"] == pytest.approx(45) and df.loc[1, "faltan_plataforma_h"] == pytest.approx(45)
    # persona 3: con las 2 clases (8 h) le faltan 63 - 8 - 10 = 45 h de plataforma
    assert df.loc[3, "faltan_plataforma_h"] == pytest.approx(45)


def test_sin_uso_de_plataforma():
    df = _tipificados([_persona(1, 1, 0, 3, 15, None),               # 0 h y el grupo inició hace 19 días
                       _persona(2, 1, 6, 3, 15, "2026-11-10"),       # 10 días sin entrar
                       _persona(3, 1, 6, 3, 15, "2026-11-18")])      # activo
    assert bool(df.loc[1, "sin_plataforma"]) and "0 h en plataforma" in df.loc[1, "motivo_critico"]
    assert bool(df.loc[2, "sin_plataforma"]) and "10 días" in df.loc[2, "motivo_critico"]
    assert not bool(df.loc[3, "critico"])


def test_grupo_cerrado_sin_aprobar_no_alcanza():
    df = _tipificados([_persona(1, 2, 20, 15, 15, "2026-11-19")], hoy="2027-01-05")
    assert df.loc[1, "tipo_ruta"] == "No alcanza"


def test_vista_interna_solo_para_correos_listados(monkeypatch):
    from vista_atenea import acceso
    monkeypatch.setattr(acceso, "_cfg", lambda: {"internos": ["Christian.Urquijo@kuepa.com"]})
    assert acceso.es_interno({"nombre": "christian.urquijo@kuepa.com", "via": "google"})
    assert not acceso.es_interno({"nombre": "otra@kuepa.com", "via": "google"})
    assert not acceso.es_interno({"nombre": "christian.urquijo@kuepa.com", "via": "usuario"})
    assert not acceso.es_interno(None)


def test_feedback_meta_por_clase_y_critico():
    import pandas as pd
    from tcf10 import metrics as M
    from tcf10 import sis_sheet as S
    hoy = pd.Timestamp("2026-11-20")
    df = pd.DataFrame({"id_sis": pd.array([1, 2, 3, 4], dtype="Int64"), "grupo": ["G1", "G1", "G2", "G1"],
                       "enrolado": True, "retirado": [False, False, False, True], "cohorte_iniciada": True,
                       "culmino": False, "cohorte_cerrada": False, "critico": False, "motivo_critico": ""})
    # G1: 4 clases antes de hoy + 1 hoy (no cuenta) · G2: ninguna todavía
    asis = pd.DataFrame({"grupo": ["G1"] * 5, "session_id": list("abcde"),
                         "fecha": pd.to_datetime(["2026-11-10", "2026-11-12", "2026-11-14", "2026-11-17", "2026-11-20"])})
    crudo = pd.DataFrame({"incremental": ["1", "1", "1", "2", "2"],
                          "feedback": ["Feedback 1", "Feedback 2", "Feedback 3", "Feedback 1", "Feedback 2"],
                          "completado": ["true", "true", "true", "true", "false"], "fecha": ""})
    r = M.feedback(df, S.feedbacks(crudo), asis, hoy).set_index("id_sis")
    assert r.loc[1, "feedbacks_meta"] == 4 and r.loc[1, "feedbacks_hechos"] == 3 and r.loc[1, "estado_feedback"] == "1 pendiente"
    assert r.loc[2, "feedbacks_hechos"] == 1 and r.loc[2, "feedbacks_atraso"] == 3
    assert r.loc[2, "estado_feedback"] == "3 o más pendientes" and r.loc[2, "critico"]
    assert "3 feedbacks pendientes (lleva 1 de 4)" in r.loc[2, "motivo_critico"]
    assert not r.loc[1, "critico"] and r.loc[3, "estado_feedback"] == "Aún no aplica"
    assert pd.isna(r.loc[4, "feedbacks_meta"]) and not r.loc[4, "critico"]  # retirado: fuera del seguimiento


def test_grupos_una_fila_por_grupo_aunque_falten_datos():
    import pandas as pd
    from tcf10 import metrics as M
    df = pd.DataFrame({"cohorte": ["C1"] * 4, "grupo": ["G1"] * 4, "perfil": ["A", "A", "Sin dato", "A"],
                       "nivel": "N", "docente": ["D1", "D1", "Sin dato", "D1"], "gestor": "X", "franja": "Mañana",
                       "id_sis": [1, 2, 3, 4], "estado": "Activo", "culmino": False, "horas_validas": 1.0,
                       "riesgo": "Bajo", "enrolado": True, "retirado": False})
    g = M.grupos(df)
    assert len(g) == 1 and g.iloc[0]["docente"] == "D1" and g.iloc[0]["integrantes"] == 4
