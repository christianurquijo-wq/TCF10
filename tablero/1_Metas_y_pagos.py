"""Metas contractuales y pagos: cuánto está asegurado, cuánto está en juego y qué falta."""
import plotly.express as px
import streamlit as st

from tcf10 import config as C
from tcf10 import metrics as M
from tcf10 import ui

ui.inicio("Metas y pagos", "Los 4 pagos del contrato ATENEA-497-2026 frente a las metas ofertadas por Kuepa")
df = ui.datos()
pagos = M.pagos(df)
dinero = M.resumen_dinero(pagos)
p2 = next(p for p in pagos if p["clave"] == "culminacion")

# ------------------------------------------------------------------ dinero
c1, c2, c3, c4 = st.columns(4)
with c1:
    ui.tarjeta("Valor del contrato", ui.plata(C.VALOR_CONTRATO),
               f"{ui.num(C.CUPOS_CONTRATADOS)} cupos × ${ui.num(C.COSTO_UNITARIO)}", ui.AZUL)
with c2:
    ui.tarjeta("Asegurado a hoy", ui.plata(dinero["asegurado"]),
               f"{ui.pct(dinero['asegurado'] / dinero['total'])} del contrato · culminados e índices cumplidos",
               ui.VERDE)
with c3:
    ui.tarjeta("Proyección del pago 2", ui.plata(p2["monto_proyectado"]),
               f"si culminan ~{ui.num(p2['proyectados'])} personas según su nivel de riesgo", ui.NARANJA)
with c4:
    perdida = C.VALOR_POR_CULMINADO * max(0, min(C.CUPOS_CONTRATADOS, len(df)) - p2["proyectados"])
    ui.tarjeta("En riesgo por no culminar", ui.plata(perdida),
               f"${ui.num(C.VALOR_POR_CULMINADO)} por cada persona que no llega a 63 h", ui.ROJO)

st.write("")
st.subheader("Estado de cada pago")
cols = st.columns(4)
for col, p in zip(cols, pagos):
    color = ui.COLOR_ESTADO.get(p["estado"], ui.GRIS)
    with col:
        if p["clave"] == "culminacion":
            valor = ui.num(p["culminados"])
            sub = (f"personas culminaron · {ui.plata(p['monto_actual'])} de {ui.plata(p['monto_maximo'])}<br>"
                   f"Proyección: {ui.num(p['proyectados'])} personas")
            extra = ui.barra(p["culminados"] / C.CUPOS_CONTRATADOS, None, color)
        else:
            valor = "–" if p["alcanzado_pct"] is None else f"{p['alcanzado_pct']} %"
            sub = f"Meta ofertada: {ui.pct(p['meta'])} · {ui.plata(p['monto_maximo'])}<br>{p['detalle']}"
            if p["faltan"] and p["medible"] and p["estado"] != "Cumplido":
                sub += f"<br><b>Faltan {ui.num(p['faltan'])} personas</b> para la meta"
            extra = ui.barra(p["actual"], p["meta"], color)
        ui.tarjeta(p["nombre"], valor, sub, color, extra=f"<div style='margin-top:6px'>{ui.pill(p['estado'], color)}</div>" + extra)

st.caption("«En curso»: el índice todavía es parcial (faltan cohortes por enrolar o por cerrar). "
           "«Sin datos»: aún no hay certificaciones o validación PILA registradas. Los índices son todo o nada: "
           "si el valor redondeado a entero queda por debajo de la meta, ese pago no se recibe.")

# ------------------------------------------------------------------ proyección y personas
t_proy, t_pers = ui.pestanas(["Proyección por cohorte", "Personas"], "mp")
with t_proy:
    st.caption("Las metas y los pagos de arriba son siempre del contrato completo. Los filtros y los clics aplican "
               "a esta proyección y a la lista de personas.")
    sel = ui.barra_filtros(df, "mp", ("cohorte", "perfil", "nivel", "grupo", "franja"))
    st.markdown("**¿Cuántas personas llegarán a culminar?** · cada barra reparte a las personas de la cohorte "
                "según su situación hoy")
    dist = (sel.groupby(["cohorte", "riesgo"]).size().rename("personas").reset_index())
    fig = px.bar(dist, x="cohorte", y="personas", color="riesgo", text="personas",
                 category_orders={"riesgo": ui.ORDEN_RIESGO}, color_discrete_map=ui.COLOR_RIESGO)
    fig.update_traces(textposition="inside", texttemplate="%{text:,.0f}")
    fig.update_layout(xaxis_title=None, yaxis_title="Personas", separators=",.")
    ui.grafica(fig, "mp", "dist", {"x": "cohorte", "trace": "riesgo"}, 380)

    coh = M.por_cohorte(sel)
    coh["valor_asegurado"] = coh["culminados"] * C.VALOR_POR_CULMINADO
    proy = sel[sel["enrolado"] & ~sel["retirado"]].groupby("cohorte")["prob_culminar"].sum()
    coh["culminados_proyectados"] = coh["cohorte"].map(proy).fillna(0)
    coh["valor_proyectado"] = coh["culminados_proyectados"] * C.VALOR_POR_CULMINADO
    st.dataframe(
        coh[["cohorte", "enrolados", "culminados", "culminados_proyectados", "riesgo_alto", "riesgo_medio",
             "valor_asegurado", "valor_proyectado"]],
        hide_index=True, width="stretch",
        column_config={
            "cohorte": st.column_config.TextColumn("Cohorte", pinned=True), "enrolados": "Enrolados",
            "culminados": "Culminaron",
            "culminados_proyectados": st.column_config.NumberColumn("Proyección culminados", format="%.0f"),
            "riesgo_alto": "Riesgo alto", "riesgo_medio": "Riesgo medio",
            "valor_asegurado": st.column_config.NumberColumn("Pago 2 asegurado ($)", format="$%,.0f"),
            "valor_proyectado": st.column_config.NumberColumn("Pago 2 proyectado ($)", format="$%,.0f"),
        })
    st.caption(f"Proyección = culminados + activos × probabilidad de culminar según riesgo "
               f"(bajo {ui.pct(C.PROB_CULMINAR['Bajo'])}, medio {ui.pct(C.PROB_CULMINAR['Medio'])}, "
               f"alto {ui.pct(C.PROB_CULMINAR['Alto'])}). Supuesto ajustable en tcf10/config.py.")

with t_pers:
    st.caption(f"{ui.num(len(sel))} personas con los filtros de la pestaña anterior, las de menos horas primero.")
    lista = sel.assign(persona=sel["nombre"].map(ui.iniciales), motivo=sel.apply(M.motivo_riesgo, axis=1))
    st.dataframe(lista[["id_sis", "persona", "cohorte", "grupo", "riesgo", "horas_validas", "tipo_ruta", "motivo"]]
                 .sort_values("horas_validas"), hide_index=True, width="stretch", height=520, column_config={
                     "id_sis": st.column_config.NumberColumn("ID SIS", format="%d", pinned=True),
                     "persona": "Iniciales", "cohorte": "Cohorte", "grupo": "Grupo", "riesgo": "Riesgo",
                     "horas_validas": st.column_config.NumberColumn("Horas válidas", format="%.1f"),
                     "tipo_ruta": "Ruta al 70 %", "motivo": "Por qué"})
