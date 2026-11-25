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
cuenta = form["estado_atenea"].value_counts()
en_curso = int(cuenta.reindex(C.EN_CURSO, fill_value=0).sum())
por_iniciar = int(cuenta.get(C.POR_INICIAR, 0))
aprobados, no_aprobados, abandono = (int(cuenta.get(e, 0)) for e in C.ESTADOS_FINALES)
c = estilo.fila(5, "resumen")
with c[0]:
    estilo.kpi("Base entregada", ui.num(len(df)), "personas en la base de Formalización", "noche")
with c[1]:
    estilo.kpi("Formalizados", ui.num(len(form)), f"frente a {ui.num(C.CUPOS_CONTRATADOS)} cupos del contrato", "azul")
with c[2]:
    estilo.kpi("En curso", ui.num(en_curso), "en alguno de los 5 estados de formación"
               + (f" · {ui.num(por_iniciar)} por iniciar" if por_iniciar else ""), "profundo")
with c[3]:
    estilo.kpi(C.APROBADO, ui.num(aprobados), f"superan el 70 % ({ui.num(C.HORAS_CULMINACION)} h completadas de 90 h)",
               "naranja")
with c[4]:
    estilo.kpi(C.ABANDONO, ui.num(abandono),
               f"{ui.pct(abandono / len(form) if len(form) else None, 1)} de los formalizados · "
               f"{ui.num(no_aprobados)} {C.NO_APROBADO.lower()}", "celeste")

st.write("")
estilo.seccion("Estado de formación")
st.caption("Participantes con su grupo en curso, según su ICP (Índice de Cumplimiento del Plan): su avance "
           "frente a lo que el plan del curso espera a hoy. Responde a los filtros de arriba.")
izq, der = st.columns([1.25, 1], gap="large")
tot = max(1, en_curso)
izq.dataframe(pd.DataFrame({
    "Estado formación": C.EN_CURSO,
    "ICP": [C.rango_estado(e) for e in C.EN_CURSO],
    "Participantes": [ui.num(int(cuenta.get(e, 0))) for e in C.EN_CURSO],
    "%": [ui.pct(int(cuenta.get(e, 0)) / tot, 1) for e in C.EN_CURSO]}), hide_index=True, width="stretch")
der.dataframe(pd.DataFrame({
    "Estado final": C.ESTADOS_FINALES,
    "Concepto": [C.CONCEPTO_FINAL[e] for e in C.ESTADOS_FINALES],
    "Participantes": [ui.num(int(cuenta.get(e, 0))) for e in C.ESTADOS_FINALES]}), hide_index=True, width="stretch")

st.write("")
estilo.seccion("Caracterización")
comun.seccion_caracterizacion(df)

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
    ("Culminación", pagos["culminacion"], "Personas con ≥ 63 h completadas"),
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
ui.grafica_atenea(fig, 400)

# Tabla: cada formalizado está en un solo estado, así que las columnas de estado suman «Formalizados».
estados = [e for e in C.ORDEN_ESTADOS if e != C.NO_FORMALIZADO and (df["estado_atenea"].eq(e).any()
                                                                   or e in C.ESTADOS_FINALES)]
t = (df.assign(asistencia=comun.asistencia_personas(df))
       .groupby("cohorte").agg(base=("id_sis", "size"), formalizados=("enrolado", "sum"),
                               horas=("horas_validas", "mean"), asistencia=("asistencia", "mean")))
conteo = pd.crosstab(df["cohorte"], df["estado_atenea"]).reindex(columns=estados, fill_value=0)
t = t.join(conteo).reset_index()
nombres = {e: e for e in estados}
tabla = pd.DataFrame({"Cohorte": t["cohorte"], "Base": t["base"].map(ui.num),
                      "Formalizados": t["formalizados"].map(ui.num)})
for e in estados:
    tabla[nombres[e]] = t[e].map(ui.num)
tabla["Horas completadas promedio"] = [ui.num(h, 1) if f else "–" for h, f in zip(t["horas"], t["formalizados"])]
tabla["Asistencia promedio"] = t["asistencia"].map(lambda a: ui.pct(a, 1))
st.dataframe(tabla, hide_index=True, width="stretch")
st.caption("Cada persona formalizada aparece en un solo estado: las columnas de estado suman «Formalizados».")
