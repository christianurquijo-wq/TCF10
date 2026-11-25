"""Vista interna · seguimiento de Feedbacks (componentes «Feedback 1» … «Feedback 8» de la plataforma).

Meta: un Feedback por clase dictada al grupo (clases de días anteriores; la de hoy todavía no se exige), hasta 8.
Un Feedback cuenta como hecho si is_completed = TRUE en VTD10_student_progress_detail (metrics.feedback).
Quien lleva C.FEEDBACK_ATRASO_CRITICO o más pendientes con el grupo en curso pasa a «caso crítico».
"""
import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tcf10 import config as C
from tcf10 import data, ui
from vista_atenea import comun

TOT = C.FEEDBACKS_TOTAL
COLOR_EST = {"3 o más pendientes": ui.ROJO, "2 pendientes": ui.NARANJA, "1 pendiente": "#F5A54A",
             "Al día": ui.VERDE, "Aún no aplica": ui.CELESTE}
CORTO = {"3 o más pendientes": "3+ pend.", "2 pendientes": "2 pend.", "1 pendiente": "1 pend.", "Al día": "Al día",
         "Aún no aplica": "No aplica"}

ui.inicio("Seguimiento de Feedbacks", f"Un Feedback por clase dictada (hasta {TOT}), los más atrasados primero")
df = ui.datos()
hoy = comun.hoy()
if "feedbacks_meta" not in df:
    st.warning("No se pudieron calcular los Feedbacks. " + df.attrs.get("feedback_error", "Pulsa «Actualizar»."),
               icon=":material/warning:")
    st.stop()
if not data.modo_demo() and data.fuente_sis() != "bq":
    st.info("Los Feedbacks se leen directo de BigQuery (`sis_dataset` en los Secrets). Con la fuente actual no hay "
            "datos de Feedbacks.", icon=":material/database:")
    st.stop()

base = ui.barra_filtros(df[df["feedbacks_meta"].notna()], "fb")
if base.empty:
    st.info("Nadie cumple esos filtros.", icon=":material/filter_alt_off:")
    st.stop()

exig = base[base["feedbacks_meta"] > 0]
metas = sorted(exig["feedbacks_meta"].dropna().astype(int).unique())
meta_unica = metas[0] if len(metas) == 1 else None
esperado = exig["feedbacks_meta"].sum()
cumplido = exig[["feedbacks_hechos", "feedbacks_meta"]].min(axis=1).sum()

# ------------------------------------------------------------------ indicadores
c = st.columns(4)
with c[0]:
    ui.tarjeta("Meta a hoy", f"{meta_unica} de {TOT}" if meta_unica is not None
               else (f"{metas[0]}–{metas[-1]}" if metas else "0"),
               "uno por clase dictada" if meta_unica is not None else "según las clases de cada grupo", ui.AZUL)
with c[1]:
    ui.tarjeta("Promedio completado", ui.num(exig["feedbacks_hechos"].mean() if len(exig) else 0, 1),
               f"de {ui.num(exig['feedbacks_meta'].mean() if len(exig) else 0, 1)} esperados · "
               f"{ui.pct(cumplido / esperado if esperado else None)} de cumplimiento", ui.AZUL_PROFUNDO)
with c[2]:
    al_dia = int(exig["feedbacks_atraso"].eq(0).sum())
    ui.tarjeta("Al día", ui.num(al_dia), f"{ui.pct(al_dia / len(exig) if len(exig) else None)} de "
               f"{ui.num(len(exig))} estudiantes", ui.VERDE)
with c[3]:
    atr = int((exig["feedbacks_atraso"] >= C.FEEDBACK_ATRASO_CRITICO).sum())
    ui.tarjeta(f"{C.FEEDBACK_ATRASO_CRITICO} o más pendientes", ui.num(atr), "casos críticos si el grupo sigue en curso",
               ui.ROJO)

# ------------------------------------------------------------------ por grupo (se usa en varias pestañas)
grupos = (base.groupby("grupo")
          .agg(jornada=("franja", "first"), docente=("docente", "first"), estudiantes=("id_sis", "size"),
               meta=("feedbacks_meta", "max"), promedio=("feedbacks_hechos", "mean"),
               al_dia=("feedbacks_atraso", lambda s: (s == 0).mean()),
               atrasados=("feedbacks_atraso", lambda s: int((s >= C.FEEDBACK_ATRASO_CRITICO).sum())),
               pendientes=("feedbacks_atraso", "sum"))
          .reset_index())
grupos["brecha"] = grupos["promedio"] - grupos["meta"]
grupos["cumplimiento"] = grupos["promedio"] / grupos["meta"].where(grupos["meta"] > 0)
grupos = grupos.sort_values(["brecha", "atrasados"], ascending=[True, False])

