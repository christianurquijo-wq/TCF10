"""Datos de las gráficas de la página Progreso (vista Atenea)."""
import pandas as pd

from vista_atenea import graficas as G


def test_horas_por_grupo_ordena_por_brecha_frente_al_plan():
    form = pd.DataFrame({"grupo": ["A", "A", "B", "C"], "horas_sinc_val": [10, 12, 5, 0], "horas_asinc_val": [20, 18, 5, 0],
                         "horas_validas": [30, 30, 10, 0], "avance_esperado_h": [25, 25, 30, None],
                         "perfil": ["x"] * 4, "nivel": ["Básico"] * 4})
    g = G.datos_horas_grupo(form)
    assert g["grupo"].tolist() == ["B", "A", "C"]          # B: -20 h, A: +5 h, C sin plan al final
    assert g.loc[g["grupo"] == "A", "total"].item() == 30 and g.loc[g["grupo"] == "A", "personas"].item() == 2


def test_cursos_por_programa_y_nivel():
    prog = pd.DataFrame({"curso": ["Nivel Avanzado - Marketing digital y finanzas con enfoque en Inteligencia Artificial",
                                   "Nivel Básico - Marketing digital y finanzas con enfoque en Inteligencia Artificial"],
                         "completado": [1, 2], "en_progreso": [3, 6], "sin_iniciar": [0, 2]})
    c = G.datos_cursos(prog)
    assert c["nivel"].tolist() == ["Básico", "Avanzado"] and set(c["programa"]) == {"Marketing y finanzas"}
    assert abs(c["pct_completado"].iloc[0] - 0.2) < 1e-9 and c["inscripciones"].tolist() == [10, 4]
