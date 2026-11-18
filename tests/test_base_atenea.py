"""Base «DB Formalización TCF10»: cruce por documento con el SIS, sin guardar datos personales."""
import pandas as pd

from tcf10 import base_atenea as B
from tcf10 import metrics as M

ENC = ["No.", "COHORTE", "ID_PERSONA", "RESULTADO", "TIPO_DOCUMENTO", "NUMERO_DOCUMENTO", "PRIMER_NOMBRE",
       "SEGUNDO_NOMBRE", "PRIMER_APELLIDO", "SEGUNDO_APELLIDO", "CORREO", "SDIS_TRABAJANDO", "TEMÁTICA",
       "NIVEL_CURSO_ASIGNADO", "RESULTADO OPERADOR\n- Formalizado.\n- No formalizado.\n- Desistido"]


def _valores():
    marca = [""] * len(ENC); marca[11] = "Actualizar"
    filas = [
        ["1", "Cohorte 1", "", "JcO", "CC", "1.000.111", "Ana", "", "Pérez", "Ruiz", "a@x.co", "NO",
         "Marketing digital y finanzas con enfoque en Inteligencia Artificial", "Básico", "Formalizado"],
        ["2", "Cohorte 2", "", "JcO", "CC", "2000222", "Luis", "", "Gómez", "", "l@x.co", "1. SI",
         "Auxiliar de información y Servicio al cliente con enfoque en Inteligencia Artificial", "Avanzado",
         "Formalizado"],
        ["3", "No aplica", "", "JcO", "CC", "3000333", "Eva", "", "Díaz", "", "e@x.co", "SIN INFORMACION",
         "Marketing digital y finanzas con enfoque en Inteligencia Artificial", "", "No Formalizado"],
        ["4", "Cohorte 1", "", "JcO", "CC", "4000444", "Sol", "", "Mora", "", "s@x.co", "2. NO",
         "Marketing digital y finanzas con enfoque en Inteligencia Artificial", "Intermedio", "Desistido"],
    ]
    return [marca, ENC] + filas


def test_encabezado_en_segunda_fila_y_sin_datos_personales():
    vals = _valores()
    assert B.es_formalizacion(vals)
    crudo = B.a_dataframe(vals)
    mapa = dict(zip(B.huella(pd.Series(["1000111", "2000222", "4000444"])), [11, 22, 44]))
    b = B.limpiar(crudo, mapa).set_index("id_sis")
    assert b.loc[11, "nombre"] == "A.P.R." and b.loc[11, "perfil"] == "Marketing y finanzas"
    assert b.loc[11, "lab_inicio"] == "Desempleado" and b.loc[22, "lab_inicio"] == "Trabajando"
    assert bool(b.loc[44, "enrolado"]) and b.loc[44, "estado"] == "Retirado"
    sin_sis = b[b.index < 0]
    assert len(sin_sis) == 1 and sin_sis["cohorte"].iloc[0] == "No formalizados" and not sin_sis["enrolado"].iloc[0]
    assert b["documento"].isna().all()
    assert not {"CORREO", "PRIMER_NOMBRE"} & set(b.columns)


def test_calendario_desde_grupos_sis_y_riesgo_sin_usuario():
    crudo = B.a_dataframe(_valores())
    mapa = dict(zip(B.huella(pd.Series(["1000111", "4000444"])), [11, 44]))   # Luis no está en el SIS
    b = B.limpiar(crudo, mapa)
    g = pd.DataFrame({"id_sis": [11, 44], "grupo": ["M0101", "M0102"],
                      "fecha_inicio": pd.to_datetime(["2026-11-10", "2026-11-11"]),
                      "fecha_fin": pd.to_datetime(["2027-02-20", "2027-02-21"])})
    b, coh = B.calendario(b, g)
    c1 = coh.set_index("cohorte").loc["Cohorte 1"]
    assert c1["fecha_inicio"] == pd.Timestamp("2026-11-10")
    av = pd.DataFrame(columns=["id_sis", "horas_sinc", "horas_asinc", "ultima_actividad"])
    df = M.preparar(b, av, coh.assign(fecha_inicio=coh["fecha_inicio"].fillna(pd.Timestamp("2026-11-10")),
                                      fecha_fin=coh["fecha_fin"].fillna(pd.Timestamp("2027-02-20"))),
                    pd.Timestamp("2026-11-18"))
    luis = df[(df["id_sis"] < 0) & df["enrolado"]].iloc[0]
    assert luis["riesgo"] == "Alto" and "sin usuario" in M.motivo_riesgo(luis)
    assert any("no tienen usuario en el SIS" in a for a in M.alertas_equipo(df))
