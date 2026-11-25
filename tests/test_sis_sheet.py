"""Fuente SIS desde Google Sheets: misma lógica que las consultas de BigQuery, sobre pestañas sintéticas."""
import pandas as pd
import pytest

from tcf10 import sis_sheet as S


def _crudas():
    alumnos = [(101, "Ana María Pérez", "G1"), (102, "Luis Gómez", "G1"), (103, "Sara Ruiz", "G2")]
    asis_det, asis_res, basica, prog_cur, prog_det, login = [], [], [], [], [], []
    for inc, nom, g in alumnos:
        basica.append({"user_incremental": inc, "user_full_name": nom, "program_name": "Auxiliar",
                       "level_name": "Básico", "contact_incremental": ""})
        for k in range(1, 5):
            pasada = k <= 3
            att = 1 if (pasada and inc != 103 and k != 3) else 0
            nreg = 1 if (pasada and k == 3) else 0
            asis_det.append({"user_id": "x", "incremental": inc, "student_name": nom, "student_doc": 1,
                             "group_name": g, "session_id": f"{g}-{k}", "session_number": k,
                             "session_date": f"2026-10-0{k}", "attended": att,
                             "not_attended": int(pasada and not att and not nreg), "not_registered": nreg,
                             "is_past_session": pasada, "last_updated_class_session": "2026-11-13 06:00:00"})
        asis_res.append({"incremental": inc, "program_name": "Auxiliar", "group_name": g, "total_sessions": 4,
                         "attended_sessions": 2 if inc != 103 else 0, "not_attended_sessions": 0 if inc != 103 else 2,
                         "total_sessions_to_date": 3,
                         "last_attendance_date": "2026-10-02 10:00:00" if inc != 103 else "",
                         "last_updated_class_session": "2026-11-13 06:00:00", "student_name": nom})
        prog_cur.append({"incremental": inc, "group_name": g, "group_start_date": "2026-10-01",
                         "group_end_date": "2026-12-15", "course_name": "Módulo 1",
                         "course_completed_status": 50, "lessons_active": 10, "lessons_completed": 5,
                         "course_time_view": 7200 if inc == 101 else "", "progress_status": "en_progreso",
                         "email": "no@usar"})
        prog_det.append({"incremental": inc, "completed_date": "2026-11-10T09:00:00",
                         "last_updated_statistics": "2026-11-13 05:00:00", "lesson_name": "Lección 1",
                         "course_name": "Módulo 1"})
        login.append({"incremental": inc, "log_date": "2026-11-12", "time_view": 1800})
    return {"asis_det": pd.DataFrame(asis_det), "asis_res": pd.DataFrame(asis_res),
            "basica": pd.DataFrame(basica), "prog_cur": pd.DataFrame(prog_cur),
            "prog_det": pd.DataFrame(prog_det), "login": pd.DataFrame(login)}


def test_descarta_datos_personales():
    t = S.preparar(_crudas())
    for df in t.values():
        assert not {"student_name", "user_full_name", "email", "student_doc"} & set(df.columns)
    assert t["basica"].set_index("id_sis").loc[101, "iniciales"] == "A.M.P."


def test_avance_horas_y_ultima_actividad():
    t = S.preparar(_crudas())
    av = S.avance(t, [101, 102, 103], horas_sesion=3.0, divisor_tiempo=3600).set_index("id_sis")
    assert av.loc[101, "horas_sinc"] == 6.0
    assert av.loc[101, "horas_asinc"] == pytest.approx(2.0)
    assert av.loc[102, "horas_asinc"] == 0
    assert av.loc[103, "ultima_actividad"] == pd.Timestamp("2026-11-12")  # el ingreso es lo más reciente
    assert av.loc[101, "grupo_sis"] == "G1"
    assert av.loc[101, "actualizado_sis"] == pd.Timestamp("2026-11-13 05:00:00")


def test_base_y_agregados():
    t = S.preparar(_crudas())
    b = S.base(t).set_index("id_sis")
    assert len(b) == 3 and b.loc[103, "grupo"] == "G2"
    assert b.loc[101, "fecha_inicio"] == pd.Timestamp("2026-10-01")
    asis, prog = S.agregados(t, [101, 102, 103])
    g1 = asis[asis["grupo"] == "G1"]
    assert g1["session_id"].nunique() == 3          # solo sesiones pasadas
    assert g1["asistieron"].sum() == 4 and g1["sin_registro"].sum() == 2
    assert prog["en_progreso"].sum() == 3


def test_fechas_serial_y_dia_mes():
    s = S._fecha(pd.Series([46339, "13/11/2026", "2026-11-13 08:00:00", ""]))
    assert s.iloc[0] == pd.Timestamp("2026-11-13")
    assert s.iloc[1] == pd.Timestamp("2026-11-13")
    assert pd.isna(s.iloc[3])


