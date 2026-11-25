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
/* Vista interna: tarjetas y pestañas que se adaptan a pantallas pequeñas */
@media (max-width: 760px) {
  .block-container {padding-left: .8rem; padding-right: .8rem;}
  .cabecera {flex-direction: column; align-items: flex-start;}
  .cabecera h1 {font-size: 1.6rem;}
  .cabecera img {height: 38px;}
  .valor {font-size: 1.6rem !important;}
  .tarjeta {padding: 10px 12px;}
  .tarjeta h4 {font-size: .7rem;}
  .sub {font-size: .78rem;}
  /* tarjetas y filtros de dos en dos en el celular (Streamlit los apila de a uno) */
  div[data-testid="stHorizontalBlock"]:has(.tarjeta), .st-key-barra_filtros div[data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important; gap: .5rem !important;}
  div[data-testid="stHorizontalBlock"]:has(.tarjeta) > div[data-testid="stColumn"],
  .st-key-barra_filtros div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
    flex: 1 1 calc(50% - .5rem) !important; min-width: calc(50% - .5rem) !important; width: calc(50% - .5rem) !important;}
  .st-key-barra_filtros [data-testid="stCaptionContainer"] {display: none;}
}
[data-testid="stTabs"] button p {font-size: 1rem; font-weight: 600;}
.tarjeta {margin-bottom: 8px;}
h1, h2, h3 {font-family: 'Barlow Semi Condensed', sans-serif; color: #141439; letter-spacing: -.01em;}
h1 {font-weight: 700;}
h2, h3 {font-weight: 600;}
.cabecera {display:flex; align-items:center; justify-content:space-between; gap:16px;
           border-bottom: 2px solid #B7D9E6; padding-bottom: 10px; margin-bottom: 6px;}
.cabecera.compacta {border-bottom: 1px solid #D3E7EF; padding-bottom: 6px;}
.cabecera.compacta h1 {font-size: 1.7rem;}
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
    if st.session_state.get("vista") == "interna":  # la banda superior ya lleva marca y logos: encabezado compacto
        st.markdown(f"<div class='cabecera compacta'><div><h1>{html.escape(titulo)}</h1>"
                    + (f"<div class='bajada'>{html.escape(subtitulo)}</div>" if subtitulo else "") + "</div></div>",
                    unsafe_allow_html=True)
        return
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
    # App unificada: quien entró a la vista interna ya pasó el control de acceso (correo en [atenea] internos).
    if st.session_state.get("vista") == "interna" and st.session_state.get("interno_ok"):
        return st.session_state.get("interno_correo", "")
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


@st.cache_data(ttl=data.TTL, show_spinner="Cargando datos…")
def _preparado(hoy: pd.Timestamp, version: str = "") -> tuple[pd.DataFrame, bool]:  # version: solo llave del caché
    benef, avance, cohortes, demo = data.cargar()
    df = metrics.preparar(benef, avance, cohortes, hoy)
    try:  # seguimiento de Feedbacks (vista interna); si la fuente no los trae, la página lo avisa
        ids = tuple(sorted(int(x) for x in df["id_sis"].dropna().unique() if int(x) > 0))
        asis, _ = data.agregados(ids)
        df = metrics.feedback(df, data.feedbacks(), asis, hoy)
    except Exception as e:  # noqa: BLE001 -- los Feedbacks nunca deben tumbar el resto del tablero
        df.attrs["feedback_error"] = f"{type(e).__name__}: {e}"
    return df, demo


def datos() -> pd.DataFrame:
    """Datos listos para las páginas + banner si es demostración."""
    hoy = HOY_DEMO if data.modo_demo() else pd.Timestamp(datetime.now(TZ).date())
    try:
        df, demo = _preparado(hoy, getattr(metrics, "VERSION", ""))
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
    try:
        from vista_atenea import comun
        comun._todos.clear()
    except Exception:  # noqa: BLE001
        pass


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


# ------------------------------------------------------------------ vista interna: estilo de gráficas
CONFIG_GRAFICA = {"displayModeBar": False, "responsive": True}  # sin barra de herramientas: solo clic y hover


def estilo(fig, height: int = 340, leyenda: bool | None = None):
    """Usar con st.plotly_chart(..., theme=None, config=CONFIG_GRAFICA) o con ui.mostrar(): el tema de Streamlit
    reescribe márgenes y leyendas.
    Estilo de la vista interna: leyenda arriba en una línea (no tapa los datos), márgenes automáticos para que
    las etiquetas largas no se corten, textos que se ocultan si no caben y sin zoom accidental (ejes fijos)."""
    dark_layout(fig, height)
    con_leyenda = (sum(1 for t in fig.data if t.showlegend is not False and t.name) > 1) if leyenda is None \
        else leyenda
    fig.update_layout(
        margin=dict(t=46 if con_leyenda else 16, b=8, l=8, r=16), font=dict(size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0, font=dict(size=12),
                    bgcolor="rgba(0,0,0,0)", entrywidth=0, itemwidth=30, tracegroupgap=0),
        showlegend=con_leyenda, uniformtext=dict(minsize=10, mode="hide"), hovermode="closest")
    fig.update_xaxes(automargin=True, fixedrange=True, title_standoff=8)
    fig.update_yaxes(automargin=True, fixedrange=True, title_standoff=8)
    fig.update_traces(selector=dict(type="bar"), cliponaxis=False)
    return fig


def mostrar(fig, height: int = 340, leyenda: bool | None = None, alto_max: int | None = 520) -> None:
    """Gráfica de solo lectura con el estilo de la vista interna (con scroll si es más alta que alto_max)."""
    fig = estilo(fig, height, leyenda)
    caja = st.container(height=alto_max) if alto_max and height > alto_max else st.container()
    with caja:
        st.plotly_chart(fig, width="stretch", config=CONFIG_GRAFICA, theme=None)


def linea_meta(fig, valor: float, texto: str, eje: str = "x", color: str = NOCHE) -> None:
    """Línea de meta punteada con su texto en la leyenda (no encima de las barras)."""
    if valor is None or pd.isna(valor):
        return
    if eje == "x":
        fig.add_vline(x=valor, line_dash="dash", line_color=color, line_width=2)
    else:
        fig.add_hline(y=valor, line_dash="dash", line_color=color, line_width=2)
    # Traza solo para la leyenda: un punto sobre un dato que ya existe (con None Plotly crea una categoría vacía).
    def primero(eje_ref: str):
        for t in fig.data:
            v = getattr(t, eje_ref)
            if v is not None and len(v):
                return [list(v)[0]]
        return [0]
    x0, y0 = ([valor], primero("y")) if eje == "x" else (primero("x"), [valor])
    fig.add_scatter(x=x0, y=y0, mode="lines", name=texto, line=dict(color=color, dash="dash", width=2),
                    hoverinfo="skip")


def rango_categorias(categorias) -> list[float]:
    """Rango del eje de categorías sin espacio vacío (Plotly agrega relleno si hay marcadores o textos)."""
    return [-.6, pd.Series(list(categorias)).nunique() - .4]


def alto_barras(n: int, por_barra: int = 26, minimo: int = 220) -> int:
    """Alto de una gráfica de barras horizontales para que cada barra se lea (la caja hace scroll si es larga)."""
    return max(minimo, 70 + por_barra * int(n))


def pestanas(nombres: list[str], clave: str):
    """Pestañas que recuerdan cuál estaba abierta (al filtrar con clic no vuelve a la primera)."""
    try:
        return st.tabs(nombres, key=f"tab_{clave}", on_change="rerun")
    except TypeError:  # Streamlit anterior a las pestañas con estado
        return st.tabs(nombres)


# ------------------------------------------------------------------ vista interna: barra única de filtros
ETIQUETAS_BARRA = {"cohorte": "Cohorte", "grupo": "Grupo", "franja": "Jornada", "docente": "Docente",
                   "perfil": "Programa", "nivel": "Nivel"}


def _limpiar_todo(pagina: str, columnas: tuple) -> None:
    for c in columnas:
        st.session_state[f"bf_{c}"] = []
        st.session_state[f"bfv_{c}"] = []
    st.session_state["bf_doc"] = ""
    st.session_state["bfv_doc"] = ""
    st.session_state[_clave_filtros(pagina)] = {}


def _por_documento(df: pd.DataFrame, texto: str) -> pd.DataFrame:
    import re
    digitos = re.sub(r"\D", "", texto)
    if not digitos:
        return df
    from vista_atenea import comun
    llaves = [c for c in ("id_sis", "huella") if c in df]
    ident = comun.con_identidad(df[llaves].reset_index(drop=True))
    docs = ident["documento"].astype("string").fillna("").str.replace(r"\D", "", regex=True)
    return df[docs.str.contains(digitos, regex=False).to_numpy()]


def barra_filtros(df: pd.DataFrame, pagina: str, columnas=("cohorte", "perfil", "nivel", "grupo", "franja"),
                  documento: bool = True) -> pd.DataFrame:
    """Una sola barra de filtros por página de la vista interna. Lo elegido se conserva al cambiar de página;
    los clics en las gráficas aparecen aquí mismo y se quitan con «Limpiar filtros»."""
    columnas = tuple(c for c in columnas if c in df)
    with st.container(border=True, key="barra_filtros"):
        cols = st.columns(len(columnas) + (1 if documento else 0))
        for col, c in zip(cols, columnas):
            opciones = sorted(df[c].dropna().astype(str).unique(), key=C.orden_franja if c == "franja" else
                              (lambda n: ((["Básico", "Intermedio", "Avanzado"] + [n]).index(n), n)) if c == "nivel" else None)
            k = f"bf_{c}"
            guardado = st.session_state.get(k, st.session_state.get(f"bfv_{c}", []))
            st.session_state[k] = [v for v in (guardado or []) if v in opciones]
            elegido = col.multiselect(ETIQUETAS_BARRA.get(c, c), opciones, key=k, placeholder="Todos")
            st.session_state[f"bfv_{c}"] = elegido
            if elegido:
                df = df[df[c].astype(str).isin(elegido)]
        if documento:
            st.session_state["bf_doc"] = st.session_state.get("bf_doc", st.session_state.get("bfv_doc", ""))
            texto = cols[-1].text_input("Documento", key="bf_doc", placeholder="Buscar por número",
                                        icon=":material/search:")
            st.session_state["bfv_doc"] = texto
            df = _por_documento(df, texto)
        clics = st.session_state.get(_clave_filtros(pagina), {})
        activos = any(st.session_state.get(f"bfv_{c}") for c in columnas) or bool(st.session_state.get("bfv_doc"))
        if clics or activos:
            a, b = st.columns([4, 1], vertical_alignment="center")
            if clics:
                a.markdown(":material/touch_app: **Desde las gráficas:** " + " · ".join(
                    f"{ETIQUETAS_FILTRO.get(c, c)}: {', '.join(v)}" for c, v in clics.items()))
            else:
                a.caption(f"{num(len(df))} estudiantes con estos filtros.")
            b.button("Limpiar filtros", icon=":material/filter_alt_off:", on_click=_limpiar_todo,
                     args=(pagina, columnas), key=f"bf_limpiar_{pagina}", width="stretch")
        else:
            st.caption(":material/touch_app: Toca una barra o un punto de cualquier gráfica para filtrar; "
                       "tócalo de nuevo para quitar ese filtro.")
    return aplicar_clic(df, pagina)


# ------------------------------------------------------------------ gráficas que filtran (vista interna)
ETIQUETAS_FILTRO = {"grupo": "Grupo", "riesgo": "Riesgo", "cohorte": "Cohorte", "tipo_ruta": "Ruta al 70 %",
                    "curso": "Curso", "periodo": "Fecha", "docente": "Docente", "franja": "Franja",
                    "feedbacks_hechos": "Feedbacks completados", "estado_feedback": "Estado de Feedbacks"}


def _clave_filtros(pagina: str) -> str:
    return f"xf_{pagina}"


def aplicar_clic(df: pd.DataFrame, pagina: str) -> pd.DataFrame:
    """Aplica los filtros hechos con clic en las gráficas de la página (solo las columnas que la tabla tenga)."""
    for col, valores in st.session_state.get(_clave_filtros(pagina), {}).items():
        if col in df:
            df = df[df[col].astype(str).isin(valores)]
    return df


def _quitar_filtros(pagina: str) -> None:
    st.session_state[_clave_filtros(pagina)] = {}


def chips_clic(pagina: str) -> None:
    """Muestra los filtros activos por clic y el botón para quitarlos (o la pista de uso si no hay)."""
    f = st.session_state.get(_clave_filtros(pagina), {})
    if not f:
        st.caption(":material/touch_app: Haz clic en una barra o punto de las gráficas para filtrar la página; "
                   "clic de nuevo en el mismo elemento para quitar el filtro.")
        return
    texto = " · ".join(f"**{ETIQUETAS_FILTRO.get(c, c)}:** {', '.join(v)}" for c, v in f.items())
    a, b = st.columns([5, 1], vertical_alignment="center")
    a.info(f"Filtro por clic — {texto}", icon=":material/filter_alt:")
    b.button("Quitar filtro", icon=":material/filter_alt_off:", on_click=_quitar_filtros, args=(pagina,),
             key=f"xf_quitar_{pagina}", width="stretch")


def grafica(fig, pagina: str, clave: str, campos: dict, height: int = 340, alto_max: int | None = 520,
            leyenda: bool | None = None) -> None:
    """Dibuja la gráfica y, al hacer clic en una barra o punto, filtra la página.

    campos: de dónde sale cada valor del punto → columna a filtrar. Fuentes: "x", "y" o "trace" (nombre de la serie,
    p. ej. el riesgo en barras apiladas). Clic de nuevo en lo mismo = quitar ese filtro.
    """
    ver_k = f"xfv_{pagina}_{clave}"
    ver = st.session_state.get(ver_k, 0)
    fig = estilo(fig, height, leyenda)
    caja = st.container(height=alto_max) if alto_max and height > alto_max else st.container()
    with caja:  # listas largas: la gráfica conserva su alto y la caja hace scroll
        evento = st.plotly_chart(fig, width="stretch", on_select="rerun", selection_mode="points",
                                 key=f"xf_{pagina}_{clave}_{ver}", config=CONFIG_GRAFICA, theme=None)
    try:
        puntos = evento.selection.points or []
    except AttributeError:
        puntos = (evento or {}).get("selection", {}).get("points", []) if isinstance(evento, dict) else []
    if not puntos:
        return
    nuevo: dict[str, set] = {}
    for p in puntos:
        for fuente, col in campos.items():
            if fuente == "trace":
                n = p.get("curve_number")
                v = fig.data[n].name if n is not None and n < len(fig.data) else None
            else:
                v = p.get(fuente)
            if v is not None and str(v) != "":
                nuevo.setdefault(col, set()).add(str(v))
    if not nuevo:
        return
    actuales = dict(st.session_state.get(_clave_filtros(pagina), {}))
    mismo = all(sorted(v) == actuales.get(c) for c, v in nuevo.items())
    for c, v in nuevo.items():
        if mismo:
            actuales.pop(c, None)
        else:
            actuales[c] = sorted(v)
    st.session_state[_clave_filtros(pagina)] = actuales
    st.session_state[ver_k] = ver + 1  # gráfica nueva: sin la selección anterior marcada
    st.rerun()


DIAS_ES = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def etiqueta_dia(d) -> str:
    """«lun 17/11»: etiqueta para ejes que solo muestran los días con sesiones."""
    d = pd.Timestamp(d)
    return f"{DIAS_ES[d.weekday()]} {d:%d/%m}"


def fecha_corta(d) -> str:
    return "–" if d is None or pd.isna(d) else pd.Timestamp(d).strftime("%d/%m/%Y")


__all__ = ["C"]


# ------------------------------------------------------------------ tabla programa × nivel (ambas vistas)
def tabla_programa_nivel(t: pd.DataFrame) -> str:
    """HTML de la tabla de metrics.programa_nivel(): programas con su subtotal arriba y niveles debajo, total al
    final. Paleta Atenea; se lee igual en escritorio y celular."""
    css = (
        "<style>.tpn{width:100%;border-collapse:separate;border-spacing:0;font-size:.95rem;border-radius:14px;"
        "overflow:hidden;box-shadow:0 1px 3px rgba(20,20,57,.08);border:1px solid #D3E7EF}"
        ".tpn th{background:#141439;color:#fff;text-align:left;padding:10px 14px;font-weight:600;"
        "font-family:'Barlow Semi Condensed',sans-serif;letter-spacing:.04em}"
        ".tpn th.n,.tpn td.n{text-align:right;width:120px}"
        ".tpn td{padding:8px 14px;border-top:1px solid #E3EEF3;color:#141439}"
        ".tpn tr.sub td{background:#EEF6F9;font-weight:700}"
        ".tpn tr.det td:first-child{padding-left:30px;color:#3C4170}"
        ".tpn tr.tot td{background:#05247D;color:#fff;font-weight:700}"
        "@media (max-width:640px){.tpn{font-size:.85rem}.tpn th.n,.tpn td.n{width:80px}}</style>")
    filas = []
    for _, r in t.iterrows():
        g, p_ = num(r["grupos"]), num(r["participantes"])
        if r["tipo"] == "subtotal":
            filas.append(f"<tr class='sub'><td>{html.escape(str(r['programa']))}</td><td class='n'>{g}</td>"
                         f"<td class='n'>{p_}</td></tr>")
        elif r["tipo"] == "total":
            filas.append(f"<tr class='tot'><td>Total</td><td class='n'>{g}</td><td class='n'>{p_}</td></tr>")
    # niveles debajo de su programa: se reordena (subtotal arriba, detalle abajo)
    salida = []
    for prog in t.loc[t["tipo"].eq("subtotal"), "programa"]:
        sub = t[(t["programa"] == prog) & t["tipo"].eq("subtotal")].iloc[0]
        salida.append(f"<tr class='sub'><td>{html.escape(str(prog))}</td><td class='n'>{num(sub['grupos'])}</td>"
                      f"<td class='n'>{num(sub['participantes'])}</td></tr>")
        for _, d in t[(t["programa"] == prog) & t["tipo"].eq("detalle")].iterrows():
            salida.append(f"<tr class='det'><td>{html.escape(str(d['nivel']))}</td><td class='n'>{num(d['grupos'])}"
                          f"</td><td class='n'>{num(d['participantes'])}</td></tr>")
    salida += [f for f in filas if "class='tot'" in f]
    return (css + "<table class='tpn'><thead><tr><th>Programa / nivel</th><th class='n'>Grupos</th>"
            "<th class='n'>Participantes</th></tr></thead><tbody>" + "".join(salida) + "</tbody></table>")
