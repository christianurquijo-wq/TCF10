"""Vista interna · asistencia y consumo de plataforma por grupo, casos críticos primero y tipificación por estudiante.

Caso crítico (solo grupos en curso):
  * sin uso de plataforma: 0 h acreditadas con el grupo iniciado hace 7+ días, o 7+ días sin entrar a la plataforma;
  * no alcanza el 70 %: le faltan más clases de las que quedan en su grupo para llegar a 63 h con la plataforma al 100 %;
  * atrasado en Feedbacks: 2 o más Feedbacks pendientes frente a uno por clase dictada (metrics.feedback).
Tipificación (metrics.tipificar): Solo plataforma (≥ 2 clases) · 1 clase + plataforma · 2 clases + plataforma ·
No alcanza · Ya aprobó, con las horas que le faltan.
"""
import io

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tcf10 import config as C
from tcf10 import ui
from vista_atenea import comun

COLOR_RUTA = {"No alcanza": ui.ROJO, "2 clases + plataforma": ui.NARANJA, "1 clase + plataforma": ui.NARANJA_CLARO,
              "Solo plataforma": ui.AZUL, "Ya aprobó": ui.VERDE}

ui.inicio("Grupos y casos críticos", "Asistencia, plataforma y Feedbacks por grupo, con los casos que necesitan "
          "acción primero")
df = ui.datos()
hoy = comun.hoy()
if "critico" not in df:  # tabla de una versión anterior en memoria: se tipifica aquí
    from tcf10 import metrics as M
    df = M.tipificar(df, hoy)
df = ui.barra_filtros(df, "gc", ("cohorte", "perfil", "nivel", "grupo", "franja", "docente"))
# En formación: formalizados, no retirados, que aún no culminan y cuyo grupo ya inició.
form = df[df["enrolado"] & ~df["retirado"] & df["cohorte_iniciada"]].copy()
en_curso = form[~form["culmino"] & ~form["cohorte_cerrada"]]
if form.empty:
    st.info("Aún no hay grupos iniciados para este filtro.", icon=":material/filter_alt_off:")
    st.stop()

# Esperado a la fecha en plataforma (proporcional al calendario del grupo)
form["plat_esperada"] = form["avance_esperado_h"] / C.HORAS_TOTALES * C.HORAS_ASINCRONICAS
form["con_actividad"] = form["horas_asinc"] > 0
form["fb_crit"] = form["critico_feedback"] if "critico_feedback" in form else False
# motivo principal de cada crítico, para apilar sin contar dos veces: plataforma > no alcanza > Feedbacks
form["solo_no_alcanza"] = form["critico"] & ~form["sin_plataforma"] & form["no_alcanza"]
form["solo_feedback"] = form["critico"] & ~form["sin_plataforma"] & ~form["no_alcanza"] & form["fb_crit"]

# ------------------------------------------------------------------ indicadores
crit = en_curso[en_curso["critico"]]
fb_crit = en_curso["critico_feedback"] if "critico_feedback" in en_curso else pd.Series(False, index=en_curso.index)
c = st.columns(5)
with c[0]:
    ui.tarjeta("En curso", ui.num(len(en_curso)), "grupos en curso, sin aprobar aún", ui.AZUL)
with c[1]:
    ui.tarjeta("Casos críticos", ui.num(len(crit)),
               f"{ui.pct(len(crit) / len(en_curso) if len(en_curso) else None, 1)} de quienes están en curso", ui.ROJO)
with c[2]:
    ui.tarjeta("Sin uso de plataforma", ui.num(int(en_curso["sin_plataforma"].sum())),
               f"0 h o {C.DIAS_SIN_PLATAFORMA}+ días sin entrar", ui.NARANJA)
with c[3]:
    ui.tarjeta("No alcanzan el 70 %", ui.num(int((en_curso["no_alcanza"]).sum())),
               "les faltan más clases de las que quedan", ui.ROJO)
with c[4]:
    ui.tarjeta("Atrasados en Feedbacks", ui.num(int(fb_crit.sum())),
               f"{C.FEEDBACK_ATRASO_CRITICO} o más Feedbacks pendientes", ui.NARANJA_CLARO)

