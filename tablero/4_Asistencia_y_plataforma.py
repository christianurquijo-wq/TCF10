"""Asistencia a sesiones sincrónicas y avance en plataforma, directo de las vistas VTD10 del SIS."""
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from tcf10 import config as C
from tcf10 import data
from tcf10 import ui

ui.inicio("Asistencia y plataforma", "Lo que registra el SIS: asistencia por sesión, registro de asistencia por "
          "parte de los docentes y avance por curso")
df = ui.datos()
base = ui.barra_filtros(df, "ap", ("cohorte", "grupo", "franja", "docente"))
ids = tuple(sorted(int(x) for x in base["id_sis"].dropna().unique()))
if not ids:
    st.info("No hay beneficiarios con esos filtros.")
    st.stop()

asis, prog = data.agregados(tuple(sorted(int(x) for x in df["id_sis"].dropna().unique())))
grupos_sel = set(base["grupo"])
asis = asis[asis["grupo"].isin(grupos_sel)].copy()
# Los docentes registran la asistencia después de la clase: lo de las últimas 24 h es «por registrar», no «sin registro».
limite = pd.Timestamp(datetime.now(ui.TZ).replace(tzinfo=None)) - pd.Timedelta(hours=C.REGISTRO_GRACIA_HORAS)
reciente = asis["fecha"] >= limite.normalize()
por_registrar = int(asis.loc[reciente, "sin_registro"].sum())
asis.loc[reciente, "sin_registro"] = 0
prog = prog[prog["grupo"].isin(grupos_sel)]
prog = prog.assign(curso=prog["curso"].map(ui.curso_corto))

# Etiqueta del día/semana de cada sesión: es lo que devuelve el clic en la gráfica de tendencia.
diaria = asis["fecha"].dt.normalize().nunique() <= 28  # el primer mes se lee mejor por día
asis["semana"] = asis["fecha"].dt.normalize() if diaria else asis["fecha"].dt.to_period("W-SUN").dt.start_time
_fmt = ui.etiqueta_dia if diaria else (lambda d: f"Sem. {d:%d/%m}")
_etq = {d: _fmt(d) for d in asis["semana"].dropna().unique()}
asis["periodo"] = [_etq.get(d, "") if pd.notna(d) else "" for d in asis["semana"]]

# Filtros por clic: grupo (barras de grupos), periodo (tendencia) y curso (avance por curso).
# La tendencia y la gráfica de cursos no se filtran por su propio clic, para seguir viendo el contexto.
asis_tend = ui.aplicar_clic(asis.rename(columns={"periodo": "_periodo"}), "ap")
prog_cur = ui.aplicar_clic(prog.rename(columns={"curso": "_curso"}), "ap").rename(columns={"_curso": "curso"})
asis = ui.aplicar_clic(asis, "ap")
prog = ui.aplicar_clic(prog, "ap")

# ------------------------------------------------------------------ KPIs
asistieron, no_asist, sin_reg = (int(asis[c].sum()) for c in ("asistieron", "no_asistieron", "sin_registro"))
registradas = asistieron + no_asist
esperadas = registradas + sin_reg
c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.tarjeta("Asistencia", ui.pct(asistieron / registradas if registradas else None),
               f"{ui.num(asistieron)} asistencias de {ui.num(registradas)} registradas", ui.AZUL)
with c2:
    cobertura = registradas / esperadas if esperadas else None
    ui.tarjeta("Asistencia registrada", ui.pct(cobertura),
               f"{ui.num(sin_reg)} cupos de sesión sin registro del docente"
               + (f" · {ui.num(por_registrar)} de las últimas 24 h por registrar" if por_registrar else ""),
               ui.VERDE if (cobertura or 0) >= .95 else ui.AMARILLO if (cobertura or 0) >= .8 else ui.ROJO)
with c3:
    ui.tarjeta("Sesiones dictadas", ui.num(asis["session_id"].nunique()),
               f"en {ui.num(asis['grupo'].nunique())} grupos", ui.AZUL)
