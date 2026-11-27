"""pytest -q tests/test_consultas.py · asistente de datos de la vista interna (con los datos de demostración)."""
import pandas as pd
import pytest

from tcf10 import config as C
from tcf10 import consultas as Q
from tcf10 import data, metrics, ui


@pytest.fixture(scope="module")
def df():
    if not data.modo_demo():
        pytest.skip("las pruebas usan los datos de demostración")
    d, _ = ui._preparado(ui.hoy_real(), metrics.VERSION, False)
    return Q.preparar_base(d)


def en_curso(df):
    return df[df["enrolado"] & ~df["retirado"] & df["cohorte_iniciada"] & ~df["cohorte_cerrada"] & ~df["culmino"]]


def test_solo_plataforma_coincide_con_la_tipificacion(df):
    a = Q.POR_CLAVE["solo_plataforma"]
    r = Q.aplicar(df, a.filtros)
    esperado = en_curso(df)["tipo_ruta"].eq("Solo plataforma").sum()
    assert len(r) == esperado > 0
    assert (r["clases_faltantes"] == 0).all()


def test_criticos_igual_que_la_pagina(df):
    r = Q.aplicar(df, Q.POR_CLAVE["criticos"].filtros)
    assert len(r) == int(en_curso(df)["critico"].sum())


def test_filtros_se_combinan_con_y(df):
    grupo = df["grupo"].dropna().iloc[0]
    f = Q.Filtros("en_curso", cat={"grupo": [grupo], "tipo_ruta": ["1 clase + plataforma"]})
    r = Q.aplicar(df, f)
    assert r["grupo"].eq(grupo).all() and r["tipo_ruta"].eq("1 clase + plataforma").all()
    assert "Grupo: " + str(grupo) in Q.describir(f)


def test_rango_y_fecha(df):
    f = Q.Filtros("en_curso", rango={"horas_validas": (10, 30)})
    r = Q.aplicar(df, f)
    assert r["horas_validas"].between(10, 30).all()
    dia = pd.Timestamp("2026-11-05")
    r = Q.aplicar(df, Q.Filtros("en_curso", fecha={"ultima_actividad": ("antes", dia)}))
    ult = pd.to_datetime(r["ultima_actividad"])
    assert (ult.isna() | (ult < dia)).all()


def test_resumen_total_cuadra(df):
    d = Q.aplicar(df, Q.Filtros("todos"))
    t = Q.resumen(d, "cohorte")
    assert t.iloc[-1]["Cohorte"] == "Total"
    assert t.iloc[-1]["Personas"] == len(d) == t.iloc[:-1]["Personas"].sum()


def test_distribucion_oculta_conteos_pequenos_sensibles():
    d = pd.DataFrame({"discapacidad": ["Sí"] * 3 + ["No"] * 8, "riesgo": [C.APROBADO] * 11})
    t = Q.distribucion(d, "discapacidad", "riesgo")
    fila_si = t[t["Discapacidad"] == "Sí"].iloc[0] if "Discapacidad" in t else t[t.iloc[:, 0] == "Sí"].iloc[0]
    assert fila_si[C.APROBADO] == "< 5"
    assert Q.Filtros(cat={"discapacidad": ["Sí"]}).sensible()


def test_faltas_por_rango(df):
    det = data.asistencia_detalle()
    personas = Q.aplicar(df, Q.Filtros("activos"))
    desde, hasta = det["fecha"].min(), det["fecha"].min() + pd.Timedelta(days=10)
    r = Q.faltas(det, personas, desde, hasta)
    assert len(r) > 0
    assert r["estado_asistencia"].eq("No asistió").all()
    assert pd.to_datetime(r["fecha"]).between(desde, hasta).all()


def test_csv_para_excel_en_espanol():
    t = Q.para_csv(pd.DataFrame({"horas_validas": [12.345], "critico": [True],
                                 "ultima_actividad": [pd.Timestamp("2026-11-03")]}))
    b = Q.a_csv(t)
    assert b.startswith(b"\xef\xbb\xbf")                     # BOM: Excel lee las tildes
    texto = b.decode("utf-8-sig")
    assert texto.splitlines()[0] == "Horas completadas;Caso crítico;Última actividad"
    assert texto.splitlines()[1] == "12,3;Sí;03/11/2026"


def test_todos_los_atajos_corren(df):
    for a in Q.ATAJOS:
        if a.tipo == "lista":
            r = Q.lista(Q.aplicar(df, a.filtros), a.columnas, a.orden, a.asc)
            assert all(c in Q.CAMPOS for c in r.columns)
