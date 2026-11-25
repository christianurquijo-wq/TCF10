"""Asistencia a las sesiones sincrónicas, por día, grupo y franja."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from tcf10 import ui
from vista_atenea import comun, estilo

estilo.pagina("Asistencia", "Asistencia a las sesiones sincrónicas con docente, según el registro en la plataforma")
df = comun.filtrado(comun.todos())
comun.nota_filtros()
asis, _ = comun.agregados_asistencia(df)
if asis.empty:
    st.info("Aún no hay sesiones registradas para este filtro.")
    st.stop()

a, n, s = (int(asis[c].sum()) for c in ("asistieron", "no_asistieron", "sin_registro"))
reg = a + n
c = estilo.fila(4, "asis")
with c[0]:
    estilo.kpi("Asistencia", ui.pct(a / reg if reg else None), f"{ui.num(a)} asistencias de {ui.num(reg)} registradas",
               "azul")
with c[1]:
    estilo.kpi("Sesiones dictadas", ui.num(asis["session_id"].nunique()), f"en {ui.num(asis['grupo'].nunique())} grupos",
               "noche")
with c[2]:
    estilo.kpi("Participantes convocados", ui.num(int(df["enrolado"].sum())), "formalizados del filtro", "celeste")
with c[3]:
    estilo.kpi("Asistencia registrada", ui.pct(reg / (reg + s) if reg + s else None),
               "de los cupos de sesión ya registrados por el docente", "naranja")

st.write("")
estilo.seccion("Asistencia por día")
d = asis.assign(dia=pd.to_datetime(asis["fecha"]).dt.normalize()).groupby("dia", as_index=False)[
    ["asistieron", "no_asistieron"]].sum()
# Solo los días con asistencia registrada (eje por categoría): los días sin sesiones no quedan como huecos vacíos.
d = d[(d["asistieron"] + d["no_asistieron"]) > 0].sort_values("dia")
d["pct"] = d["asistieron"] / (d["asistieron"] + d["no_asistieron"])
d["etiqueta"] = d["dia"].map(ui.etiqueta_dia)
fig = go.Figure()
fig.add_bar(x=d["etiqueta"], y=d["asistieron"], name="Asistencias", marker_color=ui.CELESTE, yaxis="y2")
fig.add_scatter(x=d["etiqueta"], y=d["pct"], name="% asistencia", mode="lines+markers", line=dict(color=ui.NARANJA, width=3))
fig.update_layout(xaxis=dict(type="category", title=None),
                  yaxis=dict(title="% asistencia", tickformat=".0%", range=[0, 1]),
                  yaxis2=dict(title="Asistencias", overlaying="y", side="right", showgrid=False),
                  legend=dict(orientation="h", y=1.12), separators=",.")
ui.grafica_atenea(fig, 340)

franja_grupo = df.drop_duplicates("grupo").set_index("grupo")["franja"]
g = asis.groupby("grupo", as_index=False)[["asistieron", "no_asistieron", "sin_registro"]].sum()
g["franja"] = g["grupo"].map(franja_grupo).fillna("Sin dato")
g["pct"] = g["asistieron"] / (g["asistieron"] + g["no_asistieron"]).where(lambda x: x > 0)
izq, der = st.columns([1, 1.3])
with izq:
    st.subheader("Por franja")
    f = g.groupby("franja", as_index=False)[["asistieron", "no_asistieron"]].sum()
    f["pct"] = f["asistieron"] / (f["asistieron"] + f["no_asistieron"]).where(lambda x: x > 0)
    fig = px.bar(f.sort_values("pct"), x="pct", y="franja", orientation="h", text="pct",
                 color_discrete_sequence=[ui.AZUL], labels={"pct": "% asistencia", "franja": ""})
    fig.update_traces(texttemplate="%{text:.0%}", textposition="outside")
    fig.update_layout(xaxis=dict(tickformat=".0%", range=[0, 1.1]))
    ui.grafica_atenea(fig, 60 + 45 * len(f))
with der:
    st.subheader("Por grupo")
    g["pct"] = g["pct"] * 100
    st.dataframe(g.sort_values("grupo")[["grupo", "franja", "asistieron", "no_asistieron", "sin_registro", "pct"]],
                 hide_index=True, width="stretch", height=380, column_config={
                     "grupo": "Grupo", "franja": "Franja", "asistieron": "Asistencias", "no_asistieron": "Inasistencias",
                     "sin_registro": "Sin registro",
                     "pct": st.column_config.ProgressColumn("% asistencia", format="%.0f %%", min_value=0,
                                                            max_value=100)})
st.caption("«Sin registro»: sesiones dictadas en las que el docente aún no marcó la asistencia (las de las "
           "últimas 24 horas no se cuentan).")