with c4:
    tot = prog["estudiantes"].sum()
    ui.tarjeta("Cursos completados", ui.pct(prog["completado"].sum() / tot if tot else None),
               f"{ui.num(prog['sin_iniciar'].sum())} inscripciones a curso sin iniciar", ui.NARANJA)

if asis.empty and prog.empty:
    st.info("El SIS todavía no tiene sesiones ni avance para estos beneficiarios.")
    st.stop()

# ------------------------------------------------------------------ datos de las gráficas
sem = asis_tend.dropna(subset=["semana"])
sem = sem.groupby("semana", as_index=False)[["asistieron", "no_asistieron", "sin_registro"]].sum()
# Solo los días/semanas con asistencia registrada: sin huecos vacíos en el eje (eje por categoría).
sem = sem[(sem["asistieron"] + sem["no_asistieron"]) > 0].sort_values("semana")
sem["asistencia"] = sem["asistieron"] / (sem["asistieron"] + sem["no_asistieron"])
sem["etiqueta"] = [_etq.get(d, "") for d in sem["semana"]]

por_grupo = asis.groupby("grupo", as_index=False)[["asistieron", "no_asistieron", "sin_registro"]].sum()
por_grupo["registradas"] = por_grupo["asistieron"] + por_grupo["no_asistieron"]
por_grupo["asistencia"] = por_grupo["asistieron"] / por_grupo["registradas"].where(lambda s: s > 0)
por_grupo["cobertura"] = por_grupo["registradas"] / (por_grupo["registradas"] + por_grupo["sin_registro"]).where(
    lambda s: s > 0)

t_tend, t_grupos, t_cursos, t_tabla = ui.pestanas(["Tendencia", "Por grupo", "Plataforma por curso", "Tabla"], "ap")

with t_tend:
    st.markdown(f"**{'Asistencia por día' if diaria else 'Asistencia por semana'}** · porcentaje sobre la asistencia "
                "registrada; una caída sostenida anticipa deserción")
    fig = go.Figure()
    fig.add_bar(x=sem["etiqueta"], y=sem["asistieron"], name="Asistieron", marker_color=ui.AZUL, yaxis="y2",
                opacity=.35, hovertemplate="%{x}: %{y} asistencias<extra></extra>")
    fig.add_scatter(x=sem["etiqueta"], y=sem["asistencia"], name="% asistencia", mode="lines+markers",
                    line=dict(color=ui.NARANJA, width=3), marker=dict(size=8),
                    hovertemplate="%{x}: %{y:.0%}<extra></extra>")
    fig.update_layout(xaxis=dict(type="category", tickangle=-45 if len(sem) > 12 else 0),
                      yaxis=dict(title=None, tickformat=".0%", range=[0, 1.05]),
                      yaxis2=dict(title=None, overlaying="y", side="right", showgrid=False), xaxis_title=None,
                      separators=",.")
    ui.grafica(fig, "ap", "tendencia", {"x": "periodo"}, 380)
    st.caption("Toca un día o una semana para ver solo esas sesiones.")

