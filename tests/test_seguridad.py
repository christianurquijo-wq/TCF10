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


# ------------------------------------------------------------------ usuarios con contraseña propia
class HojaUsuarios:
    def __init__(self):
        self.valores = [["Correo", "Nombre", "Estado"] + ["hash_contrasena", "creada", "actualizada", "codigo_hash",
                                                           "codigo_vence", "codigo_intentos", "envios"],
                        ["ana@agenciaatenea.gov.co", "Ana", "Activo"] + [""] * 7,
                        ["luis@agenciaatenea.gov.co", "Luis", "Inactivo"] + [""] * 7]

    def get_all_values(self):
        return [list(f) for f in self.valores]

    def batch_update(self, datos, value_input_option=None):
        from gspread.utils import a1_to_rowcol
        for d in datos:
            f, c = a1_to_rowcol(d["range"])
            self.valores[f - 1][c - 1] = d["values"][0][0]


@pytest.fixture
def hoja_usuarios(monkeypatch):
    from vista_atenea import usuarios as U
    h = HojaUsuarios()
    enviados = []
    monkeypatch.setattr(U, "_hoja", lambda: h)
    monkeypatch.setattr(U, "_cfg", lambda: {"correo_url": "x", "correo_secreto": "clave"})
    monkeypatch.setattr(U, "_enviar", lambda correo, nombre, codigo: enviados.append((correo, codigo)) or True)
    monkeypatch.setattr(S, "registrar", lambda *a, **k: None)
    return U, h, enviados


def test_crear_contrasena_con_codigo(hoja_usuarios):
    U, h, enviados = hoja_usuarios
    assert U.solicitar_codigo("Ana@AgenciaAtenea.gov.co") == "ok" and len(enviados) == 1
    codigo = enviados[0][1]
    assert codigo not in str(h.valores)                     # el código no se guarda en claro
    assert U.cambiar_con_codigo("ana@agenciaatenea.gov.co", "000000" if codigo != "000000" else "111111",
                                "Clave12345x") == "codigo"
    assert U.cambiar_con_codigo("ana@agenciaatenea.gov.co", codigo, "Clave12345x") == "ok"
    assert "Clave12345x" not in str(h.valores)              # solo la huella
    assert U.verificar_ingreso("ana@agenciaatenea.gov.co", "Clave12345x")["nombre"] == "Ana"
    assert U.verificar_ingreso("ana@agenciaatenea.gov.co", "otra") is None
    assert U.cambiar_con_codigo("ana@agenciaatenea.gov.co", codigo, "Clave12345y") == "codigo"  # un solo uso


def test_no_autorizados_y_limite(hoja_usuarios):
    U, h, enviados = hoja_usuarios
    assert U.solicitar_codigo("luis@agenciaatenea.gov.co") == "ok" and not enviados     # inactivo: no se envía
    assert U.solicitar_codigo("nadie@agenciaatenea.gov.co") == "ok" and not enviados    # no está en la lista
    for _ in range(3):
        assert U.solicitar_codigo("ana@agenciaatenea.gov.co") == "ok"
    assert U.solicitar_codigo("ana@agenciaatenea.gov.co") == "limite"
    assert U.validar_contrasena("corta1", "corta1")
    assert U.validar_contrasena("soloLetrasLargas", "soloLetrasLargas")
    assert U.validar_contrasena("Clave12345x", "Clave12345x") == ""