# ------------------------------------------------------------------ por grupo
grupos = (form.groupby("grupo")
          .agg(franja=("franja", "first"), docente=("docente", "first"), estudiantes=("id_sis", "size"),
               asistidas=("sesiones_asistidas", "sum"), registradas=("sesiones_registradas", "sum"),
               horas_plat=("horas_asinc_val", "mean"), esperada=("plat_esperada", "mean"),
               con_actividad=("con_actividad", "mean"), criticos=("critico", "sum"),
               sin_plat=("sin_plataforma", "sum"), no_alcanza=("no_alcanza", "sum"),
               solo_no_alcanza=("solo_no_alcanza", "sum"), solo_feedback=("solo_feedback", "sum"),
               fb_atrasados=("fb_crit", "sum"))
          .reset_index())
grupos["asistencia"] = grupos["asistidas"] / grupos["registradas"].where(grupos["registradas"] > 0)
grupos["pct_criticos"] = grupos["criticos"] / grupos["estudiantes"]
grupos["vs_esperado"] = grupos["horas_plat"] / grupos["esperada"].where(grupos["esperada"] > 0)
grupos = grupos.sort_values(["pct_criticos", "criticos", "asistencia"], ascending=[False, False, True])

t_graf, t_grupos, t_est = ui.pestanas(["Gráficas", "Por grupo", "Estudiantes"], "gc")

with t_graf:
    izq, der = st.columns([1, 1.3], gap="large")
    with izq:
        st.markdown("**Ruta para llegar al 70 %**")
        t = form["tipo_ruta"].value_counts().reindex(C.TIPOS_RUTA, fill_value=0)
        fig = go.Figure(go.Bar(x=t.values, y=t.index, orientation="h", marker_color=[COLOR_RUTA[k] for k in t.index],
                               text=[ui.num(v) for v in t.values], textposition="outside",
                               hovertemplate="%{y}: %{x} estudiantes<extra></extra>"))
        fig.update_layout(yaxis=dict(autorange="reversed", title=None), xaxis_title=None, separators=",.",
                          xaxis=dict(range=[0, max(1, t.max()) * 1.2]))
        ui.grafica(fig, "gc", "ruta", {"y": "tipo_ruta"}, 300)
        st.caption(f"Con la plataforma al 100 % ({ui.num(C.HORAS_ASINCRONICAS, 1)} h) faltan "
                   f"{ui.num(C.HORAS_CULMINACION - C.HORAS_ASINCRONICAS, 1)} h con docente: 2 clases de "
                   f"{ui.num(C.HORAS_POR_SESION)} h.")
    with der:
        top = grupos[grupos["criticos"] > 0].sort_values("criticos", ascending=False)
        st.markdown(f"**Grupos con casos críticos** · {ui.num(len(top))} grupos")
        if top.empty:
            st.success("Ningún grupo tiene casos críticos con este filtro.", icon=":material/check_circle:")
        else:
            orden = top.iloc[::-1]
            fig = go.Figure()
            for col_, nombre, color in (("sin_plat", "Sin plataforma", ui.NARANJA),
                                        ("solo_no_alcanza", "No alcanza", ui.ROJO),
                                        ("solo_feedback", "Solo Feedbacks", "#F5A54A")):
                fig.add_bar(y=orden["grupo"], x=orden[col_], name=nombre, orientation="h", marker_color=color,
                            hovertemplate=f"%{{y}} · {nombre}: %{{x}}<extra></extra>")
            fig.update_layout(barmode="stack", xaxis_title=None, separators=",.",
                              yaxis=dict(title=None, range=ui.rango_categorias(orden["grupo"])))
            ui.grafica(fig, "gc", "grupos", {"y": "grupo"}, ui.alto_barras(len(orden)), alto_max=420)
            st.caption("Toca un grupo para ver solo sus estudiantes.")

