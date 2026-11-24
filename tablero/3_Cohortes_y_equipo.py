"""Seguimiento por cohorte, grupo y docente, y control de las condiciones del equipo formativo."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tcf10 import config as C
from tcf10 import metrics as M
from tcf10 import ui

ui.inicio("Cohortes y equipo", f"Grupos de hasta {C.MAX_ACTIVOS_POR_GRUPO} activos, máximo "
          f"{C.MAX_GRUPOS_POR_DOCENTE} grupos simultáneos por docente, {C.MIN_GESTORES_POR_DOCENTE} gestor por "
          f"docente y al menos {C.MIN_FRANJAS} franjas horarias")
df = ui.datos()
sel = ui.barra_filtros(df, "eq", ("cohorte", "grupo", "franja", "docente"), documento=False)

# ------------------------------------------------------------------ alertas del equipo (siempre visibles)
alertas = M.alertas_equipo(df)
if alertas:
    gr = M.grupos(df)
    exceden = gr[gr["activos"] > C.MAX_ACTIVOS_POR_GRUPO]
    resumen = []
    if len(exceden):
        resumen.append(f"**{len(exceden)} grupos** superan {C.MAX_ACTIVOS_POR_GRUPO} activos "
                       f"(el mayor tiene {int(exceden['activos'].max())})")
    otras = [a for a in alertas if not a.startswith("Grupo ")]
    if otras:
        resumen.append(f"**{len(otras)} alertas** de docentes, gestores o franjas")
    st.warning(" · ".join(resumen) + ". Detalle en la pestaña «Alertas».", icon=":material/warning:")
else:
    st.success("Grupos, docentes, gestores y franjas dentro de lo que pide el contrato.", icon=":material/check_circle:")

t_grupos, t_doc, t_coh, t_alertas = ui.pestanas(["Grupos", "Docentes", "Cohortes", "Alertas"], "eq")

with t_grupos:
    g = M.grupos(sel).sort_values("activos", ascending=False)
    if g["grupo"].duplicated().any():  # mismo nombre de grupo en dos cohortes: se distinguen en la gráfica
        g["grupo"] = g["grupo"].where(~g["grupo"].duplicated(keep=False), g["grupo"] + " · " + g["cohorte"])
    st.markdown(f"**Activos por grupo** · {ui.num(len(g))} grupos, los más grandes arriba")
    orden = g.iloc[::-1]
    fig = go.Figure(go.Bar(
        y=orden["grupo"], x=orden["activos"], orientation="h", text=orden["activos"], textposition="outside",
        marker_color=[ui.ROJO if e else ui.AZUL for e in orden["excede_maximo"]],
        hovertemplate="%{y}: %{x} activos<extra></extra>", name="Activos"))
    ui.linea_meta(fig, C.MAX_ACTIVOS_POR_GRUPO, f"Máximo {C.MAX_ACTIVOS_POR_GRUPO}", color=ui.NARANJA)
    fig.update_layout(yaxis=dict(title=None, range=ui.rango_categorias(orden["grupo"])), xaxis_title=None,
                      xaxis=dict(range=[0, max(C.MAX_ACTIVOS_POR_GRUPO, int(g["activos"].max() or 0)) * 1.15]))
    ui.grafica(fig, "eq", "grupos", {"y": "grupo"}, ui.alto_barras(len(orden)), alto_max=440)
    st.caption("Rojo: el grupo supera el máximo de activos. Toca un grupo para ver su detalle y su docente.")
    st.dataframe(
        g, hide_index=True, width="stretch", height=min(460, 38 + 35 * len(g)),
        column_config={
            "cohorte": "Cohorte", "grupo": st.column_config.TextColumn("Grupo", pinned=True), "perfil": "Perfil",
            "nivel": "Nivel", "docente": "Docente", "gestor": "Gestor", "franja": "Jornada",
            "integrantes": "Integrantes", "activos": "Activos", "culminados": "Culminaron",
            "horas_promedio": st.column_config.NumberColumn("Horas promedio", format="%.1f"),
            "riesgo_alto": "Riesgo alto",
            "excede_maximo": st.column_config.CheckboxColumn(f"Más de {C.MAX_ACTIVOS_POR_GRUPO} activos"),
        })

with t_doc:
    d = M.docentes(sel)
    st.dataframe(
        d, hide_index=True, width="stretch", height=min(560, 38 + 35 * len(d)),
        column_config={"docente": st.column_config.TextColumn("Docente", pinned=True), "cohorte": "Cohorte",
                       "grupos": "Grupos", "gestores": "Gestores", "franjas": "Jornadas", "activos": "Activos",
                       "alerta": "Alerta"})

with t_coh:
    coh = M.por_cohorte(sel)
    for c in ("pct_enrolados", "desercion", "pct_culminados"):
        coh[c] = coh[c] * 100
    st.dataframe(
        coh[["cohorte", "fecha_inicio", "fecha_fin", "entregados", "enrolados", "pct_enrolados", "retirados",
             "desercion", "culminados", "pct_culminados", "horas_promedio", "riesgo_alto", "riesgo_medio"]],
        hide_index=True, width="stretch",
        column_config={
            "cohorte": st.column_config.TextColumn("Cohorte", pinned=True),
            "fecha_inicio": st.column_config.DateColumn("Inicio", format="DD/MM/YYYY"),
            "fecha_fin": st.column_config.DateColumn("Fin", format="DD/MM/YYYY"),
            "entregados": "Entregados por Atenea", "enrolados": "Enrolados",
            "pct_enrolados": st.column_config.ProgressColumn("% enrolados", format="%.1f %%", min_value=0,
                                                             max_value=100),
            "retirados": "Retirados",
            "desercion": st.column_config.NumberColumn("Deserción", format="%.1f %%"),
            "culminados": "Culminaron",
            "pct_culminados": st.column_config.NumberColumn("% culminación", format="%.1f %%"),
            "horas_promedio": st.column_config.NumberColumn("Horas válidas promedio", format="%.1f"),
            "riesgo_alto": "Riesgo alto", "riesgo_medio": "Riesgo medio",
        })
    st.caption("Deserción = retirados ÷ enrolados. La matriz de riesgos del contrato marca como crítico superar "
               "el 30 %.")

with t_alertas:
    if alertas:
        st.dataframe(pd.DataFrame({"Alerta": alertas}), hide_index=True, width="stretch",
                     height=min(560, 38 + 35 * len(alertas)))
    else:
        st.success("Sin alertas.", icon=":material/check_circle:")
