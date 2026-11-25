"""Actualización de la DB Formación (hoja simulada con la estructura real: títulos en la fila 7, datos desde la 8)."""
import pandas as pd

from tcf10 import db_formacion as D
from tcf10.base_atenea import huella


class Hoja:
    title = "Seg.Formación TCF10 C2"

    def __init__(self):
        enc = ["No.", "ID_PERSONA", "NUMERO_DOCUMENTO", "CONVOCATORIA", "OPERADOR_FORMACIÓN", "COHORTE",
               "PRIMER_NOMBRE", "SEGUNDO_NOMBRE", "PRIMER_APELLIDO", "SEGUNDO_APELLIDO", "ID_CURSO\n(CURSO DEFINITIVO)",
               "NOMBRE_CURSO\n(CURSO DEFINITIVO)", "NIVEL CURSO\n(CURSO DEFINITIVO)", "GRUPO DE FORMACIÓN",
               "FECHA_INICIO_FORMACIÓN", "FECHA_FIN_FORMACIÓN", "SÍNCRONO\n(35%)", "ASÍNCRONO\n(65%)",
               "PORCENTAJE_AVANCE_FORMACIÓN", "ICP", "ESTADO_ESTUDIANTE"]
        vacia = [""] * len(enc)
        self.valores = [list(vacia) for _ in range(6)] + [enc]
        for i, doc in enumerate(["1001343353", "1024460594", "999"]):
            f = list(vacia); f[0] = str(i + 1); f[2] = doc; f[18] = "0"; f[19] = "=S8/..."
            self.valores.append(f)
        self.escrito = {}

    def get_all_values(self):
        return [list(f) for f in self.valores]

    def update(self, range_name, values, value_input_option=None):
        self.escrito[range_name] = values


class Libro:
    title = "02. DB Formación TCF10 - Cohorte2"

    def __init__(self):
        self.ws = Hoja()
        self.control = None

    def worksheets(self):
        return [self.ws]

    def worksheet(self, nombre):
        import gspread
        raise gspread.exceptions.WorksheetNotFound(nombre)

    def add_worksheet(self, nombre, rows, cols):
        libro = self

        class Control:
            def clear(self):
                pass

            def update(self, range_name, values, value_input_option=None):
                libro.control = values
        return Control()


def test_actualiza_columnas_n_a_s_y_semana():
    libro = Libro()
    gc = type("GC", (), {"open_by_key": lambda self, _id: libro})()
    app = pd.DataFrame({
        "huella": huella(pd.Series(["1001343353", "1024460594"])),
        "grupo": ["M0136", None], "inicio": [pd.Timestamp("2026-11-10"), pd.NaT],
        "fin": [pd.Timestamp("2026-12-29"), pd.NaT], "sinc": [12.0, 0.0], "asinc": [33.0, 0.0],
        "en_sis": [True, False]}).set_index("huella")
    app["pct"] = (app["sinc"] + app["asinc"]) / 90
    r = D.actualizar_libro(gc, "x", app, pd.Timestamp("2026-11-25"), log=lambda *_: None)
    bloque = libro.ws.escrito["N8"]
    assert bloque[0] == ["M0136", "2026-11-10", "2026-12-29", 12.0, 33.0, 0.5]
    assert bloque[1] == ["", "", "", 0, 0, 0]            # sin usuario en el SIS
    assert bloque[2] == ["", "", "", 0, 0, 0]            # no está en la base
    assert libro.ws.escrito["N3"] == [[3]]               # 15 días desde el 10/11 → semana 3
    assert r["sin_cruce"] == 2 and len(libro.control) == 4
    assert "ICP" not in str(libro.ws.escrito)            # las fórmulas no se tocan
