"""Cortes semanales de la DB Formación (calendario, fórmulas con HOY() y flujo de copia con Drive simulado)."""
import pandas as pd
import pytest

from tcf10 import cortes as K
from tcf10.base_atenea import huella

T = pd.Timestamp


def test_ultimo_domingo_aguanta_cron_tarde():
    assert K.ultimo_domingo("2026-11-22") == T("2026-11-22")      # domingo 11:59 p. m.
    assert K.ultimo_domingo("2026-11-23") == T("2026-11-22")      # el cron arrancó el lunes de madrugada
    assert K.ultimo_domingo("2026-11-27") == T("2026-11-22")


def test_domingos_desde_inicio_hasta_cierre():
    # Inicia martes 13/10, último grupo termina el 04/12: cortes del 18/10 al domingo de cierre 06/12
    d = K.domingos(T("2026-10-13"), T("2026-12-04"), T("2026-12-31"))
    assert d[0] == T("2026-10-18") and d[-1] == T("2026-12-06") and len(d) == 8
    # Hoy viernes 27/11: solo los domingos cumplidos
    d = K.domingos(T("2026-10-13"), T("2026-12-04"), T("2026-11-27"))
    assert d[-1] == T("2026-11-22") and len(d) == 6
    assert K.domingos(T("2026-11-30"), T("2027-01-20"), T("2026-11-27")) == []   # aún no empieza
    assert K.domingos(None, None, T("2026-11-27")) == []


def test_calendario_usa_moda_de_inicio_y_ultimo_fin():
    i, f = K.calendario(pd.Series([T("2026-10-13")] * 3 + [T("2026-10-20")]),
                        pd.Series([T("2026-12-04"), T("2026-12-11"), None, None]))
    assert i == T("2026-10-13") and f == T("2026-12-11")


def test_semana_y_nombre():
    c = K.Cohorte("x", "01. DB Formación TCF10 - Cohorte1", T("2026-10-13"), T("2026-12-04"))
    assert c.semana(T("2026-10-18")) == 1 and c.semana(T("2026-11-22")) == 6 and c.semana(T("2026-12-20")) == 8
    assert K.nombre_corte(c, T("2026-11-22")) == ("01. DB Formación TCF10 - Cohorte1 · Corte S6 · domingo 22-11-2026 "
                                                  "11.59 p. m.")


def test_hoy_y_ahora_se_fijan_a_la_fecha_del_corte():
    f = K._fijar_hoy('=IF(TODAY()-O8>56,"Fin",IF(now() > P8,"x",""))', T("2026-11-22"))
    assert f == '=IF(DATE(2026,11,22)-O8>56,"Fin",IF((DATE(2026,11,22)+TIME(23,59,0)) > P8,"x",""))'
    assert K._fijar_hoy("=S8/90", T("2026-11-22")) == "=S8/90"


# ------------------------------------------------------------------ flujo completo con dobles
class Hoja:
    id = 7
    title = "Seg.Formación TCF10 C1"

    def __init__(self):
        enc = ["No.", "NUMERO_DOCUMENTO", "GRUPO DE FORMACIÓN", "FECHA_INICIO_FORMACIÓN", "FECHA_FIN_FORMACIÓN",
               "SÍNCRONO (35%)", "ASÍNCRONO (65%)", "PORCENTAJE_AVANCE_FORMACIÓN", "ESTADO_ESTUDIANTE"]
        self.valores = [[""] * 9 for _ in range(2)] + [enc, ["1", "1001343353", "", "", "", "0", "0", "0",
                                                              '=IF(TODAY()>E4,"Terminó","Activo")']]
        self.escrito = {}

    def get_all_values(self, value_render_option=None):
        return [list(f) for f in self.valores]

    def update(self, range_name, values, value_input_option=None):
        self.escrito[range_name] = values


class Libro:
    title = "01. DB Formación TCF10 - Cohorte1"

    def __init__(self):
        self.ws = Hoja()
        self.formulas, self.pegados, self.control = [], [], None

    def worksheets(self):
        return [self.ws]

    def worksheet(self, nombre):
        import gspread
        raise gspread.exceptions.WorksheetNotFound(nombre)

    def add_worksheet(self, nombre, rows, cols):
        libro = self

        class Control:
            id, title = 8, nombre

            def clear(self):
                pass

            def update(self, range_name, values, value_input_option=None):
                libro.control = values
        return Control()

    def values_batch_update(self, body):
        self.formulas += body["data"]

    def batch_update(self, body):
        self.pegados += body["requests"]


class Resp:
    def __init__(self, data, code=200):
        self.data, self.status_code, self.text = data, code, "x"

    def json(self):
        return self.data


class Sesion:
    def __init__(self):
        self.copias, self.papelera = [], []

    def post(self, url, params=None, json=None, timeout=None):
        self.copias.append((url, json))
        return Resp({"id": "copia1", "name": json["name"], "webViewLink": "https://docs/copia1"})

    def patch(self, url, params=None, json=None, timeout=None):
        self.papelera.append(url.rsplit("/", 1)[-1])
        return Resp({})


@pytest.fixture
def app():
    a = pd.DataFrame({"huella": huella(pd.Series(["1001343353"])), "grupo": ["M0101"],
                      "inicio": [T("2026-10-13")], "fin": [T("2026-12-04")], "sinc": [9.0], "asinc": [18.0],
                      "en_sis": [True]}).set_index("huella")
    a["pct"] = (a["sinc"] + a["asinc"]) / 90
    return a


def test_generar_uno_copia_escribe_fija_hoy_y_congela(app):
    libro, sesion = Libro(), Sesion()
    gc = type("GC", (), {"open_by_key": lambda self, _id: libro})()
    c = K.Cohorte("orig1", libro.title, T("2026-10-13"), T("2026-12-04"))
    r = K.generar_uno(gc, sesion, c, T("2026-11-01"), app, "carpeta", log=lambda *_: None)
    url, cuerpo = sesion.copias[0]
    assert url.endswith("/orig1/copy") and cuerpo["parents"] == ["carpeta"]
    assert cuerpo["appProperties"] == {"tcf10_tipo": K.TIPO, "tcf10_origen": "orig1", "tcf10_corte": "2026-11-01"}
    assert libro.ws.escrito["C4"][0] == ["M0101", "2026-10-13", "2026-12-04", 9.0, 18.0, 0.3]
    assert libro.ws.escrito["N3"] == [[3]]                                  # 01/11 = semana 3
    assert libro.formulas == [{"range": "'Seg.Formación TCF10 C1'!I4",
                               "values": [['=IF(DATE(2026,11,1)>E4,"Terminó","Activo")']]}]
    assert libro.pegados[0]["copyPaste"]["pasteType"] == "PASTE_VALUES"
    assert "Corte al domingo 01/11/2026" in libro.control[0][0]
    assert r["estado"] == "generado" and not sesion.papelera


def test_si_falla_la_copia_va_a_la_papelera(app):
    libro, sesion = Libro(), Sesion()
    libro.batch_update = lambda body: (_ for _ in ()).throw(RuntimeError("cuota"))
    gc = type("GC", (), {"open_by_key": lambda self, _id: libro})()
    c = K.Cohorte("orig1", libro.title, T("2026-10-13"), T("2026-12-04"))
    with pytest.raises(RuntimeError):
        K.generar_uno(gc, sesion, c, T("2026-11-01"), app, "carpeta", log=lambda *_: None)
    assert sesion.papelera == ["copia1"]
