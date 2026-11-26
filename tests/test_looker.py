"""Tablas del Looker de Atenea (datos de demostración y un Sheet simulado)."""
import pandas as pd

from tcf10 import config as C
from tcf10 import looker


def test_tablas_cuadran_con_la_app():
    t = looker.tablas(permitir_demo=True)
    p, g = t["personas"], t["grupos"]
    assert p["personas"].sum() == g["personas"].sum()                         # mismo universo
    assert set(p["estado"]) <= set(C.ORDEN_ESTADOS)
    assert (g[C.ORDEN_ESTADOS].sum(axis=1) == g["personas"]).all()            # cada persona en un solo estado
    assert abs(p["horas_completadas"].sum() - g["horas_completadas_suma"].sum()) < 1
    assert (p["horas_completadas"] <= C.HORAS_TOTALES + 1e-9).all()
    assert "discapacidad" not in p                                             # dato sensible: solo agregado
    assert t["historico"]["personas"].sum() == len(p)


def test_valores_y_edad():
    assert looker._valor("2. NO") == "NO" and looker._valor("1. Sí") == "SI"
    assert looker._valor("") == C.SIN_INFO and looker._valor("SIN INFORMACION") == C.SIN_INFO
    assert looker.rango_edad(22) == "18 a 24" and looker.rango_edad(None) == C.SIN_INFO


class _WS:
    def __init__(self, filas=None):
        self.filas, self.row_count, self.col_count = filas or [], 1000, 26

    def resize(self, rows, cols):
        self.row_count, self.col_count = rows, cols

    def clear(self):
        self.filas = []

    def update(self, range_name, values, value_input_option):
        self.filas += values

    def get_all_records(self):
        return [dict(zip(self.filas[0], f)) for f in self.filas[1:]]


class _Libro:
    title = "prueba"

    def __init__(self):
        self.hojas = {}

    def worksheet(self, n):
        import gspread
        if n not in self.hojas:
            raise gspread.exceptions.WorksheetNotFound(n)
        return self.hojas[n]

    def add_worksheet(self, n, rows, cols):
        self.hojas[n] = _WS()
        return self.hojas[n]


def test_historico_acumula_y_reemplaza_el_dia():
    libro = _Libro()
    dia1 = pd.DataFrame({"fecha_foto": ["2026-11-25"], "grupo": ["A"], "personas": [3]})
    looker._escribir(libro, "historico", dia1, lambda *_: None)
    dia2 = pd.DataFrame({"fecha_foto": ["2026-11-26"], "grupo": ["A"], "personas": [4]})
    h = looker._historico(libro, dia2)
    assert h["fecha_foto"].tolist() == ["2026-11-25", "2026-11-26"]
    looker._escribir(libro, "historico", h, lambda *_: None)
    otra = pd.DataFrame({"fecha_foto": ["2026-11-26"], "grupo": ["A"], "personas": [5]})
    h = looker._historico(libro, otra)                                         # misma fecha: se reemplaza
    assert h["personas"].tolist() == [3, 5]