t_graf, t_grupos, t_est = ui.pestanas(["Gráficas", "Por grupo", "Estudiantes"], "fb")

with t_graf:
    st.markdown(f"**Promedio por grupo frente a su meta** · {ui.num(len(grupos))} grupos, los más atrasados arriba")
    orden = grupos.iloc[::-1]  # Plotly dibuja de abajo hacia arriba
    color = [ui.GRIS if pd.isna(r) else ui.ROJO if r < .6 else ui.NARANJA if r < .9 else ui.VERDE
             for r in orden["cumplimiento"]]
    fig = go.Figure()
    fig.add_bar(y=orden["grupo"], x=orden["promedio"], orientation="h", name="Promedio completado",
                marker_color=color, text=[f"{v:.1f}".replace(".", ",") for v in orden["promedio"]],
                textposition="outside", customdata=orden[["meta", "estudiantes"]],
                hovertemplate="<b>%{y}</b><br>Promedio: %{x:.1f}<br>Meta: %{customdata[0]:.0f}"
                              "<br>Estudiantes: %{customdata[1]}<extra></extra>")
    if meta_unica is not None:
        ui.linea_meta(fig, meta_unica, f"Meta a hoy: {meta_unica}")
    else:
        fig.add_scatter(y=orden["grupo"], x=orden["meta"], mode="markers", name="Meta del grupo",
                        marker=dict(symbol="line-ns-open", size=16, color=ui.NOCHE, line=dict(width=3, color=ui.NOCHE)),
                        hovertemplate="%{y}: meta %{x:.0f}<extra></extra>")
    fig.update_layout(xaxis=dict(title=None, range=[0, TOT + .8], dtick=1),
                      yaxis=dict(title=None, range=ui.rango_categorias(orden["grupo"])), separators=",.", bargap=.25)
    ui.grafica(fig, "fb", "grupos", {"y": "grupo"}, ui.alto_barras(len(orden)), alto_max=480, leyenda=False)
    st.caption("Barra: promedio de Feedbacks completados · línea negra: meta a hoy · verde ≥ 90 % de la meta, "
               "naranja 60–89 %, rojo < 60 %. Desliza dentro del recuadro para ver todos los grupos.")

    izq, der = st.columns(2, gap="large")
    with izq:
        st.markdown("**Estudiantes según Feedbacks completados**")
        dist = exig.groupby(["feedbacks_hechos", "estado_feedback"]).size().rename("n").reset_index()
        fig = go.Figure()
        for est in C.ESTADOS_FEEDBACK:
            d = dist[dist["estado_feedback"].eq(est)]
            if len(d):
                fig.add_bar(x=d["feedbacks_hechos"], y=d["n"], name=CORTO[est], marker_color=COLOR_EST[est],
                            hovertemplate=f"{est}<br>%{{x}} Feedbacks: %{{y}} estudiantes<extra></extra>")
        linea = meta_unica if meta_unica is not None else (exig["feedbacks_meta"].mean() if len(exig) else None)
        if linea is not None:
            ui.linea_meta(fig, linea, f"Meta {meta_unica}" if meta_unica is not None
                          else "Meta prom. " + f"{linea:.1f}".replace(".", ","))
        fig.update_layout(barmode="stack", xaxis=dict(title="Feedbacks completados", dtick=1, range=[-.6, TOT + .6]),
                          yaxis_title="Estudiantes", separators=",.")
        ui.grafica(fig, "fb", "dist", {"x": "feedbacks_hechos"}, 380)
    with der:
        st.markdown("**Cumplimiento de cada Feedback**")
        filas = []
        for n in range(1, TOT + 1):
            e = exig[exig["feedbacks_meta"] >= n]
            if len(e):
                filas.append({"feedback": f"Feedback {n}", "n": n, "exigibles": len(e),
                              "hechos": int(e[f"fb_{n}"].sum())})
        cf = pd.DataFrame(filas)
        if cf.empty:
            st.info("Todavía no hay Feedbacks exigibles.")
        else:
            cf["pct"] = cf["hechos"] / cf["exigibles"]
            fig = go.Figure(go.Bar(
                x=[f"F{n}" for n in cf["n"]], y=cf["pct"], name="Lo hicieron", showlegend=False,
                marker_color=[ui.ROJO if p < .6 else ui.NARANJA if p < .9 else ui.VERDE for p in cf["pct"]],
                text=[ui.pct(p) for p in cf["pct"]], textposition="outside",
                customdata=cf[["feedback", "hechos", "exigibles"]],
                hovertemplate="%{customdata[0]}: %{y:.0%}<br>%{customdata[1]} de %{customdata[2]}<extra></extra>"))
            ui.linea_meta(fig, 1, "Meta: 100 %", eje="y")
            fig.update_layout(yaxis=dict(tickformat=".0%", range=[0, 1.18], title=None), xaxis_title=None)
            ui.mostrar(fig, 380, leyenda=False)
            st.caption("Sobre quienes ya debían hacerlo (su grupo ya tuvo esa clase).")

