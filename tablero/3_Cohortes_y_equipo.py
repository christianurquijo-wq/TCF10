"""Seguimiento por cohorte, grupo y docente, y control de las condiciones del equipo formativo."""
import pandas as pd
import plotly.express as px
import streamlit as st

from tcf10 import config as C
from tcf10 import metrics as M
from tcf10 import ui

ui.inicio("Cohortes y equipo", f"Grupos de hasta {C.MAX_ACTIVOS_POR_GRUPO} activos, máximo "
          f"{C.MAX_GRUPOS_POR_DOCENTE} grupos simultáneos por docente, {C.MIN_GESTORES_POR_DOCENTE} gestor por "
          f"docente y al menos {C.MIN_FRANJAS} franjas horarias")
df = ui.datos()

# ------------------------------------------------------------------ cohortes
st.subheader("Cohortes")
coh = M.por_cohorte(df)
for c in ("pct_enrolados", "desercion", "pct_culminados"):
    coh[c] = coh[c] * 100
st.dataframe(
    coh[["cohorte", "fecha_inicio", "fecha_fin", "entregados", "enrolados", "pct_enrolados", "retirados",
         "desercion", "culminados", "pct_culminados", "horas_promedio", "riesgo_alto", "riesgo_medio"]],
    hide_index=True, width="stretch",
    column_config={
        "cohorte": "Cohorte",
        "fecha_inicio": st.column_config.DateColumn("Inicio", format="DD/MM/YYYY"),
        "fecha_fin": st.column_config.DateColumn("Fin", format="DD/MM/YYYY"),
        "entregados": "Entregados por Atenea", "enrolados": "Enrolados",
        "pct_enrolados": st.column_config.ProgressColumn("% enrolados", format="%.1f %%", min_value=0, max_value=100),
        "retirados": "Retirados",
        "desercion": st.column_config.NumberColumn("Deserción", format="%.1f %%"),
        "culminados": "Culminaron",
        "pct_culminados": st.column_config.NumberColumn("% culminación", format="%.1f %%"),
        "horas_promedio": st.column_config.NumberColumn("Horas válidas promedio", format="%.1f"),
        "riesgo_alto": "Riesgo alto", "riesgo_medio": "Riesgo medio",
    })
st.caption("Deserción = retirados ÷ enrolados. La matriz de riesgos del contrato marca como crítico superar el 30 %.")

# ------------------------------------------------------------------ alertas del equipo
st.subheader("Alertas del equipo formativo")
alertas = M.alertas_equipo(df)
if alertas:
    # Una línea por alerta se volvía una lista eterna: resumen + detalle plegable.
    gr = M.grupos(df)
    exceden = gr[gr["activos"] > C.MAX_ACTIVOS_POR_GRUPO]  # no depende del nombre de columna de metrics.py
    otras = [a for a in alertas if not a.startswith("Grupo ")]
    if len(exceden):
        st.warning(f"**{len(exceden)} grupos superan el máximo de {C.MAX_ACTIVOS_POR_GRUPO} activos** "
                   f"(el mayor tiene {int(exceden['activos'].max())}).", icon=":material/groups:")
    for a in otras[:5]:
        st.warning(a, icon=":material/warning:")
    with st.expander(f"Ver las {len(alertas)} alertas"):
        st.dataframe(pd.DataFrame({"Alerta": alertas}), hide_index=True, width="stretch")
else:
    st.success("Grupos, docentes, gestores y franjas dentro de lo que pide el contrato.", icon=":material/check_circle:")

# ------------------------------------------------------------------ grupos
st.subheader("Grupos")
sel = ui.filtros(df, "eq", ("cohorte", "perfil", "nivel"))
g = M.grupos(sel)
top = g.sort_values("activos", ascending=False).head(25)
fig = px.bar(top, x="grupo", y="activos", color="excede_maximo", text="activos",
             color_discrete_map={False: ui.AZUL, True: ui.ROJO},
             labels={"activos": "Activos", "grupo": "", "excede_maximo": f"Más de {C.MAX_ACTIVOS_POR_GRUPO}"})
fig.add_hline(y=C.MAX_ACTIVOS_POR_GRUPO, line_dash="dash", line_color=ui.NARANJA,
              annotation_text=f"Máximo {C.MAX_ACTIVOS_POR_GRUPO}")
fig.update_layout(showlegend=False, xaxis_tickangle=-60)
st.plotly_chart(ui.dark_layout(fig, 340), width="stretch")
st.caption(f"Los 25 grupos con más activos de {len(g)} grupos. La tabla completa está abajo.")
st.dataframe(
    g, hide_index=True, width="stretch",
    column_config={
        "cohorte": "Cohorte", "grupo": "Grupo", "perfil": "Perfil", "nivel": "Nivel", "docente": "Docente",
        "gestor": "Gestor", "franja": "Franja", "integrantes": "Integrantes", "activos": "Activos",
        "culminados": "Culminaron", "horas_promedio": st.column_config.NumberColumn("Horas promedio", format="%.1f"),
        "riesgo_alto": "Riesgo alto", "excede_maximo": st.column_config.CheckboxColumn(f"Más de {C.MAX_ACTIVOS_POR_GRUPO} activos"),
    })

# ------------------------------------------------------------------ docentes
st.subheader("Carga por docente")
d = M.docentes(sel)
st.dataframe(
    d, hide_index=True, width="stretch",
    column_config={"docente": "Docente", "cohorte": "Cohorte", "grupos": "Grupos", "gestores": "Gestores",
                   "franjas": "Franjas", "activos": "Activos", "alerta": "Alerta"})
