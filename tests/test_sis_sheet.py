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
                            pd.Series(["2026-11-10 08:00:00", "2026-11-12 08:00:00", "2026-11-14 14:00:00",
                                       "2026-11-10 18:30:00"])).set_index("grupo")["franja"]
    assert f["G1"] == "Mañana · 8:00" and f["G2"] == "Noche · 18:30"


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
    assert S.fuente_plataforma(t) == "pedagogical_time"
    av = S.avance(t, [101, 102, 103], horas_sesion=3.0, divisor_tiempo=60).set_index("id_sis")
    assert av.loc[101, "horas_asinc"] == pytest.approx(2.5)   # no usa course_time_view (7200 s) ni el divisor 60
    assert av.loc[102, "horas_asinc"] == pytest.approx(0.5)
    assert av.loc[103, "horas_asinc"] == 0


def test_sin_pestana_pedagogica_usa_respaldo():
    t = S.preparar(_crudas())
    assert S.fuente_plataforma(t) == "course_time_view"
