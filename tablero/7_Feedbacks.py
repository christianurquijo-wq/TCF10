"""Vista interna · seguimiento de Feedbacks (componentes «Feedback 1» … «Feedback 8» de la plataforma).

Meta: un Feedback por clase dictada al grupo (clases de días anteriores; la de hoy todavía no se exige), hasta 8.
Un Feedback cuenta como hecho si is_completed = TRUE en VTD10_student_progress_detail (metrics.feedback).
Quien lleva C.FEEDBACK_ATRASO_CRITICO o más pendientes con el grupo en curso pasa a «caso crítico».
"""
import io
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tcf10 import config as C
from tcf10 import data, ui
from vista_atenea import comun

TOT = C.FEEDBACKS_TOTAL
COLOR_EST = {"3 o más pendientes": ui.ROJO, "2 pendientes": ui.NARANJA, "1 pendiente": "#F5A54A",
             "Al día": ui.VERDE, "Aún no aplica": ui.CELESTE}

ui.inicio("Seguimiento de Feedbacks",
          f"Un Feedback por clase dictada (hasta {TOT}): quién va al día y quién está atrasado, los más atrasados primero")
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

base = comun.con_identidad(df[df["feedbacks_meta"].notna()].copy())
if base.empty:
    st.info("Aún no hay grupos iniciados.")
    st.stop()

# ------------------------------------------------------------------ filtros
f1, f2, f3, f4 = st.columns([1, 1.3, 1, 1])
for col, c, etiqueta in ((f1, "cohorte", "Cohorte"), (f2, "grupo", "Grupo"), (f3, "franja", "Jornada")):
    opciones = sorted(base[c].dropna().astype(str).unique(), key=C.orden_franja if c == "franja" else None)
    elegido = col.multiselect(etiqueta, opciones, key=f"fb_{c}", placeholder="Todos")
    if elegido:
        base = base[base[c].astype(str).isin(elegido)]
doc = re.sub(r"\D", "", f4.text_input("Documento", key="fb_doc", placeholder="Número de documento"))
if doc:
    base = base[base["documento"].astype(str).str.replace(r"\D", "", regex=True).str.contains(doc, na=False)]
ui.chips_clic("fb")
base = ui.aplicar_clic(base, "fb")
if base.empty:
    st.info("Nadie cumple esos filtros.")
    st.stop()

exig = base[base["feedbacks_meta"] > 0]
metas = sorted(exig["feedbacks_meta"].dropna().astype(int).unique())
meta_unica = metas[0] if len(metas) == 1 else None
esperado = exig["feedbacks_meta"].sum()
cumplido = exig[["feedbacks_hechos", "feedbacks_meta"]].min(axis=1).sum()

# ------------------------------------------------------------------ indicadores
c = st.columns(4)
with c[0]:
    if meta_unica is not None:
        ui.tarjeta("Meta a hoy", f"{meta_unica} de {TOT}", "Feedbacks: uno por clase dictada", ui.AZUL)
    else:
        ui.tarjeta("Meta a hoy", f"{metas[0]}–{metas[-1]}" if metas else "0",
                   "Feedbacks según las clases dictadas a cada grupo", ui.AZUL)
with c[1]:
    ui.tarjeta("Promedio completado", ui.num(exig["feedbacks_hechos"].mean() if len(exig) else 0, 1),
               f"de {ui.num(exig['feedbacks_meta'].mean() if len(exig) else 0, 1)} esperados · "
               f"{ui.pct(cumplido / esperado if esperado else None)} de cumplimiento", ui.AZUL_PROFUNDO)
with c[2]:
    al_dia = int(exig["feedbacks_atraso"].eq(0).sum())
    ui.tarjeta("Al día", ui.num(al_dia), f"{ui.pct(al_dia / len(exig) if len(exig) else None)} de "
               f"{ui.num(len(exig))} estudiantes con Feedbacks exigibles", ui.VERDE)
with c[3]:
    atr = int((exig["feedbacks_atraso"] >= C.FEEDBACK_ATRASO_CRITICO).sum())
    ui.tarjeta(f"Con {C.FEEDBACK_ATRASO_CRITICO} o más pendientes", ui.num(atr),
               "caso crítico si su grupo sigue en curso", ui.ROJO)

# ------------------------------------------------------------------ por grupo
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

