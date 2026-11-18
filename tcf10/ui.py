"""Componentes visuales compartidos: identidad de la Agencia Atenea (Manual de marca 2026), tarjetas y
formato colombiano. La paleta sale del manual; rojo y verde solo para semáforos (Alcaldía permite el rojo
de la marca Bogotá como recurso puntual)."""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from tcf10 import config as C
from tcf10 import data, metrics

# Manual de marca Atenea 2026 · esquema cromático
NOCHE, AZUL_PROFUNDO, AZUL, CELESTE, NARANJA_CLARO, NARANJA = (
    "#141439", "#05247D", "#2051A0", "#B7D9E6", "#EF6F18", "#E55B0E")
VERDE, AMARILLO, ROJO, GRIS = "#2E8B57", "#EF6F18", "#C8102E", "#8A8FA8"  # semáforos
COLOR_RIESGO = {"Alto": ROJO, "Medio": NARANJA_CLARO, "Bajo": AZUL, "Culminó": NOCHE, "Retirado": GRIS,
                "No culminó": "#5B5F7A", "Sin iniciar": CELESTE, "Sin enrolar": "#DCE3EA"}
ORDEN_RIESGO = ["Culminó", "Bajo", "Medio", "Alto", "No culminó", "Retirado", "Sin iniciar", "Sin enrolar"]
COLOR_ESTADO = {"Cumplido": VERDE, "En curso": AZUL, "No cumplido": ROJO, "Sin datos": GRIS}
TZ = timezone(timedelta(hours=-5))
HOY_DEMO = pd.Timestamp("2026-11-13")  # fecha con la que se generaron los datos de demostración

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@400;500;600;700&display=swap');
.block-container {padding-top: 1.6rem;}
h1, h2, h3 {font-family: 'Barlow Semi Condensed', sans-serif; color: #141439; letter-spacing: -.01em;}
h1 {font-weight: 700;}
h2, h3 {font-weight: 600;}
.cabecera {display:flex; align-items:center; justify-content:space-between; gap:16px;
           border-bottom: 2px solid #B7D9E6; padding-bottom: 10px; margin-bottom: 6px;}
.cabecera .eyebrow {font-size:.8rem; font-weight:600; letter-spacing:.12em; text-transform:uppercase; color:#E55B0E;}
.cabecera h1 {margin:0; padding:0; font-size:2.1rem; line-height:1.1;}
.cabecera .bajada {color:#3C4170; font-size:.95rem; margin-top:4px;}
.cabecera img {height:52px;}
.cabecera .marcas {display:flex; align-items:center; gap:14px; flex-wrap:wrap; justify-content:flex-end;}
.cabecera .marcas .sep {width:1px; height:40px; background:#B7D9E6;}
.cabecera .marcas img.kuepa {height:34px;}
.tarjeta {background:#FFFFFF; border:1px solid #D3E7EF; border-radius:12px; padding:14px 16px; height:100%;
          box-shadow: 0 1px 3px rgba(20,20,57,.06);}
.tarjeta h4 {margin:0 0 4px 0; font-size:.8rem; font-weight:600; letter-spacing:.06em; text-transform:uppercase;
             color:#3C4170;}
.valor {font-family:'Barlow Semi Condensed', sans-serif; font-size:2.1rem; font-weight:700; line-height:1.1;}
.sub {font-size:.85rem; color:#4A4F78;}
.pill {display:inline-block; padding:2px 10px; border-radius:10px; font-size:.72rem; font-weight:700; color:#fff;}
.barra {height:8px; border-radius:4px; background:#EEF6F9; margin:8px 0 4px 0; position:relative;}
.barra > span {display:block; height:8px; border-radius:4px;}
.barra > i {position:absolute; top:-3px; width:2px; height:14px; background:#141439;}
[data-testid="stCaptionContainer"] {color:#4A4F78;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"], [data-testid="stSidebar"] small {color:#B7D9E6 !important;}
</style>
"""
def _logo(blanco: bool = False) -> str:
    """Logo horizontal de Atenea embebido (data URI) para la cabecera."""
    import base64
    from pathlib import Path
    ruta = Path(__file__).resolve().parent.parent / "assets" / (
        "atenea_horizontal_blanco.png" if blanco else "atenea_horizontal.png")
    return "data:image/png;base64," + base64.b64encode(ruta.read_bytes()).decode() if ruta.exists() else ""


KUEPA_URL = "https://storage.googleapis.com/ket-bucket/bucket/U0378MDRBDW/HE/36b6f0e6d0418eb184abea7bef55a989.png"


def logo_kuepa() -> str:
    """Logo de Kuepa: assets/kuepa.png si existe (recomendado); si no, la URL pública del bucket."""
    import base64
    from pathlib import Path
    ruta = Path(__file__).resolve().parent.parent / "assets" / "kuepa.png"
    return "data:image/png;base64," + base64.b64encode(ruta.read_bytes()).decode() if ruta.exists() else KUEPA_URL


def chip_kuepa(texto: str = "Operado por") -> str:
    """Sello blanco «Operado por Kuepa»: se lee bien sobre fondos oscuros sin depender de los colores del logo."""
    return ("<span style='display:inline-flex;align-items:center;gap:8px;background:#FFFFFF;border-radius:10px;"
            "padding:6px 12px;font-size:.68rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;"
            f"color:#3C4170;white-space:nowrap'>{html.escape(texto)}"
            f"<img src='{logo_kuepa()}' alt='Kuepa EduTech' style='height:22px;display:block'></span>")


def inicio(titulo: str, subtitulo: str = "") -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    logo = _logo()
    st.markdown(
        f"<div class='cabecera'><div><div class='eyebrow'>Talento Capital · Formación 10</div>"
        f"<h1>{html.escape(titulo)}</h1>"
        + (f"<div class='bajada'>{html.escape(subtitulo)}</div>" if subtitulo else "")
        + "</div><div class='marcas'>" + (f"<img src='{logo}' alt='Agencia Atenea'><span class='sep'></span>" if logo else "")
        + f"<img class='kuepa' src='{logo_kuepa()}' alt='Kuepa EduTech'></div></div>",
        unsafe_allow_html=True)


def acceso_restringido(seccion: str = "tcf10", dominios_def=("kuepa.com",)) -> str:
    """Páginas con datos por persona: exigen sesión de Google con un correo autorizado.
    Secrets: [auth] (Google OIDC, igual que el dashboard EFE) y en [tcf10] consulta_correos / consulta_dominios.
    En modo demo no se pide (los datos son sintéticos)."""
    if data.modo_demo():
        return ""
    # Modo pruebas: `sin_login = true` en [tcf10] (consulta interna) o en [atenea] (vista Atenea) apaga el
    # inicio de sesión SIN tocar el código. Mientras esté activo, cualquiera con el enlace ve nombres/documentos.
    try:
        sec = dict(st.secrets.get(seccion, {}))
    except Exception:  # noqa: BLE001
        sec = {}
    if str(sec.get("sin_login", "")).lower() in ("true", "1", "si", "sí"):
        st.warning("**Modo pruebas:** inicio de sesión desactivado. Quita `sin_login` de los Secrets antes de "
                   "compartir el enlace.", icon=":material/lock_open:")
        return ""
    try:
        hay_auth = "auth" in st.secrets
    except Exception:  # noqa: BLE001
        hay_auth = False
    if not hay_auth:
        st.warning("Esta consulta muestra el estado de cada participante y solo funciona con inicio de sesión. "
                   "Falta configurar `[auth]` en los Secrets.", icon=":material/lock:")
        st.stop()
    if not st.user.is_logged_in:
        st.info("Inicia sesión con tu cuenta de Google autorizada para consultar participantes.",
                icon=":material/lock:")
        # Admite [auth] plano o con proveedor nombrado ([auth.google]); con el plano, st.login() va sin argumento.
        auth = st.secrets["auth"]
        proveedor = next((k for k in auth.keys() if isinstance(auth[k], dict) or hasattr(auth[k], "keys")), None)
        st.button("Iniciar sesión con Google", on_click=st.login, args=(proveedor,) if proveedor else (),
                  type="primary")
        st.stop()
    correo = str(st.user.get("email", "")).lower()
    cfg = data._cfg()
    if seccion != "tcf10":
        try:
            cfg = dict(st.secrets.get(seccion, {}))
        except Exception:  # noqa: BLE001
            cfg = {}
    correos = {c.strip().lower() for c in cfg.get("consulta_correos", cfg.get("correos", []))}
    dominios = {d.strip().lower().lstrip("@")
                for d in cfg.get("consulta_dominios", cfg.get("dominios", list(dominios_def)))}
    if correo not in correos and correo.split("@")[-1] not in dominios:
        st.error(f"La cuenta {correo} no está autorizada para esta consulta. Solicita acceso al equipo de Kuepa.",
                 icon=":material/block:")
        st.button("Cerrar sesión", on_click=st.logout)
        st.stop()
    return correo


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


def curso_corto(nombre: str) -> str:
    """«Nivel Básico - Auxiliar de información y Servicio al cliente con enfoque en IA» → «Básico · Auxiliar»."""
    import re as _re
    t = _re.sub(r"\s*con enfoque en Inteligencia Artificial", "", str(nombre or ""), flags=_re.I)
    t = t.replace("Auxiliar de información y Servicio al cliente", "Auxiliar y servicio al cliente")
    t = t.replace("Marketing digital y finanzas", "Marketing y finanzas")
    return _re.sub(r"^Nivel\s+", "", t).replace(" - ", " · ")


def iniciales(nombre: str) -> str:
    """La app es pública: nunca se muestra el nombre completo ni el documento."""
    partes = re.findall(r"[^\W\d_]+", str(nombre or ""))  # sirve con nombre completo o con «J.P.» del SIS
    return "".join(p[0].upper() + "." for p in partes[:4]) or "–"


@st.cache_data(ttl=900, show_spinner=False)
def _preparado(hoy: pd.Timestamp) -> tuple[pd.DataFrame, bool]:
    benef, avance, cohortes, demo = data.cargar()
    return metrics.preparar(benef, avance, cohortes, hoy), demo


def datos() -> pd.DataFrame:
    """Datos listos para las páginas + banner si es demostración."""
    hoy = HOY_DEMO if data.modo_demo() else pd.Timestamp(datetime.now(TZ).date())
    try:
        df, demo = _preparado(hoy)
    except data.ErrorConfiguracion as e:
        st.error(str(e), icon=":material/error:")
        st.stop()
    if demo:
        st.info("**Datos de demostración** (sintéticos). Configura `[tcf10]` y `[gcp_service_account]` en los "
                "Secrets para ver los datos reales.", icon=":material/science:")
    elif data.modo() == "sis":
        st.info("**Datos del SIS.** Mientras no esté la base de Atenea, las cohortes se arman con las fechas de "
                "inicio de los grupos y no se muestran docente, gestor, franja, población, certificación ni PILA.",
                icon=":material/database:")
    sis = pd.to_datetime(df.get("actualizado_sis"), errors="coerce").max() if "actualizado_sis" in df else pd.NaT
    st.caption(f"Corte: {hoy:%d/%m/%Y}" + ("" if pd.isna(sis) else f" · SIS actualizado: {sis:%d/%m/%Y %H:%M}"))
    return df


def refrescar() -> None:
    data.refrescar()
    _preparado.clear()


def filtros(df: pd.DataFrame, clave: str, columnas=("cohorte", "perfil", "nivel")) -> pd.DataFrame:
    cols = st.columns(len(columnas))
    etiquetas = {"cohorte": "Cohorte", "perfil": "Perfil", "nivel": "Nivel", "docente": "Docente",
                 "grupo": "Grupo", "riesgo": "Riesgo", "poblacion": "Población", "franja": "Franja"}
    for col, c in zip(cols, columnas):
        opciones = sorted(df[c].dropna().astype(str).unique())
        elegido = col.multiselect(etiquetas.get(c, c), opciones, key=f"{clave}_{c}", placeholder="Todos")
        if elegido:
            df = df[df[c].astype(str).isin(elegido)]
    return df


def dark_layout(fig, height: int = 340):
    """Estilo de gráfica Atenea (el nombre se conserva para no tocar las páginas)."""
    fig.update_layout(height=height, margin=dict(t=40, b=10, l=10, r=10), legend_title_text="",
                      template="plotly_white", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Barlow Semi Condensed, Arial, sans-serif", size=13, color=NOCHE),
                      hoverlabel=dict(font_family="Barlow Semi Condensed, Arial, sans-serif"))
    fig.update_xaxes(gridcolor="#E3EEF3", linecolor="#B7D9E6", zerolinecolor="#B7D9E6")
    fig.update_yaxes(gridcolor="#E3EEF3", linecolor="#B7D9E6", zerolinecolor="#B7D9E6")
    return fig


def fecha_corta(d) -> str:
    return "–" if d is None or pd.isna(d) else pd.Timestamp(d).strftime("%d/%m/%Y")


__all__ = ["C"]
