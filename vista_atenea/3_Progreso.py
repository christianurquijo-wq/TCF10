"""Progreso: horas completadas frente a la meta de 63 h y avance en los cursos de la plataforma."""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from tcf10 import config as C
from tcf10 import ui
from vista_atenea import comun, estilo

estilo.pagina("Progreso", f"Horas completadas frente a la meta de {ui.num(C.HORAS_CULMINACION)} h y avance en los cursos")
df = comun.filtrado(comun.todos())
comun.nota_filtros()
form = df[df["estado_atenea"].isin(C.EN_CURSO + [C.APROBADO, C.NO_APROBADO])]
if form.empty:
    st.info("No hay participantes en formación para este filtro.")
    st.stop()

c = estilo.fila(4, "prog")
with c[0]:
    estilo.kpi("Horas completadas promedio", ui.num(form["horas_validas"].mean(), 1),
               f"de {ui.num(C.HORAS_CULMINACION)} h para aprobar (70 %)", "azul")
with c[1]:
    estilo.kpi(f"{C.ETQ_SINC} promedio", ui.num(form["horas_sinc_val"].mean(), 1),
               f"tope {ui.num(C.HORAS_SINCRONICAS, 1)} h · 35 % (clases con docente)", "noche")
with c[2]:
    estilo.kpi(f"{C.ETQ_ASINC} promedio", ui.num(form["horas_asinc_val"].mean(), 1),
               f"tope {ui.num(C.HORAS_ASINCRONICAS, 1)} h · 65 % (plataforma)", "noche")
with c[3]:
    estilo.kpi("Avance hacia la aprobación", ui.pct(min(1, form["horas_validas"].mean() / C.HORAS_CULMINACION)),
               "promedio de horas completadas ÷ 63 h", "naranja")

st.write("")
estilo.seccion("Distribución de horas completadas")
fig = go.Figure(go.Histogram(x=form["horas_validas"], xbins=dict(start=0, end=90, size=3), marker_color=ui.AZUL))
fig.add_vline(x=C.HORAS_CULMINACION, line_dash="dash", line_color=ui.NARANJA,
              annotation_text=f"Meta {ui.num(C.HORAS_CULMINACION)} h")
fig.update_layout(xaxis_title="Horas completadas", yaxis_title="Participantes", bargap=.05)
ui.grafica_atenea(fig, 320)

_, prog = comun.agregados_asistencia(df)
izq, der = st.columns(2)
with izq:
    st.subheader("Horas promedio por grupo")
    g = form.groupby("grupo", as_index=False)[["horas_sinc_val", "horas_asinc_val"]].mean().sort_values("grupo")
    g = g.melt(id_vars="grupo", var_name="tipo", value_name="horas")
    g["tipo"] = g["tipo"].map({"horas_sinc_val": C.ETQ_SINC, "horas_asinc_val": C.ETQ_ASINC})
    fig = px.bar(g, x="horas", y="grupo", color="tipo", orientation="h",
                 color_discrete_map={C.ETQ_SINC: ui.NOCHE, C.ETQ_ASINC: ui.CELESTE},
                 labels={"horas": "Horas promedio", "grupo": "", "tipo": ""})
    fig.update_layout(barmode="stack", legend=dict(orientation="h", y=1.08))
    ui.grafica_atenea(fig, max(320, 22 * form["grupo"].nunique()))
with der:
    st.subheader("Avance en los cursos")
    if prog.empty:
        st.info("Sin avance registrado en la plataforma para este filtro.")
    else:
        cur = prog.assign(curso=prog["curso"].map(ui.curso_corto)).groupby("curso", as_index=False)[
            ["completado", "en_progreso", "sin_iniciar"]].sum()
        cur = cur.melt(id_vars="curso", var_name="estado", value_name="inscripciones")
        cur["estado"] = cur["estado"].map({"completado": "Completado", "en_progreso": "En progreso",
                                           "sin_iniciar": "Sin iniciar"})
        fig = px.bar(cur, y="curso", x="inscripciones", color="estado", orientation="h",
                     category_orders={"estado": ["Completado", "En progreso", "Sin iniciar"]},
                     color_discrete_map={"Completado": ui.NOCHE, "En progreso": ui.AZUL, "Sin iniciar": ui.CELESTE},
                     labels={"curso": "", "estado": ""})
        fig.update_layout(barmode="stack", barnorm="percent", xaxis=dict(title="% de inscripciones", ticksuffix=" %"),
                          legend=dict(orientation="h", y=1.08))
        ui.grafica_atenea(fig, 60 + 50 * cur["curso"].nunique())
