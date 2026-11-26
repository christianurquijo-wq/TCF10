"""Gráficas de la página Progreso de la vista Atenea (nov-2026, rediseño):

- Horas promedio por grupo: barra apilada Sincrónico + Asincrónico por grupo, con lo que el plan espera a hoy
  (marca naranja) y la meta de 63 h. Los grupos más atrasados frente al plan van arriba. Muchos grupos → caja con
  scroll y el eje arriba, para leer las horas sin bajar hasta el final.
- Avance en los cursos: % de inscripciones completadas / en progreso / sin iniciar, un panel por programa y una
  barra por nivel (Básico → Avanzado), con el % escrito dentro de cada tramo y el total de inscripciones.

Los cálculos están en funciones sin Streamlit (datos_horas_grupo, datos_cursos) para poder probarlos.
"""
from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from tcf10 import config as C
from tcf10 import ui

NIVELES = ["Básico", "Intermedio", "Avanzado"]
ESTADOS_CURSO = [("completado", "Completado", ui.NOCHE, "#FFFFFF"),
                 ("en_progreso", "En progreso", ui.AZUL, "#FFFFFF"),
                 ("sin_iniciar", "Sin iniciar", ui.CELESTE, ui.NOCHE)]
ALTO_FILA = 26


def _h(v: float) -> str:
    return f"{ui.num(v, 1)} h"


# ------------------------------------------------------------------ horas por grupo
def datos_horas_grupo(form: pd.DataFrame) -> pd.DataFrame:
    """Una fila por grupo: horas promedio por modalidad, lo esperado por el plan a hoy y la brecha. Ordenado del
    grupo más atrasado frente al plan (arriba) al más adelantado."""
    if form.empty:
        return pd.DataFrame()
    g = (form.groupby("grupo")
             .agg(sinc=("horas_sinc_val", "mean"), asinc=("horas_asinc_val", "mean"),
                  total=("horas_validas", "mean"), esperado=("avance_esperado_h", "mean"),
                  personas=("horas_validas", "size"), programa=("perfil", "first"), nivel=("nivel", "first"))
             .reset_index())
    g["esperado"] = pd.to_numeric(g["esperado"], errors="coerce")
    g["brecha"] = g["total"] - g["esperado"]
    # sin plan a hoy (grupo sin iniciar o sin línea base): al final
    g["_orden"] = g["brecha"].fillna(10_000)
    return g.sort_values(["_orden", "grupo"]).drop(columns="_orden").reset_index(drop=True)


