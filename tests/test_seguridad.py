"""Registro de accesos, bloqueo por intentos y Excel confidencial (sin conexión: hoja simulada)."""
import datetime as dt
import io

import pandas as pd
import pytest
import streamlit as st

from vista_atenea import legal, seguridad as S


class HojaFalsa:
    def __init__(self, filas):
        self.filas = filas

    def get(self, rango):
        return self.filas


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    yield


def _t(min_atras):
    return (S.ahora() - dt.timedelta(minutes=min_atras)).strftime(S.FORMATO)


def test_bloqueo_desde_registro(monkeypatch):
    filas = [[_t(10 - i), "ingreso_fallido", "ana"] for i in range(5)]
    monkeypatch.setattr(S, "_hoja", lambda: HojaFalsa(filas))
    hasta = S.bloqueado_hasta("Ana")
    assert hasta is not None and hasta > S.ahora()


def test_ingreso_exitoso_reinicia_contador(monkeypatch):
    filas = [[_t(12), "ingreso_fallido", "ana"]] * 4 + [[_t(8), "ingreso", "ana"], [_t(5), "ingreso_fallido", "ana"]]
    monkeypatch.setattr(S, "_hoja", lambda: HojaFalsa(filas))
    assert S.bloqueado_hasta("ana") is None


def test_fallos_viejos_no_cuentan(monkeypatch):
    filas = [[_t(30 + i), "ingreso_fallido", "ana"] for i in range(6)]
    monkeypatch.setattr(S, "_hoja", lambda: HojaFalsa(filas))
    assert S.bloqueado_hasta("ana") is None


def test_ya_acepto(monkeypatch):
    filas = [[_t(1), "acepta_terminos", "ana@agenciaatenea.gov.co", "google", "", legal.VERSION_TERMINOS, "x"]]
    monkeypatch.setattr(S, "_hoja", lambda: HojaFalsa(filas))
    assert S.ya_acepto("ana@agenciaatenea.gov.co", legal.VERSION_TERMINOS)
    assert not S.ya_acepto("otro@agenciaatenea.gov.co", legal.VERSION_TERMINOS)


def test_excel_confidencial():
    st.session_state["seg_usuario"] = "ana"
    datos = S.excel_confidencial(pd.DataFrame({"Nombre": ["A", "B"], "Documento": ["1", "2"]}), "Participantes", "TCF10")
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(datos))
    ws = wb["Participantes"]
    assert "CONFIDENCIAL" in ws["A1"].value and "ana" in ws["A1"].value
    assert ws["A4"].value == "Nombre" and ws["A5"].value == "A"
    assert "ana" in wb.properties.description


def test_zip_vistas_crudas(monkeypatch):
    import types
    import zipfile

    from tcf10 import data

    class Res:
        schema = [types.SimpleNamespace(name="id_sis"), types.SimpleNamespace(name="nombre")]

        def __iter__(self):
            for f in ({"id_sis": 1, "nombre": "Ana, Pérez"}, {"id_sis": 2, "nombre": None}):
                yield types.SimpleNamespace(values=f.values)

    class Cliente:
        def query(self, sql):
            assert sql.startswith("SELECT * FROM `")
            return types.SimpleNamespace(result=lambda page_size=None: Res())

    monkeypatch.setattr(data, "_cliente_bq", lambda: Cliente())
    datos, filas = data.zip_vistas_crudas("CONFIDENCIAL")
    zf = zipfile.ZipFile(io.BytesIO(datos))
    assert sorted(zf.namelist()) == sorted(["LEEME.txt"] + [v + ".csv" for v in data.VISTAS_CRUDAS])
    texto = zf.read("VTD10_student_basic_info.csv").decode("utf-8-sig")
    assert texto.splitlines() == ["id_sis,nombre", '1,"Ana, Pérez"', "2,"]
    assert set(filas.values()) == {2}
