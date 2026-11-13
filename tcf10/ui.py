"""Componentes visuales compartidos (marca Kuepa, tarjetas, formato colombiano)."""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from tcf10 import config as C
from tcf10 import data, metrics

NARANJA, AZUL, VERDE, AMARILLO, ROJO, GRIS = "#FD531E", "#1F4E9C", "#1A9E86", "#E58A00", "#D64541", "#8C8C8C"
COLOR_RIESGO = {"Alto": ROJO, "Medio": AMARILLO, "Bajo": VERDE, "Culminó": AZUL, "Retirado": GRIS,
                "No culminó": "#5A5A5A", "Sin iniciar": "#BDBDBD", "Sin enrolar": "#D9D9D9"}
ORDEN_RIESGO = ["Culminó", "Bajo", "Medio", "Alto", "No culminó", "Retirado", "Sin iniciar", "Sin enrolar"]
COLOR_ESTADO = {"Cumplido": VERDE, "En curso": AZUL, "No cumplido": ROJO, "Sin datos": GRIS}
TZ = timezone(timedelta(hours=-5))
HOY_DEMO = pd.Timestamp("2026-11-13")  # fecha con la que se generaron los datos de demostración

CSS = """
<style>
.block-container {padding-top: 2rem;}
.tarjeta {border:1px solid rgba(128,128,128,.25); border-radius:12px; padding:14px 16px; height:100%;}
.tarjeta h4 {margin:0 0 4px 0; font-size:.95rem;}
.valor {font-size:1.9rem; font-weight:700; line-height:1.15;}
.sub {font-size:.82rem; opacity:.75;}
.pill {display:inline-block; padding:2px 10px; border-radius:10px; font-size:.72rem; font-weight:700; color:#fff;}
.barra {height:8px; border-radius:4px; background:rgba(128,128,128,.2); margin:8px 0 4px 0; position:relative;}
.barra > span {display:block; height:8px; border-radius:4px;}
.barra > i {position:absolute; top:-3px; width:2px; height:14px; background:#333;}
</style>
"""


def inicio(titulo: str, subtitulo: str = "") -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.title(titulo)
    if subtitulo:
        st.caption(subtitulo)


def num(x, dec: int = 0) -> str:
    if x is None or pd.isna(x):
        return "–"
    s = f"{x:,.{dec}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def pct(x, dec: int = 0) -> str:
    return "–" if x is None or pd.isna(x) else num(x * 100, dec) + " %"


def plata(x) -> str:
    """$1.059 M / $3.239 M (millones de pesos)."""
    return "–" if x is None or pd.isna(x) else "$" + num(x / 1e6, 0) + " M"


def pill(texto: str, color: str) -> str:
    return f"<span class='pill' style='background:{color}'>{html.escape(texto)}</span>"


def tarjeta(titulo: str, valor: str, sub: str = "", color: str = AZUL, extra: str = "") -> None:
    st.markdown(f"<div class='tarjeta'><h4>{html.escape(titulo)}</h4>"
                f"<div class='valor' style='color:{color}'>{valor}</div>"
                f"<div class='sub'>{sub}</div>{extra}</div>", unsafe_allow_html=True)


def barra(avance: float | None, meta: float | None, color: str) -> str:
    ancho = 0 if avance is None or pd.isna(avance) else max(0, min(1, avance)) * 100
    marca = f"<i style='left:{meta * 100:.1f}%'></i>" if meta else ""
    return f"<div class='barra'><span style='width:{ancho:.1f}%;background:{color}'></span>{marca}</div>"


def iniciales(nombre: str) -> str:
    """La app es pública: nunca se muestra el nombre completo ni el documento."""
    partes = [p for p in str(nombre or "").split() if p.isalpha()]
    return "".join(p[0].upper() + "." for p in partes[:4]) or "–"


@st.cache_data(ttl=900, show_spinner=False)
def _preparado(hoy: pd.Timestamp) -> tuple[pd.DataFrame, bool]:
    benef, avance, cohortes, demo = data.cargar()
    return metrics.preparar(benef, avance, cohortes, hoy), demo


def datos() -> pd.DataFrame:
    """Datos listos para las páginas + banner si es demostración."""
    hoy = HOY_DEMO if data.modo_demo() else pd.Timestamp(datetime.now(TZ).date())
    df, demo = _preparado(hoy)
    if demo:
        st.info("**Datos de demostración** (sintéticos). Configura `[tcf10]` y `[gcp_service_account]` en los "
                "Secrets para ver los datos reales.", icon=":material/science:")
    st.caption(f"Corte: {hoy:%d/%m/%Y}")
    return df


def refrescar() -> None:
    data.refrescar()
    _preparado.clear()


def filtros(df: pd.DataFrame, clave: str, columnas=("cohorte", "perfil", "nivel")) -> pd.DataFrame:
    cols = st.columns(len(columnas))
    etiquetas = {"cohorte": "Cohorte", "perfil": "Perfil", "nivel": "Nivel", "docente": "Docente",
                 "grupo": "Grupo", "riesgo": "Riesgo", "poblacion": "Población"}
    for col, c in zip(cols, columnas):
        opciones = sorted(df[c].dropna().astype(str).unique())
        elegido = col.multiselect(etiquetas.get(c, c), opciones, key=f"{clave}_{c}", placeholder="Todos")
        if elegido:
            df = df[df[c].astype(str).isin(elegido)]
    return df


def dark_layout(fig, height: int = 340):
    fig.update_layout(height=height, margin=dict(t=40, b=10, l=10, r=10), legend_title_text="",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def fecha_corta(d) -> str:
    return "–" if d is None or pd.isna(d) else pd.Timestamp(d).strftime("%d/%m/%Y")


__all__ = ["C"]