st.subheader("Promedio de Feedbacks por grupo frente a la meta")
st.caption("Barra: Feedbacks completados en promedio. Marca negra: meta del grupo a hoy (una por clase dictada). "
           "Los grupos más atrasados van arriba. Clic en un grupo para filtrar la página.")
top = grupos.head(25).iloc[::-1]
color = [ui.GRIS if pd.isna(r) else ui.ROJO if r < .6 else ui.NARANJA if r < .9 else ui.VERDE
         for r in top["cumplimiento"]]
fig = go.Figure()
fig.add_bar(y=top["grupo"], x=top["promedio"], orientation="h", name="Promedio completado", marker_color=color,
            text=[f"{v:.1f}".replace(".", ",") for v in top["promedio"]], textposition="outside",
            hovertemplate="%{y}: %{x:.1f} Feedbacks en promedio<extra></extra>")
fig.add_scatter(y=top["grupo"], x=top["meta"], mode="markers", name="Meta del grupo",
                marker=dict(symbol="line-ns-open", size=22, color=ui.NOCHE, line=dict(width=4, color=ui.NOCHE)),
                hovertemplate="%{y}: meta %{x:.0f}<extra></extra>")
if meta_unica is not None:
    fig.add_vline(x=meta_unica, line_dash="dash", line_color=ui.NOCHE,
                  annotation_text=f"Meta a hoy: {meta_unica}", annotation_position="top")
fig.update_layout(xaxis=dict(title="Feedbacks", range=[0, TOT + .6], dtick=1), yaxis_title=None, separators=",.",
                  legend=dict(orientation="h", y=1.08), bargap=.3)
ui.grafica(fig, "fb", "grupos", {"y": "grupo"}, 80 + 26 * len(top))

izq, der = st.columns(2)
with izq:
    st.subheader("Estudiantes por Feedbacks completados")
    dist = (exig.groupby(["feedbacks_hechos", "estado_feedback"]).size().rename("n").reset_index())
    fig = go.Figure()
    for est in C.ESTADOS_FEEDBACK:
        d = dist[dist["estado_feedback"].eq(est)]
        if len(d):
            fig.add_bar(x=d["feedbacks_hechos"], y=d["n"], name=est, marker_color=COLOR_EST[est])
    linea = meta_unica if meta_unica is not None else (exig["feedbacks_meta"].mean() if len(exig) else None)
    if linea is not None:
        fig.add_vline(x=linea, line_dash="dash", line_color=ui.NOCHE,
                      annotation_text=(f"Meta: {meta_unica}" if meta_unica is not None
                                       else "Meta promedio: " + f"{linea:.1f}".replace(".", ",")),
                      annotation_position="top left")
    fig.update_layout(barmode="stack", xaxis=dict(title="Feedbacks completados", dtick=1, range=[-.6, TOT + .6]),
                      yaxis_title="Estudiantes", separators=",.",
                      legend=dict(orientation="h", y=-.3, x=0))
    ui.grafica(fig, "fb", "dist", {"x": "feedbacks_hechos"}, 400)
with der:
    st.subheader("Cumplimiento de cada Feedback")
    filas = []
    for n in range(1, TOT + 1):
        e = exig[exig["feedbacks_meta"] >= n]
        if len(e):
            filas.append({"feedback": f"Feedback {n}", "n": n, "exigibles": len(e), "hechos": int(e[f"fb_{n}"].sum())})
    cf = pd.DataFrame(filas)
    if cf.empty:
        st.info("Todavía no hay Feedbacks exigibles.")
    else:
        cf["pct"] = cf["hechos"] / cf["exigibles"]
        fig = go.Figure(go.Bar(x=[f"F{n}" for n in cf["n"]], y=cf["pct"], marker_color=[
            ui.ROJO if p < .6 else ui.NARANJA if p < .9 else ui.VERDE for p in cf["pct"]],
            text=[ui.pct(p) for p in cf["pct"]], textposition="outside", textfont=dict(size=13),
            customdata=cf[["feedback", "hechos", "exigibles"]],
            hovertemplate="%{customdata[0]}: %{y:.0%} (%{customdata[1]} de %{customdata[2]})<extra></extra>"))
        fig.add_hline(y=1, line_dash="dash", line_color=ui.NOCHE, annotation_text="Meta: 100 %")
        fig.update_layout(yaxis=dict(tickformat=".0%", range=[0, 1.25], title="Lo hicieron"), xaxis_title=None,
                          xaxis_tickangle=0)
        st.plotly_chart(ui.dark_layout(fig, 400), width="stretch")
        st.caption("Sobre quienes ya debían hacerlo: su grupo ya tuvo esa clase.")

