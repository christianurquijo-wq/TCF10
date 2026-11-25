"""Estilo propio de la vista para Atenea (distinto del tablero interno): navegación superior, banda institucional
azul noche con los filtros, indicadores en bloques de color sólido y metas en tarjetas celestes.
Paleta del Manual de marca Atenea 2026."""
from __future__ import annotations

import html

import streamlit as st

from tcf10 import ui

NOCHE, AZUL_PROFUNDO, AZUL, CELESTE, NARANJA = "#141439", "#05247D", "#2051A0", "#B7D9E6", "#E55B0E"
TONOS = {  # fondo, texto, texto secundario
    "noche": (NOCHE, "#FFFFFF", "#B7D9E6"),
    "azul": (AZUL, "#FFFFFF", "#DCEBF3"),
    "profundo": (AZUL_PROFUNDO, "#FFFFFF", "#B7D9E6"),
    "naranja": (NARANJA, NOCHE, NOCHE),  # texto blanco sobre naranja = 3,6:1 (no cumple AA); azul noche = 4,9:1
    "celeste": (CELESTE, NOCHE, "#2A2F5E"),
    "gris": ("#E9EDF3", NOCHE, "#4A4F78"),
}

CSS = """
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {display:none;}
/* Accesibilidad (WCAG 2.1 AA, nov-2026) */
:focus-visible {outline: 3px solid #EF6F18 !important; outline-offset: 2px !important;}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {color:#141439 !important;}
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primaryFormSubmit"] p {color:#141439 !important;
    font-weight:600;}
/* Las tablas no se descargan desde su barra: la única descarga es el Excel con marca de agua y registro */
button[aria-label^="Download as CSV"], [data-testid="stElementToolbarButton"]:has(button[aria-label^="Download"]) {
    display:none !important;}
.pie-legal {border-top:1px solid #D3E7EF; margin-top:28px; padding-top:10px; color:#4A4F78; font-size:.85rem;}
.pie-legal a {color:#2051A0;}
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
.banda-interna {background:#E55B0E; color:#141439; border-radius:6px; padding:2px 8px; margin-right:6px;
                letter-spacing:.08em;}
.banda-lado {display:flex; flex-direction:column; align-items:flex-end; gap:10px; flex-shrink:0;}
@media (max-width: 640px) {.banda-lado {flex-direction:row; align-items:center; flex-wrap:wrap;}}
.banda-fecha {display:inline-block; background:#05247D; color:#fff; border-radius:20px; padding:4px 12px;
              font-size:.8rem; font-weight:600;}
.pagina-titulo {font-family:'Barlow Semi Condensed', sans-serif; font-size:1.7rem; font-weight:700; color:#141439;
                margin:14px 0 0 0;}
.pagina-bajada {color:#4A4F78; margin-bottom:10px;}
/* Tarjetas de tamaño fijo: mismo alto siempre, textos largos se recortan a 2 líneas */
.kpi {border-radius:16px; padding:16px 18px 14px 18px; height:152px; display:flex; flex-direction:column;
      overflow:hidden; box-sizing:border-box;}
.kpi .k-et {font-size:.78rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase; white-space:nowrap;
            overflow:hidden; text-overflow:ellipsis;}
.kpi .k-val {font-family:'Barlow Semi Condensed', sans-serif; font-size:clamp(1.7rem, 2.3vw, 2.5rem); font-weight:700;
             line-height:1.1; margin-top:6px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
.kpi .k-nota, .meta .m-nota {font-size:.85rem; margin-top:4px; display:-webkit-box; -webkit-line-clamp:2;
             -webkit-box-orient:vertical; overflow:hidden;}
.meta {background:#EEF6F9; border-radius:16px; padding:16px 18px; height:212px; display:flex; flex-direction:column;
       overflow:hidden; box-sizing:border-box;}
.meta .m-pie {margin-top:auto;}
.meta .m-et {font-size:.8rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:#05247D;}
.meta .m-val {font-family:'Barlow Semi Condensed', sans-serif; font-size:2rem; font-weight:700; color:#141439;}
.meta .m-nota {color:#4A4F78;}
.meta .m-barra {height:10px; border-radius:6px; background:#FFFFFF; margin-top:10px; position:relative;}
.meta .m-barra span {display:block; height:10px; border-radius:6px; background:#2051A0;}
.meta .m-barra i {position:absolute; top:-3px; width:3px; height:16px; background:#E55B0E; border-radius:2px;}
.estado {display:inline-block; margin-top:8px; padding:2px 10px; border-radius:12px; font-size:.75rem;
         font-weight:700; background:#141439; color:#fff;}
.ficha-cab {background:#EEF6F9; border-radius:16px; padding:18px 22px; margin:6px 0 12px 0;}
.ficha-nombre {font-family:'Barlow Semi Condensed', sans-serif; font-size:1.9rem; font-weight:700; color:#141439;
               line-height:1.1;}
.ficha-datos {color:#4A4F78; margin-top:4px;}
.chip {display:inline-block; padding:3px 12px; border-radius:14px; font-size:.8rem; font-weight:700; color:#fff;
       margin:8px 6px 0 0;}
/* Responsive: filas de tarjetas y filtros se reacomodan (escritorio 4-5, tablet 2, celular 1 por fila) */
[class*="st-key-fila"] [data-testid="stHorizontalBlock"], .st-key-banda [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap; row-gap: 1rem;}
[class*="st-key-fila"] [data-testid="stColumn"] {flex: 1 1 180px; min-width: 180px;}
.st-key-banda [data-testid="stColumn"] {flex: 1 1 200px; min-width: 200px;}
@media (max-width: 1100px) {
  .st-key-banda [data-testid="stColumn"] {flex: 1 1 calc(50% - 1rem); min-width: calc(50% - 1rem);}
}
@media (max-width: 900px) {
  .block-container {padding-left: 1rem; padding-right: 1rem;}
  .st-key-banda {padding: 18px 16px 8px 16px;}
  .banda-titulo {font-size: 1.7rem;}
  .banda-bajada {display: none;}
  .pagina-titulo {font-size: 1.4rem;}
}
@media (max-width: 640px) {
  [class*="st-key-fila"] [data-testid="stColumn"], .st-key-banda [data-testid="stColumn"] {flex: 1 1 100%; min-width: 100%;}
  .kpi {height: 128px;} .meta {height: 196px;}
  .ficha-nombre {font-size: 1.5rem;}
}
</style>
"""


