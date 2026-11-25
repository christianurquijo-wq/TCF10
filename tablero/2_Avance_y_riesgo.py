"""Avance de horas y estado de formación por beneficiario (cuadro Kuepa EduTech, nov-2026)."""
import plotly.graph_objects as go
import streamlit as st

from tcf10 import config as C
from tcf10 import metrics as M
from tcf10 import ui

ui.inicio("Avance y estado de formación", f"Horas completadas frente a la meta de {ui.num(C.HORAS_CULMINACION)} h "
          f"(70 % de {ui.num(C.HORAS_TOTALES)} h) y estado según el ICP (cumplimiento del plan a hoy)")
df = ui.datos()
df = ui.barra_filtros(df, "av", ("cohorte", "perfil", "nivel", "grupo", "franja", "docente"))
en_curso = df[df["riesgo"].isin(C.EN_CURSO)]
ORDEN = {e: i for i, e in enumerate(reversed(C.EN_CURSO))}  # Matriculado Inactivo primero (más urgente)

cols = st.columns(len(C.EN_CURSO))
for col, (estado, _) in zip(cols, C.ESTADOS_FORMACION):
    n = int(en_curso["riesgo"].eq(estado).sum())
    nota = f"ICP {C.rango_estado(estado)}"
    if estado in (C.RIESGO_ALTO, C.INACTIVO):
        nota += f" · {ui.plata(n * C.VALOR_POR_CULMINADO)} en juego"
    with col:
        ui.tarjeta(estado, ui.num(n), nota, ui.COLOR_RIESGO[estado])
finales = df["riesgo"].value_counts()
st.caption(" · ".join(f"**{e}:** {ui.num(int(finales.get(e, 0)))} ({C.CONCEPTO_FINAL[e].lower()})"
                      for e in C.ESTADOS_FINALES) + f" · **En curso:** {ui.num(len(en_curso))}")

t_graf, t_lista = ui.pestanas(["Gráficas", "Lista de seguimiento"], "av")
with t_graf:
    izq, der = st.columns([1.1, 1], gap="large")
    with izq:
        st.markdown("**Distribución de horas completadas**")
        fig = go.Figure()
        for r in C.EN_CURSO + [C.APROBADO]:
            x = df.loc[df["riesgo"].eq(r), "horas_validas"]
            if len(x):
                fig.add_histogram(x=x, name=r, marker_color=ui.COLOR_RIESGO[r], xbins=dict(start=0, end=90, size=3),
                                  hovertemplate=f"{r}<br>%{{x}} h: %{{y}} personas<extra></extra>")
        ui.linea_meta(fig, C.HORAS_CULMINACION, f"Aprobación {ui.num(C.HORAS_CULMINACION)} h (70 %)", color=ui.NARANJA)
        fig.update_layout(barmode="stack", xaxis_title=f"Horas completadas ({C.ETQ_SINC.lower()} + {C.ETQ_ASINC.lower()})",
                          yaxis_title="Personas", separators=",.")
        ui.grafica(fig, "av", "histo", {"trace": "riesgo"}, 380)
        st.caption("Toca un color para ver solo ese estado.")
    with der:
        g = (en_curso.groupby(["grupo", "riesgo"]).size().unstack(fill_value=0)
             .reindex(columns=C.EN_CURSO, fill_value=0))
        g = g.assign(_o=(g[C.INACTIVO] + g[C.RIESGO_ALTO]) * 1000 + g[C.RIESGO_BAJO]).sort_values(
            "_o", ascending=False).drop(columns="_o")
        st.markdown(f"**Estado de formación por grupo** · {ui.num(len(g))} grupos, más inactivos y riesgo alto arriba")
        orden = g.iloc[::-1]
        fig = go.Figure()
        for r in reversed(C.EN_CURSO):
            fig.add_bar(y=orden.index, x=orden[r], name=r, orientation="h", marker_color=ui.COLOR_RIESGO[r],
                        hovertemplate=f"%{{y}} · {r}: %{{x}}<extra></extra>")
        fig.update_layout(barmode="stack", yaxis=dict(title=None, range=ui.rango_categorias(orden.index)), xaxis_title=None,
                          separators=",.")
        ui.grafica(fig, "av", "grupos", {"y": "grupo", "trace": "riesgo"}, ui.alto_barras(len(orden)), alto_max=380)

# ------------------------------------------------------------------ lista priorizada
with t_lista:
    if ui.sensible_activo():
        ui.aviso_sensible()
    else:
        niveles = st.pills("Estado de formación", C.EN_CURSO, selection_mode="multi", key="av_niv",
                           default=[C.INACTIVO, C.RIESGO_ALTO, C.RIESGO_BAJO])
        lista = en_curso[en_curso["riesgo"].isin(niveles or C.EN_CURSO)].copy()
        lista["orden"] = lista["riesgo"].map(ORDEN)
        lista["pct_esp"] = lista["pct_esperado"] * 100
        lista = lista.sort_values(["orden", "pct_esperado", "dias_sin_actividad"], ascending=[True, True, False])
        lista["persona"] = lista["nombre"].map(ui.iniciales)
        lista["id_sis"] = lista["id_sis"].where(lista["id_sis"] > 0)  # negativos = sin usuario en el SIS
        lista["motivo"] = lista.apply(M.motivo_riesgo, axis=1)
        lista["faltan_h"] = (C.HORAS_CULMINACION - lista["horas_validas"]).clip(lower=0)
        st.caption(f"{ui.num(len(lista))} personas, las más urgentes primero.")
        vista = lista[["riesgo", "pct_esp", "id_sis", "persona", "cohorte", "grupo", "docente", "gestor", "horas_sinc_val",
                       "horas_asinc_val", "horas_validas", "avance_esperado_h", "faltan_h", "dias_sin_actividad", "motivo"]]
        st.dataframe(
            vista, hide_index=True, width="stretch", height=520,
            column_config={
                "riesgo": st.column_config.TextColumn("Estado formación", pinned=True),
                "pct_esp": st.column_config.NumberColumn("ICP", format="%.0f %%"),
                "id_sis": st.column_config.NumberColumn("ID SIS", format="%d"), "persona": "Iniciales",
                "cohorte": "Cohorte", "grupo": "Grupo", "docente": "Docente", "gestor": "Gestor",
                "horas_sinc_val": st.column_config.NumberColumn("Sincrónico (h)", format="%.1f"),
                "horas_asinc_val": st.column_config.NumberColumn("Asincrónico (h)", format="%.1f"),
                "horas_validas": st.column_config.ProgressColumn("Horas completadas", format="%.1f",
                                                                 min_value=0, max_value=C.HORAS_CULMINACION),
                "avance_esperado_h": st.column_config.NumberColumn("Plan a hoy (h)", format="%.1f"),
                "faltan_h": st.column_config.NumberColumn("Faltan para 63 h", format="%.1f"),
                "dias_sin_actividad": st.column_config.NumberColumn("Días sin actividad", format="%d"),
                "motivo": "Por qué",
            })
        st.download_button("Descargar lista (CSV)", vista.to_csv(index=False).encode("utf-8-sig"),
                           "tcf10_seguimiento.csv", "text/csv", icon=":material/download:")