st.subheader("Detalle por grupo")
vista = grupos.assign(al_dia=grupos["al_dia"] * 100, cumplimiento=grupos["cumplimiento"] * 100)
st.dataframe(
    vista[["grupo", "jornada", "docente", "estudiantes", "meta", "promedio", "brecha", "cumplimiento", "al_dia",
           "atrasados", "pendientes"]],
    hide_index=True, width="stretch", height=min(520, 38 + 35 * len(vista)), column_config={
        "grupo": "Grupo", "jornada": "Jornada", "docente": "Docente", "estudiantes": "Estudiantes",
        "meta": st.column_config.NumberColumn("Meta a hoy", format="%d"),
        "promedio": st.column_config.NumberColumn("Promedio hecho", format="%.1f"),
        "brecha": st.column_config.NumberColumn("Diferencia vs. meta", format="%.1f"),
        "cumplimiento": st.column_config.ProgressColumn("Cumplimiento", format="%.0f %%", min_value=0, max_value=100),
        "al_dia": st.column_config.ProgressColumn("% al día", format="%.0f %%", min_value=0, max_value=100),
        "atrasados": st.column_config.NumberColumn(f"Con {C.FEEDBACK_ATRASO_CRITICO}+ pendientes", format="%d"),
        "pendientes": st.column_config.NumberColumn("Feedbacks pendientes", format="%d"),
    })

# ------------------------------------------------------------------ estudiantes
st.subheader("Estudiantes · los más atrasados primero")
e1, e2 = st.columns([1.6, 1])
estados = e1.multiselect("Estado", C.ESTADOS_FEEDBACK, placeholder="Todos", key="fb_estados")
solo = e2.toggle("Solo con pendientes", value=False, key="fb_solo")
est = base.copy()
if estados:
    est = est[est["estado_feedback"].isin(estados)]
if solo:
    est = est[est["feedbacks_atraso"] > 0]
est = est.sort_values(["feedbacks_atraso", "feedbacks_hechos", "grupo"], ascending=[False, True, True])
marca = {True: "✓", False: "✗"}
for n in range(1, TOT + 1):  # ✓ hecho · ✗ pendiente (ya le tocaba) · – aún no le toca
    est[f"F{n}"] = [marca[bool(h)] if (bool(h) or n <= m) else "–"
                    for h, m in zip(est[f"fb_{n}"], est["feedbacks_meta"].fillna(0))]
est["nombre_completo"] = est["nombre_completo"].fillna(est["nombre"] if "nombre" in est else "")
cols = ["nombre_completo", "documento", "grupo", "franja", "feedbacks_meta", "feedbacks_hechos", "feedbacks_atraso",
        "estado_feedback"] + [f"F{n}" for n in range(1, TOT + 1)]
tabla = est[cols]
st.caption(f"{ui.num(len(tabla))} estudiantes. ✓ hecho · ✗ pendiente (su grupo ya tuvo esa clase) · – aún no le toca.")
cfg = {"nombre_completo": "Estudiante", "documento": "Documento", "grupo": "Grupo", "franja": "Jornada",
       "feedbacks_meta": st.column_config.NumberColumn("Meta", format="%d"),
       "feedbacks_hechos": st.column_config.NumberColumn("Hechos", format="%d"),
       "feedbacks_atraso": st.column_config.NumberColumn("Pendientes", format="%d"),
       "estado_feedback": "Estado"}
cfg.update({f"F{n}": st.column_config.TextColumn(f"F{n}", width="small") for n in range(1, TOT + 1)})
st.dataframe(tabla, hide_index=True, width="stretch", height=min(620, 38 + 35 * max(1, len(tabla))), column_config=cfg)

buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    tabla.rename(columns={"nombre_completo": "Estudiante", "documento": "Documento", "grupo": "Grupo",
                          "franja": "Jornada", "feedbacks_meta": "Meta", "feedbacks_hechos": "Hechos",
                          "feedbacks_atraso": "Pendientes", "estado_feedback": "Estado"}
                 ).to_excel(xw, sheet_name="Estudiantes", index=False)
    grupos.to_excel(xw, sheet_name="Grupos", index=False)
st.download_button("Descargar Excel (grupos y estudiantes)", buf.getvalue(), f"tcf10_feedbacks_{hoy:%Y%m%d}.xlsx",
                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:")
