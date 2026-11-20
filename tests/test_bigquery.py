"""Fuente BigQuery directa: con resultados tipados como los de BigQuery debe dar lo mismo que la copia en Sheets."""
import re

import pandas as pd
import pytest

from tcf10 import data, sis_sheet as S
from test_sis_sheet import _crudas


def _tipado(df: pd.DataFrame) -> pd.DataFrame:
    """Simula tipos de BigQuery: INT64, TIMESTAMP (UTC), BOOL."""
    out = df.copy()
    for c in out.columns:
        if c in ("incremental", "user_incremental", "session_number", "attended", "not_attended", "not_registered"):
            out[c] = pd.to_numeric(out[c], errors="coerce").astype("Int64")
        elif c == "is_past_session":
            out[c] = out[c].astype("boolean")
        elif c in ("last_updated_class_session", "last_updated_statistics"):
            out[c] = pd.to_datetime(out[c]).dt.tz_localize("America/Bogota").dt.tz_convert("UTC")
    return out


@pytest.fixture
def bq(monkeypatch):
    crudas = {k: _tipado(v) for k, v in _crudas().items()}
    est = pd.DataFrame({"incremental": pd.array([101, 102], dtype="Int64"),
                        "horas_plataforma_acreditadas": [7.5, 0.0],
                        "ultima_fecha_completada": pd.to_datetime(["2026-11-14 16:12:14", None]).tz_localize("UTC"),
                        "ultima_leccion": ["Feedback 4", None], "ultimo_curso": ["Nivel Avanzado", None],
                        "last_updated_statistics": pd.to_datetime(["2026-11-19 17:49:49"] * 2).tz_localize("UTC")})
    vistas = {v: k for k, v in S.PESTANAS.items()}
    consultas = []

    def consulta(cliente, sql, nombre):
        consultas.append(sql)
        if "INFORMATION_SCHEMA" in sql:
            return pd.DataFrame([(v, c) for v, k in vistas.items() for c in crudas[k].columns],
                                columns=["table_name", "column_name"])
        if "horas_plataforma_acreditadas" in sql:
            return est
        vista = re.search(r"\.(VTD10_\w+)`", sql).group(1)
        cols = re.findall(r"`(\w+)`", sql.split(" FROM ")[0])
        return crudas[vistas[vista]][cols]

    monkeypatch.setattr(data, "_cfg", lambda: {"sis_dataset": "proyecto.DVTD_SIS"})
    monkeypatch.setattr(data, "_cliente_bq", lambda: type("C", (), {"project": "proyecto"})())
    monkeypatch.setattr(data, "_consulta", consulta)
    return consultas


def test_bigquery_entrega_las_mismas_tablas(bq):
    t = data._sis_bigquery()
    assert S.fuente_plataforma(t) == "consulta_por_estudiante"
    av = S.avance(t, [101, 102, 103], horas_sesion=4.0, divisor_tiempo=3600).set_index("id_sis")
    assert av.loc[101, "horas_sinc"] == 8.0                     # 2 sesiones × 4 h
    assert av.loc[101, "horas_asinc"] == pytest.approx(7.5)     # horas_plataforma_acreditadas
    assert av.loc[103, "horas_sinc"] == 0
    assert S.ultima_leccion(t, 101) == ("Feedback 4", pd.Timestamp("2026-11-14 11:12:14"), "Nivel Avanzado")
    assert t["basica"].set_index("id_sis").loc[101, "iniciales"] == "A.M.P."
    for df in t.values():                                        # sin datos personales
        assert not {"student_name", "user_full_name", "student_doc", "email"} & set(df.columns)


def test_bigquery_excluye_usuarios_de_prueba_y_pide_solo_columnas_necesarias(bq):
    data._sis_bigquery()
    lecturas = [q for q in bq if "INFORMATION_SCHEMA" not in q]
    assert all("NOT IN (3172, 2980)" in q for q in lecturas)
    assert not any("SELECT *" in q for q in lecturas)
