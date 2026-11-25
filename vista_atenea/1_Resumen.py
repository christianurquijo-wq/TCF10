"""Resumen del contrato para Atenea: participantes, estado de formación y metas (sin montos)."""
import pandas as pd
import plotly.express as px
import streamlit as st

from tcf10 import config as C
from tcf10 import metrics as M
from tcf10 import ui
from vista_atenea import comun, estilo

estilo.pagina("Resumen del programa", "Participantes, estado de formación y metas del contrato ATENEA-497-2026")
completo = comun.todos()
df = comun.filtrado(completo)
comun.nota_filtros()

form = df[df["enrolado"]]
culminaron = int(df["estado_atenea"].eq("Culminó").sum())
desistieron = int(df["estado_atenea"].eq("Desistió").sum())
# «En formación» = formalizados que no han culminado ni desistido, para que las tarjetas sumen los formalizados.
# Incluye a quienes aún no inician su grupo (la nota lo detalla).
en_formacion = len(form) - culminaron - desistieron
otros = {e: int(form["estado_atenea"].eq(e).sum()) for e in ("Por iniciar",)}
detalle = " · ".join(f"{ui.num(n)} {e.lower()}" for e, n in otros.items() if n)
nota_formacion = "formalizados que aún no culminan" + (f" · incluye {detalle}" if detalle else "")
asis = comun.asistencia_personas(form)
c = estilo.fila(5, "resumen")
with c[0]:
    estilo.kpi("Base entregada", ui.num(len(df)), "personas en la base de Formalización", "noche")
with c[1]:
    estilo.kpi("Formalizados", ui.num(len(form)), f"frente a {ui.num(C.CUPOS_CONTRATADOS)} cupos del contrato", "azul")
with c[2]:
    estilo.kpi("En formación", ui.num(en_formacion), nota_formacion, "profundo")
with c[3]:
    estilo.kpi("Culminaron", ui.num(culminaron), f"≥ {ui.num(C.HORAS_CULMINACION)} h válidas (70 % de 90 h)", "naranja")
with c[4]:
    estilo.kpi("Desistieron", ui.num(desistieron),
               f"{ui.pct(desistieron / len(form) if len(form) else None, 1)} de los formalizados", "celeste")

st.write("")
estilo.seccion("Participantes por programa y nivel")
st.caption("Formalizados según la Asignación docente: grupos distintos y participantes. Responde a los filtros de "
           "arriba.")
st.markdown(ui.tabla_programa_nivel(M.programa_nivel(df)), unsafe_allow_html=True)

st.write("")
estilo.seccion("Metas del contrato")
st.caption("Se calculan sobre toda la base, sin filtros. Los índices se liquidan al cierre de las cohortes.")
pagos = {p["clave"]: p for p in M.pagos(completo)}
cols = estilo.fila(4, "metas")
fichas = [
    ("Enrolamiento", pagos["enrolamiento"], "Formalizados ÷ cupos contratados"),
    ("Culminación", pagos["culminacion"], "Personas con ≥ 63 h válidas"),
    ("Índice de éxito", pagos["exito"], "Certificados de industria ÷ culminados"),
    ("Tránsito laboral", pagos["tml"], "Formales en PILA a 3 meses ÷ culminados (convocatoria abierta)"),
]
for col, (nombre, p, formula) in zip(cols, fichas):
    color = ui.COLOR_ESTADO.get(p["estado"], ui.GRIS)
    with col:
        if p["clave"] == "culminacion":
            valor, sub = ui.num(p["culminados"]), f"personas culminaron · {formula}"
            extra = ui.barra(p["culminados"] / C.CUPOS_CONTRATADOS, None, color)
        else:
            valor = "–" if p["alcanzado_pct"] is None else f"{min(p['alcanzado_pct'], 100)} %"
            sub = f"Meta: {ui.pct(p['meta'])} · {formula}"
            extra = ui.barra(p["actual"], p["meta"], color)
        avance = (p["culminados"] / C.CUPOS_CONTRATADOS) if p["clave"] == "culminacion" else p["actual"]
        estilo.meta(nombre, valor, sub, p["estado"], avance, p["meta"])

st.write("")
estilo.seccion("Participantes por cohorte y estado")
dist = df.groupby(["cohorte", "estado_atenea"]).size().rename("personas").reset_index()
totales = df.groupby("cohorte").size()
fig = px.bar(dist, x="cohorte", y="personas", color="estado_atenea", text="personas",
             category_orders={"estado_atenea": comun.ORDEN_ESTADO, "cohorte": list(totales.index)},
             color_discrete_map=comun.COLOR_ESTADO,
             labels={"estado_atenea": "Estado", "cohorte": "", "personas": "Personas"})
# Cifra dentro del segmento solo si cabe; el total de cada cohorte va encima de la barra (antes solo se leía
# el segmento grande y los pequeños —p. ej. culminó— no se veían, así que la barra parecía no cuadrar).
fig.update_traces(texttemplate="%{text:,.0f}", textposition="inside", insidetextanchor="middle",
                  hovertemplate="%{x} · %{fullData.name}: %{y:,.0f}<extra></extra>")
fig.update_layout(uniformtext=dict(minsize=11, mode="hide"), separators=",.",
                  legend=dict(orientation="h", y=1.14, title=None), yaxis=dict(range=[0, totales.max() * 1.12]))
for coh, tot in totales.items():
    fig.add_annotation(x=coh, y=tot, text=f"<b>{ui.num(tot)}</b>", showarrow=False, yshift=12,
                       font=dict(color=ui.NOCHE, size=13))
st.plotly_chart(ui.dark_layout(fig, 400), width="stretch")

# Tabla: cada formalizado está en un solo estado, así que las columnas de estado suman «Formalizados».
estados = [e for e in ["En formación", "Por iniciar", "Culminó", "Desistió"]
           if df["estado_atenea"].eq(e).any() or e in ("En formación", "Culminó", "Desistió")]
t = (df.assign(asistencia=comun.asistencia_personas(df))
       .groupby("cohorte").agg(base=("id_sis", "size"), formalizados=("enrolado", "sum"),
                               horas=("horas_validas", "mean"), asistencia=("asistencia", "mean")))
conteo = pd.crosstab(df["cohorte"], df["estado_atenea"]).reindex(columns=estados, fill_value=0)
t = t.join(conteo).reset_index()
nombres = {"En formación": "En formación", "Por iniciar": "Por iniciar", "Culminó": "Culminaron",
           "Desistió": "Desistieron"}
tabla = pd.DataFrame({"Cohorte": t["cohorte"], "Base": t["base"].map(ui.num),
                      "Formalizados": t["formalizados"].map(ui.num)})
for e in estados:
    tabla[nombres[e]] = t[e].map(ui.num)
tabla["Horas válidas promedio"] = [ui.num(h, 1) if f else "–" for h, f in zip(t["horas"], t["formalizados"])]
tabla["Asistencia promedio"] = t["asistencia"].map(lambda a: ui.pct(a, 1))
st.dataframe(tabla, hide_index=True, width="stretch")
st.caption("Cada persona formalizada aparece en un solo estado: las columnas de estado suman «Formalizados».")