def css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def banda_html(fecha: str, interna: bool = False) -> str:
    ceja = ("<span class='banda-interna'>Vista interna</span> Gestión del contrato · Kuepa EduTech" if interna
            else "Informe de seguimiento · Operador Kuepa EduTech")
    return (f"<div style='display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap'>"
            f"<div><div class='banda-eyebrow'>{ceja}</div>"
            f"<div class='banda-titulo'>Talento Capital · Formación 10</div>"
            f"<div class='banda-bajada'>Contrato ATENEA-497-2026 · Formación en Marketing digital y finanzas, y "
            f"Auxiliar de información y servicio al cliente, con enfoque en Inteligencia Artificial</div></div>"
            f"<div class='banda-lado'>{ui.chip_kuepa()}<div class='banda-fecha'>Datos al {html.escape(fecha)}</div>"
            f"</div></div>")


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
                f"<div class='m-pie'><div class='m-barra'><span style='width:{ancho:.1f}%'></span>{marca}</div>"
                f"<div class='estado'>{html.escape(estado)}</div></div></div>", unsafe_allow_html=True)


def seccion(titulo: str) -> None:
    st.markdown(f"<h3 style='margin:18px 0 6px 0'>{html.escape(titulo)}</h3>", unsafe_allow_html=True)


def fila(n: int, clave: str):
    """Fila de tarjetas responsive (se reacomoda en tablet y celular). Devuelve las columnas."""
    return st.container(key=f"fila_{clave}").columns(n)
