"""Avance de horas y nivel de riesgo por beneficiario (Anexo 8: alertas y niveles alto/medio/bajo)."""
import plotly.graph_objects as go
import streamlit as st

from tcf10 import config as C
from tcf10 import metrics as M
from tcf10 import ui

ui.inicio("Avance y riesgo", f"Horas válidas frente a la meta de {ui.num(C.HORAS_CULMINACION)} h "
          f"(70 % de {ui.num(C.HORAS_TOTALES)} h) y alertas tempranas de deserción")
df = ui.datos()
df = ui.barra_filtros(df, "av", ("cohorte", "grupo", "franja", "docente"))
en_curso = df[df["riesgo"].isin(["Alto", "Medio", "Bajo"])]

c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.tarjeta("En formación", ui.num(len(en_curso)), "enrolados activos que aún no culminan", ui.AZUL)
with c2:
    n = int(en_curso["riesgo"].eq("Alto").sum())
    ui.tarjeta("Riesgo alto", ui.num(n),
               f"ritmo < {ui.pct(C.RIESGO['alto']['ritmo_menor_a'])} o ≥ {C.RIESGO['alto']['dias_sin_actividad']} días "
               f"sin actividad · {ui.plata(n * C.VALOR_POR_CULMINADO)} en juego", ui.ROJO)
with c3:
    n = int(en_curso["riesgo"].eq("Medio").sum())
    ui.tarjeta("Riesgo medio", ui.num(n),
               f"ritmo < {ui.pct(C.RIESGO['medio']['ritmo_menor_a'])} o ≥ {C.RIESGO['medio']['dias_sin_actividad']} días "
               "sin actividad", ui.AMARILLO)
with c4:
    ui.tarjeta("Culminaron", ui.num(int(df["culmino"].sum())), f"≥ {ui.num(C.HORAS_CULMINACION)} h válidas", ui.VERDE)

t_graf, t_lista = ui.pestanas(["Gráficas", "Lista de seguimiento"], "av")
with t_graf:
    izq, der = st.columns([1.1, 1], gap="large")
    with izq:
        st.markdown("**Distribución de horas válidas**")
        fig = go.Figure()
        for r in ["Bajo", "Medio", "Alto", "Culminó"]:
            x = df.loc[df["riesgo"].eq(r), "horas_validas"]
            if len(x):
                fig.add_histogram(x=x, name=r, marker_color=ui.COLOR_RIESGO[r], xbins=dict(start=0, end=90, size=3),
                                  hovertemplate=f"{r}<br>%{{x}} h: %{{y}} personas<extra></extra>")
        ui.linea_meta(fig, C.HORAS_CULMINACION, f"Meta {ui.num(C.HORAS_CULMINACION)} h", color=ui.NARANJA)
        fig.update_layout(barmode="stack", xaxis_title="Horas válidas (con docente + plataforma)",
                          yaxis_title="Personas", separators=",.")
        ui.grafica(fig, "av", "histo", {"trace": "riesgo"}, 380)
        st.caption("Toca un color para ver solo ese nivel de riesgo.")
    with der:
        g = (en_curso.groupby(["grupo", "riesgo"]).size().unstack(fill_value=0)
             .reindex(columns=["Alto", "Medio", "Bajo"], fill_value=0))
        g = g.assign(_o=g["Alto"] * 1000 + g["Medio"]).sort_values("_o", ascending=False).drop(columns="_o")
        st.markdown(f"**Riesgo por grupo** · {ui.num(len(g))} grupos, más riesgo alto arriba")
        orden = g.iloc[::-1]
        fig = go.Figure()
        for r in ["Alto", "Medio", "Bajo"]:
            fig.add_bar(y=orden.index, x=orden[r], name=r, orientation="h", marker_color=ui.COLOR_RIESGO[r],
                        hovertemplate=f"%{{y}} · {r}: %{{x}}<extra></extra>")
        fig.update_layout(barmode="stack", yaxis=dict(title=None, range=[-.6, len(orden) - .4]), xaxis_title=None,
                          separators=",.")
        ui.grafica(fig, "av", "grupos", {"y": "grupo", "trace": "riesgo"}, ui.alto_barras(len(orden)), alto_max=380)

# ------------------------------------------------------------------ lista priorizada
with t_lista:
    niveles = st.pills("Nivel de riesgo", ["Alto", "Medio", "Bajo"], selection_mode="multi", key="av_niv",
                       default=["Alto", "Medio"])
    lista = en_curso[en_curso["riesgo"].isin(niveles or ["Alto", "Medio", "Bajo"])].copy()
    lista["orden"] = lista["riesgo"].map({"Alto": 0, "Medio": 1, "Bajo": 2})
    lista = lista.sort_values(["orden", "ritmo", "dias_sin_actividad"], ascending=[True, True, False])
    lista["persona"] = lista["nombre"].map(ui.iniciales)
    lista["id_sis"] = lista["id_sis"].where(lista["id_sis"] > 0)  # negativos = sin usuario en el SIS
    lista["motivo"] = lista.apply(M.motivo_riesgo, axis=1)
    lista["faltan_h"] = (C.HORAS_CULMINACION - lista["horas_validas"]).clip(lower=0)
    st.caption(f"{ui.num(len(lista))} personas, las más urgentes primero.")
    vista = lista[["riesgo", "id_sis", "persona", "cohorte", "grupo", "docente", "gestor", "horas_sinc_val",
                   "horas_asinc_val", "horas_validas", "avance_esperado_h", "faltan_h", "dias_sin_actividad", "motivo"]]
    st.dataframe(
        vista, hide_index=True, width="stretch", height=520,
        column_config={
            "riesgo": st.column_config.TextColumn("Riesgo", pinned=True),
            "id_sis": st.column_config.NumberColumn("ID SIS", format="%d"), "persona": "Iniciales",
            "cohorte": "Cohorte", "grupo": "Grupo", "docente": "Docente", "gestor": "Gestor",
            "horas_sinc_val": st.column_config.NumberColumn("Con docente (h)", format="%.1f"),
            "horas_asinc_val": st.column_config.NumberColumn("Plataforma (h)", format="%.1f"),
            "horas_validas": st.column_config.ProgressColumn("Horas válidas", format="%.1f",
                                                             min_value=0, max_value=C.HORAS_CULMINACION),
            "avance_esperado_h": st.column_config.NumberColumn("Esperado hoy (h)", format="%.1f"),
            "faltan_h": st.column_config.NumberColumn("Faltan para 63 h", format="%.1f"),
            "dias_sin_actividad": st.column_config.NumberColumn("Días sin actividad", format="%d"),
            "motivo": "Por qué",
        })
    st.download_button("Descargar lista (CSV)", vista.to_csv(index=False).encode("utf-8-sig"),
                       "tcf10_seguimiento.csv", "text/csv", icon=":material/download:")