with t_grupos:
    st.caption("Ordenado de más a menos casos críticos (%). «Plataforma vs. esperado»: horas promedio del grupo "
               "frente a lo que debería llevar hoy según su calendario.")
    vista = grupos.assign(asistencia=grupos["asistencia"] * 100, con_actividad=grupos["con_actividad"] * 100,
                          pct_criticos=grupos["pct_criticos"] * 100, vs_esperado=grupos["vs_esperado"] * 100)
    st.dataframe(
        vista[["grupo", "franja", "docente", "estudiantes", "criticos", "pct_criticos", "sin_plat", "no_alcanza",
               "fb_atrasados", "asistencia", "horas_plat", "esperada", "vs_esperado", "con_actividad"]],
        hide_index=True, width="stretch", height=min(560, 38 + 35 * len(vista)), column_config={
            "grupo": st.column_config.TextColumn("Grupo", pinned=True), "franja": "Jornada", "docente": "Docente",
            "estudiantes": "Estudiantes", "criticos": st.column_config.NumberColumn("Críticos", format="%d"),
            "pct_criticos": st.column_config.ProgressColumn("% críticos", format="%.0f %%", min_value=0,
                                                            max_value=100),
            "sin_plat": st.column_config.NumberColumn("Sin plataforma", format="%d"),
            "no_alcanza": st.column_config.NumberColumn("No alcanzan", format="%d"),
            "fb_atrasados": st.column_config.NumberColumn("Atrasados en Feedbacks", format="%d"),
            "asistencia": st.column_config.ProgressColumn("Asistencia", format="%.0f %%", min_value=0, max_value=100),
            "horas_plat": st.column_config.NumberColumn("Plataforma (h prom.)", format="%.1f"),
            "esperada": st.column_config.NumberColumn("Esperado a hoy (h)", format="%.1f"),
            "vs_esperado": st.column_config.NumberColumn("Plataforma vs. esperado", format="%.0f %%"),
            "con_actividad": st.column_config.ProgressColumn("% con actividad", format="%.0f %%", min_value=0,
                                                             max_value=100),
        })

with t_est:
    g1, g2 = st.columns([2.2, 1], vertical_alignment="bottom")
    tipos = g1.pills("Ruta al 70 %", C.TIPOS_RUTA, selection_mode="multi", key="gc_tipos")
    solo_crit = g2.toggle("Solo críticos", value=True, key="gc_solo")
    est = form
    if tipos:
        est = est[est["tipo_ruta"].isin(tipos)]
    if solo_crit:
        est = est[est["critico"]]
    est = comun.con_identidad(est)
    est["asistencia"] = (est["sesiones_asistidas"] / est["sesiones_registradas"].where(est["sesiones_registradas"] > 0)) * 100
    est["orden"] = est["tipo_ruta"].map({k: i for i, k in enumerate(C.TIPOS_RUTA)})
    est = est.sort_values(["critico", "orden", "faltan_h"], ascending=[False, True, False])
    st.caption(f"{ui.num(len(est))} estudiantes, críticos primero. «Faltan»: horas válidas que le faltan para 63 h; "
               "«En plataforma»: las que debe completar en plataforma si toma solo las clases mínimas de su ruta.")
    tabla = est[["nombre_completo", "documento", "grupo", "tipo_ruta", "motivo_critico", "faltan_h", "clases_faltantes",
                 "faltan_plataforma_h", "sesiones_restantes", "horas_sinc_val", "horas_asinc_val", "asistencia",
                 "ultima_plataforma"]].copy()
    tabla["nombre_completo"] = tabla["nombre_completo"].fillna(est["nombre"] if "nombre" in est else "")
    st.dataframe(tabla, hide_index=True, width="stretch", height=min(600, 38 + 35 * max(1, len(tabla))),
                 column_config={
                     "nombre_completo": st.column_config.TextColumn("Estudiante", pinned=True),
                     "documento": "Documento", "grupo": "Grupo", "tipo_ruta": "Ruta al 70 %",
                     "motivo_critico": "Por qué es crítico",
                     "faltan_h": st.column_config.NumberColumn("Faltan (h)", format="%.1f"),
                     "clases_faltantes": st.column_config.NumberColumn("Clases que faltan", format="%d"),
                     "faltan_plataforma_h": st.column_config.NumberColumn("En plataforma (h)", format="%.1f"),
                     "sesiones_restantes": st.column_config.NumberColumn("Clases que quedan", format="%d"),
                     "horas_sinc_val": st.column_config.NumberColumn("Con docente (h)", format="%.1f"),
                     "horas_asinc_val": st.column_config.NumberColumn("Plataforma (h)", format="%.1f"),
                     "asistencia": st.column_config.ProgressColumn("Asistencia", format="%.0f %%", min_value=0,
                                                                   max_value=100),
                     "ultima_plataforma": st.column_config.DateColumn("Último ingreso plataforma", format="DD/MM/YYYY"),
                 })
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        tabla.to_excel(xw, sheet_name="Estudiantes", index=False)
        grupos.to_excel(xw, sheet_name="Grupos", index=False)
    st.download_button("Descargar Excel", buf.getvalue(), f"tcf10_casos_criticos_{hoy:%Y%m%d}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", icon=":material/download:")