with t_grupos:
    vista = grupos.assign(al_dia=grupos["al_dia"] * 100, cumplimiento=grupos["cumplimiento"] * 100)
    st.dataframe(
        vista[["grupo", "jornada", "docente", "estudiantes", "meta", "promedio", "brecha", "cumplimiento", "al_dia",
               "atrasados", "pendientes"]],
        hide_index=True, width="stretch", height=min(560, 38 + 35 * len(vista)), column_config={
            "grupo": st.column_config.TextColumn("Grupo", pinned=True), "jornada": "Jornada", "docente": "Docente",
            "estudiantes": "Estudiantes", "meta": st.column_config.NumberColumn("Meta a hoy", format="%d"),
            "promedio": st.column_config.NumberColumn("Promedio hecho", format="%.1f"),
            "brecha": st.column_config.NumberColumn("Diferencia vs. meta", format="%.1f"),
            "cumplimiento": st.column_config.ProgressColumn("Cumplimiento", format="%.0f %%", min_value=0,
                                                            max_value=100),
            "al_dia": st.column_config.ProgressColumn("% al día", format="%.0f %%", min_value=0, max_value=100),
            "atrasados": st.column_config.NumberColumn(f"Con {C.FEEDBACK_ATRASO_CRITICO}+ pendientes", format="%d"),
            "pendientes": st.column_config.NumberColumn("Feedbacks pendientes", format="%d"),
        })

with t_est:
    if ui.sensible_activo():
        ui.aviso_sensible()
    else:
        e1, e2 = st.columns([2, 1], vertical_alignment="bottom")
        estados = e1.pills("Estado", C.ESTADOS_FEEDBACK, selection_mode="multi", key="fb_estados")
        solo = e2.toggle("Solo con pendientes", value=False, key="fb_solo")
        est = comun.con_identidad(base)
        if estados:
            est = est[est["estado_feedback"].isin(estados)]
        if solo:
            est = est[est["feedbacks_atraso"] > 0]
        est = est.sort_values(["feedbacks_atraso", "feedbacks_hechos", "grupo"], ascending=[False, True, True])
        for n in range(1, TOT + 1):  # ✓ hecho · ✗ pendiente (ya le tocaba) · – aún no le toca
            est[f"F{n}"] = ["✓" if h else ("✗" if n <= m else "–")
                            for h, m in zip(est[f"fb_{n}"], est["feedbacks_meta"].fillna(0))]
        est["nombre_completo"] = est["nombre_completo"].fillna(est["nombre"] if "nombre" in est else "")
        cols = ["nombre_completo", "documento", "grupo", "franja", "feedbacks_meta", "feedbacks_hechos",
                "feedbacks_atraso", "estado_feedback"] + [f"F{n}" for n in range(1, TOT + 1)]
        tabla = est[cols]
        st.caption(f"{ui.num(len(tabla))} estudiantes · ✓ hecho · ✗ pendiente · – aún no le toca")
        cfg = {"nombre_completo": st.column_config.TextColumn("Estudiante", pinned=True), "documento": "Documento",
               "grupo": "Grupo", "franja": "Jornada", "feedbacks_meta": st.column_config.NumberColumn("Meta", format="%d"),
               "feedbacks_hechos": st.column_config.NumberColumn("Hechos", format="%d"),
               "feedbacks_atraso": st.column_config.NumberColumn("Pendientes", format="%d"), "estado_feedback": "Estado"}
        cfg.update({f"F{n}": st.column_config.TextColumn(f"F{n}", width="small") for n in range(1, TOT + 1)})
        st.dataframe(tabla, hide_index=True, width="stretch", height=min(600, 38 + 35 * max(1, len(tabla))),
                     column_config=cfg)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as xw:
            tabla.rename(columns={"nombre_completo": "Estudiante", "documento": "Documento", "grupo": "Grupo",
                                  "franja": "Jornada", "feedbacks_meta": "Meta", "feedbacks_hechos": "Hechos",
                                  "feedbacks_atraso": "Pendientes", "estado_feedback": "Estado"}
                         ).to_excel(xw, sheet_name="Estudiantes", index=False)
            grupos.to_excel(xw, sheet_name="Grupos", index=False)
        st.download_button("Descargar Excel", buf.getvalue(), f"tcf10_feedbacks_{hoy:%Y%m%d}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           icon=":material/download:")