def horas_por_grupo(form: pd.DataFrame) -> None:
    g = datos_horas_grupo(form)
    if g.empty:
        st.info("No hay participantes en formación para este filtro.")
        return
    orden = list(g["grupo"])
    detalle = [f"{ui.curso_corto(p) if p else ''} · {n} · {ui.num(k)} personas"
               for p, n, k in zip(g["programa"], g["nivel"], g["personas"])]
    fig = go.Figure()
    fig.add_bar(y=g["grupo"], x=g["sinc"], orientation="h", name=C.ETQ_SINC, marker_color=ui.NOCHE,
                customdata=detalle, hovertemplate="<b>%{y}</b> · %{customdata}<br>" + C.ETQ_SINC
                + ": %{x:.1f} h<extra></extra>")
    fig.add_bar(y=g["grupo"], x=g["asinc"], orientation="h", name=C.ETQ_ASINC, marker_color=ui.CELESTE,
                customdata=detalle, hovertemplate="<b>%{y}</b> · %{customdata}<br>" + C.ETQ_ASINC
                + ": %{x:.1f} h<extra></extra>")
    # Lo que el plan espera a hoy (línea base del curso): una marca por grupo
    con_plan = g[g["esperado"].notna() & (g["esperado"] > 0)]
    alto = max(260, 120 + ALTO_FILA * len(g))
    fig.add_scatter(y=con_plan["grupo"], x=con_plan["esperado"], mode="markers", name="Esperado por el plan a hoy",
                    marker=dict(symbol="line-ns-open", size=18, color=ui.NARANJA, line=dict(width=3)),
                    customdata=con_plan["brecha"],
                    hovertemplate="<b>%{y}</b><br>Esperado a hoy: %{x:.1f} h<br>Diferencia: %{customdata:+.1f} h"
                                  "<extra></extra>")
    # Total al final de cada barra (texto, no color: se lee sin depender de la leyenda)
    # (después de la marca de lo esperado, si está más a la derecha, para que no se monten)
    pos = pd.concat([g["total"], g["esperado"].fillna(0)], axis=1).max(axis=1) + 0.6
    fig.add_scatter(y=g["grupo"], x=pos, mode="text", text=[_h(v) for v in g["total"]],
                    textposition="middle right", textfont=dict(size=12, color=ui.NOCHE), showlegend=False,
                    hoverinfo="skip")
    fig.add_vline(x=C.HORAS_CULMINACION, line_dash="dash", line_color=ui.NOCHE, line_width=1.5)
    fig.add_scatter(x=[C.HORAS_CULMINACION] * 2, y=[orden[0]] * 2, mode="lines", hoverinfo="skip",
                    name=f"Meta para aprobar ({ui.num(C.HORAS_CULMINACION)} h)",
                    line=dict(color=ui.NOCHE, dash="dash", width=1.5))
    tope = max(C.HORAS_CULMINACION, float(g["total"].max()), float(con_plan["esperado"].max() if len(con_plan) else 0))
    ui.dark_layout(fig, alto)
    fig.update_layout(
        barmode="stack", bargap=0.35, separators=",.", hovermode="closest",
        margin=dict(t=88, b=12, l=8, r=12),
        # leyenda sobre las etiquetas del eje superior (46 px más arriba del área de la gráfica)
        legend=dict(orientation="h", yanchor="bottom", y=1.0 + 46 / alto, xanchor="left", x=0, font=dict(size=12),
                    traceorder="normal", bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(side="top", range=[0, tope * 1.14], dtick=10, ticksuffix=" h", title=None, showgrid=True,
                     fixedrange=True)
    fig.update_yaxes(categoryorder="array", categoryarray=orden, range=[len(orden) - 0.5, -0.5], title=None,
                     tickfont=dict(size=12), fixedrange=True, automargin=True)
    tabla = pd.DataFrame({"Grupo": g["grupo"], "Programa": g["programa"].map(ui.curso_corto), "Nivel": g["nivel"],
                          "Personas": g["personas"], C.ETQ_SINC + " (h)": g["sinc"].round(1),
                          C.ETQ_ASINC + " (h)": g["asinc"].round(1), "Horas completadas (h)": g["total"].round(1),
                          "Esperado a hoy (h)": g["esperado"].round(1), "Diferencia (h)": g["brecha"].round(1)})
    ui.grafica_atenea(fig, alto, alto_max=560, tabla=tabla, estilo_base=False)
    st.caption(f"Promedio por persona en formación. Arriba, los grupos más atrasados frente a lo que su plan espera "
               f"a hoy (marca naranja). La línea punteada es la meta de {ui.num(C.HORAS_CULMINACION)} h para aprobar.")


# ------------------------------------------------------------------ avance en los cursos
def _programa_nivel(curso: str) -> tuple[str, str]:
    corto = ui.curso_corto(curso)  # «Básico · Marketing y finanzas»
    partes = [p.strip() for p in corto.split("·")]
    nivel = next((n for n in NIVELES if partes and partes[0].lower().startswith(n.lower()[:5])), "")
    programa = " · ".join(partes[1:]) if nivel and len(partes) > 1 else corto
    return programa, nivel or (partes[0] if partes else "")


def datos_cursos(prog: pd.DataFrame) -> pd.DataFrame:
    """Una fila por curso (programa × nivel) con conteos y % de inscripciones por estado."""
    if prog.empty:
        return pd.DataFrame()
    c = prog.groupby("curso", as_index=False)[["completado", "en_progreso", "sin_iniciar"]].sum()
    c[["programa", "nivel"]] = [list(_programa_nivel(x)) for x in c["curso"]]
    c["inscripciones"] = c[["completado", "en_progreso", "sin_iniciar"]].sum(axis=1)
    for k, *_ in ESTADOS_CURSO:
        c[f"pct_{k}"] = c[k] / c["inscripciones"].where(c["inscripciones"] > 0)
    c["_n"] = c["nivel"].map({n: i for i, n in enumerate(NIVELES)}).fillna(9)
    return c.sort_values(["programa", "_n"]).drop(columns="_n").reset_index(drop=True)


def avance_cursos(prog: pd.DataFrame) -> None:
    c = datos_cursos(prog)
    if c.empty:
        st.info("Sin avance registrado en la plataforma para este filtro.")
        return
    programas = list(dict.fromkeys(c["programa"]))
    filas = [len(c[c["programa"] == p]) for p in programas]
    fig = make_subplots(rows=len(programas), cols=1, shared_xaxes=True, vertical_spacing=0.16 / max(1, len(programas)),
                        subplot_titles=programas, row_heights=filas)
    for i, p in enumerate(programas, start=1):
        d = c[c["programa"] == p]
        etiquetas = [f"{n}<br><span style='font-size:11px'>{ui.num(t)} inscripciones</span>"
                     for n, t in zip(d["nivel"], d["inscripciones"])]
        for k, nombre, color, texto in ESTADOS_CURSO:
            pct = d[f"pct_{k}"].fillna(0)
            fig.add_bar(y=etiquetas, x=pct * 100, orientation="h", name=nombre, marker_color=color,
                        legendgroup=k, showlegend=(i == 1),
                        text=[f"{ui.num(v * 100)} %" if v >= 0.07 else "" for v in pct],
                        textposition="inside", insidetextanchor="middle",
                        textfont=dict(color=texto, size=13), customdata=d[k],
                        hovertemplate=f"<b>{p}</b> · %{{y}}<br>{nombre}: %{{x:.1f}} % (%{{customdata:,}} "
                                      "inscripciones)<extra></extra>", row=i, col=1)
        fig.update_yaxes(autorange="reversed", row=i, col=1)
    alto = 110 + 64 * len(c) + 40 * len(programas)
    ui.dark_layout(fig, alto)
    fig.update_layout(barmode="stack", bargap=0.3, separators=",.", uniformtext=dict(minsize=10, mode="hide"),
                      margin=dict(t=70, b=40, l=8, r=12),
                      legend=dict(orientation="h", yanchor="bottom", y=1.0 + 40 / alto, xanchor="left", x=0,
                                  font=dict(size=12), traceorder="normal"))
    fig.update_annotations(font=dict(size=14, color=ui.NOCHE), xanchor="left", x=0)
    fig.update_xaxes(range=[0, 100.5], tickvals=[0, 25, 50, 75, 100], ticksuffix=" %", fixedrange=True,
                     showgrid=True)
    fig.update_xaxes(title="% de inscripciones al curso", row=len(programas), col=1)
    fig.update_yaxes(fixedrange=True, automargin=True, tickfont=dict(size=13), title=None)
    tabla = pd.DataFrame({"Programa": c["programa"], "Nivel": c["nivel"], "Inscripciones": c["inscripciones"],
                          **{nombre + " (%)": (c[f"pct_{k}"] * 100).round(1) for k, nombre, *_ in ESTADOS_CURSO}})
    ui.grafica_atenea(fig, alto, tabla=tabla, estilo_base=False)
    st.caption("Cada barra suma 100 % de las inscripciones a ese curso en la plataforma. «Completado» es el curso "
               "terminado; el % solo se escribe cuando el tramo es de 7 % o más (el resto, al pasar el cursor o en "
               "«Ver datos»).")


# ------------------------------------------------------------------ participantes por horas completadas
def tramos_horas() -> list[tuple[str, float, float]]:
    """(etiqueta, desde, hasta) en horas completadas. Tramos de 15 h hasta la meta de aprobación (63 h)."""
    meta = C.HORAS_CULMINACION
    return [("Sin horas", -1.0, 0.0), ("Hasta 15 h", 0.0, 15.0), ("15 a 30 h", 15.0, 30.0),
            ("30 a 45 h", 30.0, 45.0), (f"45 a {ui.num(meta)} h", 45.0, meta - 1e-9),
            (f"{ui.num(meta)} h o más", meta - 1e-9, C.HORAS_TOTALES + 1)]


def datos_tramos(form: pd.DataFrame) -> pd.DataFrame:
    """Personas en formación por tramo de horas completadas (cada persona en un solo tramo)."""
    h = pd.to_numeric(form["horas_validas"], errors="coerce").fillna(0)
    filas = []
    for etiqueta, desde, hasta in tramos_horas():
        n = int(((h > desde) & (h <= hasta)).sum())
        filas.append({"tramo": etiqueta, "personas": n})
    t = pd.DataFrame(filas)
    t["pct"] = t["personas"] / max(1, len(h))
    return t


def personas_por_horas(form: pd.DataFrame) -> None:
    t = datos_tramos(form)
    total = int(t["personas"].sum())
    aprobados = int(t["personas"].iloc[-1])
    sin_horas = int(t["personas"].iloc[0])
    meta = ui.num(C.HORAS_CULMINACION)
    st.markdown(f"**{ui.num(aprobados)} de {ui.num(total)} personas** ({ui.pct(aprobados / total if total else None, 1)}) "
                f"ya completaron {meta} h o más y quedan como {C.APROBADO}. "
                f"**{ui.num(sin_horas)}** aún no registran horas completadas.")
    # Un color para quienes aún no llegan a la meta, el de «Aprobado Operador» para los que la superan y celeste
    # para «Sin horas» (el color acompaña a la etiqueta del eje; no es la única forma de distinguirlos).
    colores = [ui.CELESTE] + [ui.AZUL] * (len(t) - 2) + [ui.NOCHE]
    fig = go.Figure(go.Bar(
        x=t["tramo"], y=t["personas"], marker_color=colores,
        text=[f"<b>{ui.num(n)}</b><br>{ui.pct(p, 1)}" for n, p in zip(t["personas"], t["pct"])],
        textposition="outside", textfont=dict(size=13, color=ui.NOCHE), cliponaxis=False,
        customdata=t["pct"],
        hovertemplate="<b>%{x}</b><br>%{y:,} personas (%{customdata:.1%})<extra></extra>"))
    # Separador visual entre «aún no aprueban» y «aprueban»
    fig.add_vline(x=len(t) - 1.5, line_dash="dash", line_color=ui.NOCHE, line_width=1.5)
    fig.add_annotation(x=len(t) - 1.5, y=1.0, yref="paper", yanchor="bottom", xanchor="right", xshift=-6,
                       text="← Aún no alcanzan la meta", showarrow=False, font=dict(size=12, color=ui.NOCHE))
    fig.add_annotation(x=len(t) - 1.5, y=1.0, yref="paper", yanchor="bottom", xanchor="left", xshift=6,
                       text=f"Alcanzan la meta de {meta} h (70 %) →", showarrow=False, font=dict(size=12, color=ui.NOCHE))
    alto = 340
    ui.dark_layout(fig, alto)
    fig.update_layout(separators=",.", bargap=0.28, showlegend=False, margin=dict(t=44, b=10, l=10, r=10))
    fig.update_xaxes(title=dict(text="Horas completadas (de 90 h del curso)", font=dict(size=13)),
                     tickfont=dict(size=13), fixedrange=True, showgrid=False)
    fig.update_yaxes(title=None, showticklabels=False, showgrid=False, range=[0, t["personas"].max() * 1.25 or 1],
                     fixedrange=True)
    tabla = pd.DataFrame({"Horas completadas": t["tramo"], "Personas": t["personas"],
                          "% de personas en formación": (t["pct"] * 100).round(1)})
    ui.grafica_atenea(fig, alto, tabla=tabla, estilo_base=False)
    st.caption(f"Personas en formación (grupo en curso, {C.APROBADO} o {C.NO_APROBADO}) según sus horas completadas: "
               f"{C.ETQ_SINC} (hasta {ui.num(C.HORAS_SINCRONICAS, 1)} h) + {C.ETQ_ASINC} (hasta "
               f"{ui.num(C.HORAS_ASINCRONICAS, 1)} h). Cada persona está en un solo tramo.")