def test_fechas_con_zona_horaria_mezcladas():
    s = S._fecha(pd.Series(["2026-11-10 14:00:00 UTC", "2026-11-10T14:00:00+00:00", "2026-11-10 09:00:00",
                            "05/11/2026", None, "basura"]))
    assert s.dtype == "datetime64[ns]"
    assert s.iloc[0] == pd.Timestamp("2026-11-10 09:00:00")   # UTC → Bogotá
    assert s.iloc[1] == pd.Timestamp("2026-11-10 09:00:00")
    assert s.iloc[2] == pd.Timestamp("2026-11-10 09:00:00")   # sin zona: se respeta
    assert s.iloc[3] == pd.Timestamp("2026-11-05")            # día/mes/año
    assert pd.isna(s.iloc[4]) and pd.isna(s.iloc[5])


def test_pestana_faltante():
    c = _crudas(); c.pop("asis_res")
    with pytest.raises(S.FaltaEstructura):
        S.preparar(c)


def test_franja_por_hora_de_inicio_mas_comun():
    f = S.franjas_por_grupo(pd.Series(["G1", "G1", "G1", "G2"]),
                            pd.Series(["2026-11-10 03:00:00", "2026-11-12 03:00:00", "2026-11-14 09:00:00",
                                       "2026-11-10 12:00:00"])).set_index("grupo")["franja"]
    assert f["G1"] == "Mañana · 8:00 a. m." and f["G2"] == "Noche · 5:00 p. m."
    g = S.franjas_por_grupo(pd.Series(["G3"]), pd.Series(["2026-11-10 08:05:00"])).set_index("grupo")["franja"]
    assert g["G3"] == "Tarde · 1:00 p. m."


def test_horas_plataforma_acreditadas_desde_pedagogical_time():
    c = _crudas()
    # detalle por lección: 101 tiene dos lecciones (3600 + 5400 s = 2,5 h), 102 una (1800 s), 103 vacío
    extra = pd.DataFrame({"incremental": [101, 102], "completed_date": "2026-11-11T09:00:00",
                          "last_updated_statistics": "2026-11-13 05:00:00", "lesson_name": "Lección 2",
                          "course_name": "Módulo 1"})
    det = pd.concat([c["prog_det"], extra], ignore_index=True)
    det["pedagogical_time"] = [3600, 0, "", "5400", 1800]   # filas: 101, 102, 103, 101, 102
    c["prog_det"] = det
    t = S.preparar(c)
    assert S.fuente_plataforma(t) == "pedagogical_time_sin_filtro"  # sin component_category / is_completed
    av = S.avance(t, [101, 102, 103], horas_sesion=3.0, divisor_tiempo=60).set_index("id_sis")
    assert av.loc[101, "horas_asinc"] == pytest.approx(2.5)   # no usa course_time_view (7200 s) ni el divisor 60
    assert av.loc[102, "horas_asinc"] == pytest.approx(0.5)
    assert av.loc[103, "horas_asinc"] == 0


def test_sin_pestana_pedagogica_usa_respaldo():
    t = S.preparar(_crudas())
    assert S.fuente_plataforma(t) == "course_time_view"


def test_avance_del_curso_coherente_con_lecciones():
    pc = pd.DataFrame({"course_completed_status": [100, 100, 0, 80], "lessons_active": [44, 44, 10, 0],
                       "lessons_completed": [36, 44, 0, 0],
                       "progress_status": ["completado", "completado", "en_progreso", "en_progreso"]})
    r = S.avance_por_lecciones(pc)
    assert r["course_completed_status"].round(1).tolist() == [81.8, 100.0, 0.0, 80.0]
    assert r["progress_status"].tolist() == ["en_progreso", "completado", "en_progreso", "en_progreso"]



def test_pedagogical_time_solo_recursos_completados():
    """Regla de Looker Studio: component_category = "resource" AND is_completed = TRUE."""
    c = _crudas()
    det = pd.concat([c["prog_det"]] * 2, ignore_index=True)          # 6 filas: 101,102,103,101,102,103
    det["pedagogical_time"] = [3600, 1800, 900, 7200, 600, 300]
    det["component_category"] = ["resource", "resource", "quiz", "resource", "Resource ", "resource"]
    det["is_completed"] = [True, "FALSE", True, "TRUE", 1, ""]
    c["prog_det"] = det
    t = S.preparar(c)
    assert S.fuente_plataforma(t) == "pedagogical_time"
    h = S.horas_plataforma(t, [101, 102, 103])
    assert h[101] == pytest.approx(3.0)          # 3600 + 7200 s
    assert h[102] == pytest.approx(600 / 3600)   # la de 1800 s no está completada
    assert h[103] == 0                           # quiz y recurso sin completar no cuentan


