"""Estilo propio de la vista para Atenea (distinto del tablero interno): navegación superior, banda institucional
azul noche con los filtros, indicadores en bloques de color sólido y metas en tarjetas celestes.
Paleta del Manual de marca Atenea 2026."""
from __future__ import annotations

import html

import streamlit as st

NOCHE, AZUL_PROFUNDO, AZUL, CELESTE, NARANJA = "#141439", "#05247D", "#2051A0", "#B7D9E6", "#E55B0E"
TONOS = {  # fondo, texto, texto secundario
    "noche": (NOCHE, "#FFFFFF", "#B7D9E6"),
    "azul": (AZUL, "#FFFFFF", "#DCEBF3"),
    "profundo": (AZUL_PROFUNDO, "#FFFFFF", "#B7D9E6"),
    "naranja": (NARANJA, "#FFFFFF", "#FFE3D3"),
    "celeste": (CELESTE, NOCHE, "#2A2F5E"),
    "gris": ("#E9EDF3", NOCHE, "#4A4F78"),
}

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@400;500;600;700&display=swap');
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none;}
.block-container {padding-top: 3.2rem; max-width: 1320px;}
h1, h2, h3 {font-family:'Barlow Semi Condensed', sans-serif; color:#141439;}
/* banda institucional (contenedor con key="banda") */
.st-key-banda {background:#141439; border-radius:18px; padding:22px 28px 10px 28px; margin-bottom:8px;}
.st-key-banda label, .st-key-banda p {color:#B7D9E6 !important;}
.st-key-banda button p {color:#141439 !important; font-weight:600;}
.st-key-banda [data-baseweb="select"] > div {background:#05247D; border-color:#2051A0; color:#fff;}
.st-key-banda [data-baseweb="select"] span {color:#fff;}
.banda-eyebrow {font-size:.78rem; font-weight:600; letter-spacing:.14em; text-transform:uppercase; color:#EF6F18;}
.banda-titulo {font-family:'Barlow Semi Condensed', sans-serif; font-size:2.3rem; font-weight:700; color:#fff;
               line-height:1.05; margin:2px 0 4px 0;}
.banda-bajada {color:#B7D9E6; font-size:.95rem;}
.banda-fecha {display:inline-block; background:#05247D; color:#fff; border-radius:20px; padding:4px 12px;
              font-size:.8rem; font-weight:600;}
.pagina-titulo {font-family:'Barlow Semi Condensed', sans-serif; font-size:1.7rem; font-weight:700; color:#141439;
                margin:14px 0 0 0;}
.pagina-bajada {color:#4A4F78; margin-bottom:10px;}
.kpi {border-radius:16px; padding:16px 18px 14px 18px; height:100%;}
.kpi .k-et {font-size:.78rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase;}
.kpi .k-val {font-family:'Barlow Semi Condensed', sans-serif; font-size:2.5rem; font-weight:700; line-height:1.05;
             margin-top:6px;}
.kpi .k-nota {font-size:.85rem; margin-top:4px;}
.meta {background:#EEF6F9; border-radius:16px; padding:16px 18px; height:100%;}
.meta .m-et {font-size:.8rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:#05247D;}
.meta .m-val {font-family:'Barlow Semi Condensed', sans-serif; font-size:2rem; font-weight:700; color:#141439;}
.meta .m-nota {font-size:.85rem; color:#4A4F78;}
.meta .m-barra {height:10px; border-radius:6px; background:#FFFFFF; margin-top:10px; position:relative;}
.meta .m-barra span {display:block; height:10px; border-radius:6px; background:#2051A0;}
.meta .m-barra i {position:absolute; top:-3px; width:3px; height:16px; background:#E55B0E; border-radius:2px;}
.estado {display:inline-block; margin-top:8px; padding:2px 10px; border-radius:12px; font-size:.75rem;
         font-weight:700; background:#141439; color:#fff;}
</style>
"""


def css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def banda_html(fecha: str) -> str:
    return (f"<div style='display:flex;justify-content:space-between;align-items:flex-start;gap:16px'>"
            f"<div><div class='banda-eyebrow'>Informe de seguimiento · Operador Kuepa EduTech</div>"
            f"<div class='banda-titulo'>Talento Capital · Formación 10</div>"
            f"<div class='banda-bajada'>Contrato ATENEA-497-2026 · Formación en Marketing digital y finanzas, y "
            f"Auxiliar de información y servicio al cliente, con enfoque en Inteligencia Artificial</div></div>"
            f"<div class='banda-fecha'>Datos al {html.escape(fecha)}</div></div>")


def pagina(titulo: str, bajada: str = "") -> None:
    st.markdown(f"<div class='pagina-titulo'>{html.escape(titulo)}</div>"
                + (f"<div class='pagina-bajada'>{html.escape(bajada)}</div>" if bajada else ""),
                unsafe_allow_html=True)


def kpi(etiqueta: str, valor: str, nota: str = "", tono: str = "noche") -> None:
    fondo, texto, sec = TONOS.get(tono, TONOS["noche"])
    st.markdown(f"<div class='kpi' style='background:{fondo};color:{texto}'>"
                f"<div class='k-et' style='color:{sec}'>{html.escape(etiqueta)}</div>"
                f"<div class='k-val'>{valor}</div><div class='k-nota' style='color:{sec}'>{nota}</div></div>",
                unsafe_allow_html=True)


def meta(etiqueta: str, valor: str, nota: str, estado: str, avance: float | None, objetivo: float | None) -> None:
    ancho = 0 if avance is None else max(0, min(1, avance)) * 100
    marca = f"<i style='left:{objetivo * 100:.1f}%'></i>" if objetivo else ""
    st.markdown(f"<div class='meta'><div class='m-et'>{html.escape(etiqueta)}</div>"
                f"<div class='m-val'>{valor}</div><div class='m-nota'>{nota}</div>"
                f"<div class='m-barra'><span style='width:{ancho:.1f}%'></span>{marca}</div>"
                f"<div class='estado'>{html.escape(estado)}</div></div>", unsafe_allow_html=True)


def seccion(titulo: str) -> None:
    st.markdown(f"<h3 style='margin:18px 0 6px 0'>{html.escape(titulo)}</h3>", unsafe_allow_html=True)
