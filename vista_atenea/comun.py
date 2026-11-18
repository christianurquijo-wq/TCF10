"""Piezas compartidas de la vista para Atenea: datos, filtros globales (barra lateral) y estados en lenguaje
institucional. Sin montos ni clasificación de riesgo: solo datos objetivos de asistencia, horas y avance."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from tcf10 import config as C
from tcf10 import data
from tcf10 import ui

FILTROS = [("cohorte", "Cohorte"), ("grupo", "Grupo"), ("franja", "Franja"), ("nivel", "Nivel")]
ORDEN_ESTADO = ["En formación", "Culminó", "Por iniciar", "Sin usuario en plataforma", "Desistió", "No formalizado"]
COLOR_ESTADO = {"En formación": ui.AZUL, "Culminó": ui.NOCHE, "Por iniciar": ui.CELESTE,
                "Sin usuario en plataforma": ui.NARANJA, "Desistió": ui.GRIS, "No formalizado": "#DCE3EA"}


def hoy() -> pd.Timestamp:
    return ui.HOY_DEMO if data.modo_demo() else pd.Timestamp(datetime.now(ui.TZ).date())


def todos() -> pd.DataFrame:
    """Toda la base preparada (sin filtros)."""
    try:
        df, _ = ui._preparado(hoy())
    except data.ErrorConfiguracion as e:
        st.error(str(e), icon=":material/error:")
        st.stop()
    df = df.copy()
    df["estado_atenea"] = df.apply(estado, axis=1)
    return df


def estado(f: pd.Series) -> str:
    if f["estado"] == "No formalizado" or not f["enrolado"]:
        return "No formalizado"
    if f["retirado"]:
        return "Desistió"
    if f.get("en_sis") in (False,):
        return "Sin usuario en plataforma"
    if f["culmino"]:
        return "Culminó"
    if not f["cohorte_iniciada"]:
        return "Por iniciar"
    return "En formación"


def filtros_banda(df: pd.DataFrame) -> None:
    """Filtros globales en la banda superior (valen para todas las páginas)."""
    cols = st.columns(len(FILTROS))
    base = df
    for c, (col, etiqueta) in zip(cols, FILTROS):
        opciones = sorted(base[col].dropna().astype(str).unique())
        sel = c.multiselect(etiqueta, opciones, key=f"at_{col}", placeholder="Todos")
        if sel:
            base = base[base[col].astype(str).isin(sel)]


def filtrado(df: pd.DataFrame) -> pd.DataFrame:
    for col, _ in FILTROS:
        sel = st.session_state.get(f"at_{col}") or []
        if sel:
            df = df[df[col].astype(str).isin(sel)]
    return df


def nota_filtros() -> None:
    """Los filtros ya se ven en la banda: aquí no se repiten."""
    return None


def asistencia_personas(df: pd.DataFrame) -> pd.Series:
    reg = pd.to_numeric(df.get("sesiones_registradas"), errors="coerce")
    return pd.to_numeric(df.get("sesiones_asistidas"), errors="coerce") / reg.where(reg > 0)


def agregados_asistencia(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ids = tuple(sorted(int(x) for x in df["id_sis"].dropna().unique() if int(x) > 0))
    asis, prog = data.agregados(ids)
    grupos = set(df["grupo"])
    asis = asis[asis["grupo"].isin(grupos)].copy()
    prog = prog[prog["grupo"].isin(grupos)].copy()
    # lo de las últimas 24 h todavía puede estar por registrar por el docente
    limite = (pd.Timestamp(datetime.now(ui.TZ).replace(tzinfo=None))
              - pd.Timedelta(hours=C.REGISTRO_GRACIA_HORAS)).normalize()
    asis.loc[pd.to_datetime(asis["fecha"]) >= limite, "sin_registro"] = 0
    return asis, prog