def test_consulta_por_estudiante_es_la_fuente_principal():
    c = _crudas()
    # misma forma que la pestaña «Consulta por estudiante» (BigQuery vinculado); datos sintéticos
    c["prog_est"] = pd.DataFrame({
        "incremental": [101, 101, 102, 103], "student_name": ["X Y", "X Y", "Z W", "Q R"],
        "student_doc": ["111", "111", "222", "333"], "group_name": ["G1", "G1", "G1", "G2"],
        "horas_plataforma_acreditadas": ["8.333", "1.667", "0.0", ""],
        "ultima_fecha_completada": ["2026-11-14 16:12:14.000000 UTC", "", "", ""],
        "ultima_leccion": ["Feedback 4", "", "", ""], "ultimo_curso": ["Nivel Avanzado", "", "", ""],
        "last_updated_statistics": ["2026-11-19T17:49:49.475000"] * 4})
    t = S.preparar(c)
    assert S.fuente_plataforma(t) == "consulta_por_estudiante"
    assert not {"student_name", "student_doc"} & set(t["prog_est"].columns)   # sin datos personales
    av = S.avance(t, [101, 102, 103], horas_sesion=3.0, divisor_tiempo=3600).set_index("id_sis")
    assert av.loc[101, "horas_asinc"] == pytest.approx(10.0)   # suma de sus filas (grupo/materia)
    assert av.loc[102, "horas_asinc"] == 0 and av.loc[103, "horas_asinc"] == 0
    # 14/11 16:12 UTC = 11:12 en Bogotá, más reciente que el detalle (10/11)
    assert S.ultima_leccion(t, 101) == ("Feedback 4", pd.Timestamp("2026-11-14 11:12:14"), "Nivel Avanzado")
    assert S.ultima_leccion(t, 102)[0] == "Lección 1"           # sin dato en la consulta: usa el detalle


def test_franjas_corrige_desfase_de_bigquery():
    # BigQuery guarda la hora 5 h atrás: 03:00 → Mañana (8:00), 08:00 → Tarde (13:00), 12:00 → Noche (17:00)
    import pandas as pd
    from tcf10 import sis_sheet as S
    g = pd.Series(["A", "A", "B", "C", "D"])
    ini = pd.Series(["2026-11-10 03:00:00", "2026-11-11 03:00:00", "2026-11-10 08:00:00",
                     "2026-11-10 12:00:00", pd.Timestamp("2026-11-10 12:00", tz="UTC")])
    fr = S.franjas_por_grupo(g, ini).set_index("grupo")["franja"]
    assert fr["A"].startswith("Mañana") and fr["B"].startswith("Tarde")
    assert fr["C"].startswith("Noche") and fr["D"].startswith("Noche")


def _con_recursos():
    c = _crudas()
    filas = []
    for inc in (101, 102):
        for k, (fecha, seg, cat, comp) in enumerate([("2026-10-02T10:00:00", 1800, "resource", True),
                                                      ("2026-10-05T10:00:00", 3600, "resource", True),
                                                      ("2026-10-06T10:00:00", 900, "quiz", True),
                                                      ("", 600, "resource", True)]):
            filas.append({"incremental": inc, "completed_date": fecha, "last_updated_statistics": "2026-11-13 05:00:00",
                          "lesson_name": f"Tema {k}", "course_name": "Módulo 1", "component_name": f"Recurso {k}",
                          "component_category": cat, "is_completed": comp, "pedagogical_time": seg})
    c["prog_det"] = pd.DataFrame(filas)
    return c


def test_recursos_cuadran_con_horas_y_corte():
    t = S.preparar(_con_recursos())
    rec = S.recursos(t, [101])
    assert list(rec["recurso"].fillna("")) == ["Recurso 0", "Recurso 1", "Recurso 3"]   # el quiz no cuenta
    assert rec["horas"].sum() == pytest.approx((1800 + 3600 + 600) / 3600)
    # al 3 de octubre solo el primer recurso (y el que no trae fecha)
    al3 = S.recursos(t, [101], pd.Timestamp("2026-10-03"))
    assert al3["horas"].sum() == pytest.approx((1800 + 600) / 3600)
    av = S.avance(t, [101, 103], 4.0, 3600, corte=pd.Timestamp("2026-10-02")).set_index("id_sis")
    assert av.loc[101, "horas_asinc"] == pytest.approx((1800 + 600) / 3600, abs=0.01)
    assert av.loc[101, "sesiones_asistidas"] == 2      # sesiones del 1 y 2 de octubre
    assert av.loc[101, "horas_sinc"] == 8.0
    assert av.loc[101, "sesiones_a_la_fecha"] == 2
    asis, _ = S.agregados(t, [101, 102, 103], pd.Timestamp("2026-10-01"))
    assert set(asis["sesion"]) == {1}
