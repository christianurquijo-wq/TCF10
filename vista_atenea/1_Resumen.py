"""Resumen del contrato para Atenea: participantes, estado de formación y metas (sin montos)."""
import plotly.express as px
import streamlit as st

from tcf10 import config as C
from tcf10 import metrics as M
from tcf10 import ui
from vista_atenea import comun

ui.inicio("Resumen del programa", "Participantes, estado de formación y metas del contrato ATENEA-497-2026")
completo = comun.todos()
df = comun.filtrado(completo)
comun.nota_filtros()

form = df[df["enrolado"]]
en_formacion = int(df["estado_atenea"].eq("En formación").sum())
culminaron = int(df["estado_atenea"].eq("Culminó").sum())
desistieron = int(df["estado_atenea"].eq("Desistió").sum())
asis = comun.asistencia_personas(form)
c = st.columns(5)
with c[0]:
    ui.tarjeta("Base entregada", ui.num(len(df)), "personas en la base de Formalización", ui.NOCHE)
with c[1]:
    ui.tarjeta("Formalizados", ui.num(len(form)), f"frente a {ui.num(C.CUPOS_CONTRATADOS)} cupos del contrato", ui.AZUL)
with c[2]:
    ui.tarjeta("En formación", ui.num(en_formacion), "formalizados que aún no culminan", ui.AZUL)
with c[3]:
    ui.tarjeta("Culminaron", ui.num(culminaron), f"≥ {ui.num(C.HORAS_CULMINACION)} h válidas (70 % de 90 h)", ui.NARANJA)
with c[4]:
    ui.tarjeta("Desistieron", ui.num(desistieron),
               f"{ui.pct(desistieron / len(form) if len(form) else None, 1)} de los formalizados", ui.GRIS)

st.write("")
st.subheader("Metas del contrato")
st.caption("Se calculan sobre toda la base, sin filtros. Los índices se liquidan al cierre de las cohortes.")
pagos = {p["clave"]: p for p in M.pagos(completo)}
cols = st.columns(4)
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
        ui.tarjeta(nombre, valor, sub, color,
                   extra=f"<div style='margin-top:6px'>{ui.pill(p['estado'], color)}</div>" + extra)

st.write("")
st.subheader("Participantes por cohorte y estado")
dist = df.groupby(["cohorte", "estado_atenea"]).size().rename("personas").reset_index()
fig = px.bar(dist, x="cohorte", y="personas", color="estado_atenea", text="personas",
             category_orders={"estado_atenea": comun.ORDEN_ESTADO}, color_discrete_map=comun.COLOR_ESTADO,
             labels={"estado_atenea": "Estado", "cohorte": "", "personas": "Personas"})
fig.update_traces(texttemplate="%{text:,.0f}", textposition="inside")
fig.update_layout(separators=",.", legend=dict(orientation="h", y=1.12, title=None))
st.plotly_chart(ui.dark_layout(fig, 380), width="stretch")

tabla = (df.assign(asistencia=comun.asistencia_personas(df))
           .groupby("cohorte").agg(base=("id_sis", "size"), formalizados=("enrolado", "sum"),
                                   en_formacion=("estado_atenea", lambda s: int(s.eq("En formación").sum())),
                                   culminaron=("estado_atenea", lambda s: int(s.eq("Culminó").sum())),
                                   desistieron=("estado_atenea", lambda s: int(s.eq("Desistió").sum())),
                                   horas=("horas_validas", "mean"), asistencia=("asistencia", "mean"))
           .reset_index())
tabla["asistencia"] = tabla["asistencia"] * 100
st.dataframe(tabla, hide_index=True, width="stretch", column_config={
    "cohorte": "Cohorte", "base": "Base", "formalizados": "Formalizados", "en_formacion": "En formación",
    "culminaron": "Culminaron", "desistieron": "Desistieron",
    "horas": st.column_config.NumberColumn("Horas válidas promedio", format="%.1f"),
    "asistencia": st.column_config.NumberColumn("Asistencia promedio", format="%.1f %%"),
})