with t_grupos:
    izq, der = st.columns(2, gap="large")
    with izq:
        g = por_grupo.dropna(subset=["asistencia"]).sort_values("asistencia")
        st.markdown(f"**Asistencia por grupo** · {ui.num(len(g))} grupos, la más baja arriba")
        orden = g.iloc[::-1]
        fig = go.Figure(go.Bar(
            x=orden["asistencia"], y=orden["grupo"], orientation="h", text=[ui.pct(v) for v in orden["asistencia"]],
            textposition="outside", name="Asistencia",
            marker_color=[ui.ROJO if v < .6 else ui.NARANJA if v < .8 else ui.VERDE for v in orden["asistencia"]],
            hovertemplate="%{y}: %{x:.0%}<extra></extra>"))
        fig.update_layout(xaxis=dict(tickformat=".0%", range=[0, 1.15], title=None),
                          yaxis=dict(title=None, range=ui.rango_categorias(orden["grupo"])))
        ui.grafica(fig, "ap", "menor", {"y": "grupo"}, ui.alto_barras(len(orden)), alto_max=460)
    with der:
        g = por_grupo[por_grupo["sin_registro"] > 0].sort_values("sin_registro", ascending=False)
        st.markdown(f"**Asistencia sin registrar** · {ui.num(len(g))} grupos")
        if g.empty:
            st.success("Todos los docentes registraron la asistencia de las sesiones dictadas.",
                       icon=":material/check_circle:")
        else:
            orden = g.iloc[::-1]
            fig = go.Figure(go.Bar(x=orden["sin_registro"], y=orden["grupo"], orientation="h",
                                   text=orden["sin_registro"], textposition="outside", marker_color=ui.AMARILLO,
                                   name="Sin registro", hovertemplate="%{y}: %{x} cupos sin registro<extra></extra>"))
            fig.update_layout(xaxis_title=None, yaxis=dict(title=None, range=ui.rango_categorias(orden["grupo"])),
                              xaxis=dict(range=[0, orden["sin_registro"].max() * 1.2]))
            ui.grafica(fig, "ap", "sinreg", {"y": "grupo"}, ui.alto_barras(len(orden)), alto_max=460)
            st.caption("Cupos de sesión sin registro del docente: esas horas no cuentan para la culminación (63 h).")

with t_cursos:
    cur = prog_cur.groupby("curso", as_index=False)[["completado", "en_progreso", "sin_iniciar"]].sum()
    cur = cur.melt(id_vars="curso", var_name="estado", value_name="inscripciones")
    cur["estado"] = cur["estado"].map({"completado": "Completado", "en_progreso": "En progreso",
                                       "sin_iniciar": "Sin iniciar"})
    fig = px.bar(cur, y="curso", x="inscripciones", color="estado", orientation="h", text="inscripciones",
                 category_orders={"estado": ["Completado", "En progreso", "Sin iniciar"]},
                 color_discrete_map={"Completado": ui.VERDE, "En progreso": ui.AZUL, "Sin iniciar": "#BDBDBD"})
    fig.update_traces(texttemplate="%{text:,.0f}", textposition="inside")
    fig.update_layout(barmode="stack", barnorm="percent", xaxis=dict(title=None, ticksuffix=" %"),
                      yaxis_title=None, separators=",.")
    ui.grafica(fig, "ap", "cursos", {"y": "curso"}, 80 + 44 * cur["curso"].nunique())
    st.caption("Porcentaje de inscripciones a cada curso según su estado. Toca un curso para filtrar.")

with t_tabla:
    tabla = por_grupo.merge(
        prog.groupby("grupo", as_index=False).agg(avance_plataforma=("avance_promedio", "mean")), on="grupo",
        how="outer")
    if "periodo" in st.session_state.get("xf_ap", {}):  # filtro por fecha: solo los grupos con sesión ese día/semana
        tabla = tabla[tabla["grupo"].isin(asis["grupo"])]
    for c in ("asistencia", "cobertura", "avance_plataforma"):
        tabla[c] = tabla[c] * 100
    st.dataframe(
        tabla[["grupo", "asistieron", "no_asistieron", "sin_registro", "asistencia", "cobertura", "avance_plataforma"]]
        .sort_values("asistencia"),
        hide_index=True, width="stretch", height=min(560, 38 + 35 * len(tabla)),
        column_config={
            "grupo": st.column_config.TextColumn("Grupo", pinned=True), "asistieron": "Asistencias",
            "no_asistieron": "Inasistencias", "sin_registro": "Sin registro",
            "asistencia": st.column_config.ProgressColumn("% asistencia", format="%.1f %%", min_value=0,
                                                          max_value=100),
            "cobertura": st.column_config.NumberColumn("% registrado", format="%.1f %%"),
            "avance_plataforma": st.column_config.NumberColumn("Avance promedio en plataforma", format="%.1f %%"),
        })
