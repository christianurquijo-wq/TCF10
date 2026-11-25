"""Datos de la ficha integral de un participante: sesiones, trayectoria diaria de horas, recursos y último recurso.

Con el SIS en Google Sheets se arma con las pestañas VTD10 (asistencia por sesión, ingresos con tiempo en
plataforma y progreso por lección). En modo demo se generan datos sintéticos coherentes con la fila del tablero.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tcf10 import config as C
from tcf10 import data, sis_sheet

ESTADOS_SESION = ["Asistió", "No asistió", "Sin registro", "Programada"]


def _cfg_float(nombre: str, defecto: float) -> float:
    try:
        return float(data._cfg().get(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


def detalle(f: pd.Series, hoy: pd.Timestamp) -> dict:
    if data.modo_demo() or pd.isna(f["id_sis"]) or int(f["id_sis"]) <= 0:
        return _demo(f, hoy) if data.modo_demo() else _vacio()
    t = data._sis_sheet(data._esquema_sis())
    pid = int(f["id_sis"])
    horas_sesion = float(C.HORAS_POR_SESION)

    s = t["asis_det"][t["asis_det"]["id_sis"] == pid].copy()
    # hoy = fecha de corte: lo posterior a ese día aún no había pasado
    pasada = s["is_past_session"] & (s["session_date"].dt.normalize() <= hoy)
    s["estado"] = np.select([pasada & (s["attended"] > 0), pasada & (s["not_attended"] > 0), pasada],
                            ["Asistió", "No asistió", "Sin registro"], default="Programada")
    sesiones = (s.sort_values("session_date")
                  .rename(columns={"session_date": "fecha", "session_number": "sesion"})[["fecha", "sesion", "estado"]])

    # Trayectoria: sincrónicas el día de cada sesión asistida; asincrónicas repartidas según el tiempo de cada
    # ingreso a la plataforma (login_activity), escaladas al total que reporta el SIS por curso.
    sinc = sesiones[sesiones["estado"] == "Asistió"].assign(h_sinc=horas_sesion)
    sinc = sinc.groupby(sinc["fecha"].dt.normalize())["h_sinc"].sum()
    lg = t["login"][(t["login"]["id_sis"] == pid) & (t["login"]["log_date"].dt.normalize() <= hoy)]
    if "time_view" in lg:
        tv = lg.groupby(lg["log_date"].dt.normalize())["time_view"].sum()
    else:  # caché de una versión anterior sin el tiempo por ingreso: se reparte igual entre los días de ingreso
        tv = lg.groupby(lg["log_date"].dt.normalize()).size().astype(float)
    total_asinc = float(f.get("horas_asinc", 0) or 0)
    asinc = (tv / tv.sum() * total_asinc) if tv.sum() > 0 else pd.Series(dtype=float)
    diario = pd.concat([sinc.rename("h_sinc"), asinc.rename("h_asinc")], axis=1).fillna(0).sort_index()
    diario.index.name = "fecha"

    # Recursos completados hasta la fecha de corte: la gráfica por curso y la tabla salen de las mismas filas, que
    # son las que suman las horas asincrónicas (pedagogical_time de recursos completados).
    rec = sis_sheet.recursos(t, [pid], hoy)
    ultima = None
    if len(rec):
        u = rec.dropna(subset=["fecha"]).sort_values("fecha")
        if len(u):
            ultima = (str(u.iloc[-1]["recurso"]), u.iloc[-1]["fecha"], str(u.iloc[-1]["curso"]))
    elif not sis_sheet.hay_recursos(t):
        ultima = sis_sheet.ultima_leccion(t, pid)
    return {"sesiones": sesiones.reset_index(drop=True), "diario": diario.reset_index(), "cursos": cursos_de(rec),
            "recursos": rec, "ultima_leccion": ultima, "hay_recursos": sis_sheet.hay_recursos(t)}


def cursos_de(rec: pd.DataFrame) -> pd.DataFrame:
    """Recursos completados y horas por curso (lo que dibuja la gráfica «Avance por curso»)."""
    if rec.empty:
        return pd.DataFrame(columns=["curso", "recursos", "horas"])
    return (rec.groupby("curso", dropna=False).agg(recursos=("recurso", "size"), horas=("horas", "sum"))
               .reset_index().sort_values("curso"))


def _vacio() -> dict:
    return {"sesiones": pd.DataFrame(columns=["fecha", "sesion", "estado"]),
            "diario": pd.DataFrame(columns=["fecha", "h_sinc", "h_asinc"]),
            "cursos": cursos_de(pd.DataFrame(columns=["curso", "recurso", "horas"])),
            "recursos": pd.DataFrame(columns=["id_sis", "curso", "leccion", "recurso", "fecha", "horas"]),
            "ultima_leccion": None, "hay_recursos": True}


def _demo(f: pd.Series, hoy: pd.Timestamp) -> dict:
    """Datos sintéticos para probar la ficha sin el SIS (coherentes con las horas de la fila)."""
    rng = np.random.default_rng(int(f["id_sis"]) if pd.notna(f["id_sis"]) else 1)
    inicio = pd.to_datetime(f.get("fi_grupo") if pd.notna(f.get("fi_grupo", pd.NaT)) else f["fecha_inicio"])
    fin = pd.to_datetime(f.get("ff_grupo") if pd.notna(f.get("ff_grupo", pd.NaT)) else f["fecha_fin"])
    if pd.isna(inicio):
        return _vacio()
    fechas = pd.date_range(inicio, fin if pd.notna(fin) else inicio + pd.Timedelta(days=70), freq="3D")
    prob = min(0.95, max(0.15, float(f["horas_sinc_val"]) / max(1.0, C.HORAS_SINCRONICAS * 0.6)))
    estados = []
    for d in fechas:
        if d > hoy:
            estados.append("Programada")
        else:
            estados.append(rng.choice(["Asistió", "No asistió", "Sin registro"], p=[prob, (1 - prob) * .8, (1 - prob) * .2]))
    sesiones = pd.DataFrame({"fecha": fechas, "sesion": range(1, len(fechas) + 1), "estado": estados})
    pasadas = sesiones[sesiones["estado"] == "Asistió"]
    h_s = float(f["horas_sinc_val"]) / max(1, len(pasadas))
    dias = pd.date_range(inicio, min(hoy, fin) if pd.notna(fin) else hoy, freq="D")
    pesos = rng.random(len(dias)) * (rng.random(len(dias)) > .55)
    asinc = pesos / pesos.sum() * float(f["horas_asinc_val"]) if pesos.sum() > 0 else np.zeros(len(dias))
    diario = pd.DataFrame({"fecha": dias, "h_asinc": asinc})
    diario = diario.merge(pasadas[["fecha"]].assign(h_sinc=h_s), on="fecha", how="outer").fillna(0).sort_values("fecha")
    # Recursos sintéticos que suman exactamente las horas asincrónicas de la fila
    total = float(f.get("horas_asinc", f["horas_asinc_val"]) or 0)
    n = int(max(0, round(total / 0.6)))
    filas = []
    if n:
        dur = rng.uniform(0.2, 1.0, n)
        dur = dur / dur.sum() * total
        fechas_r = sorted(rng.choice(dias, size=n)) if len(dias) else [hoy] * n
        for k in range(n):
            curso = ["Inducción", "Módulo 1", "Módulo 2", "Módulo 3"][min(3, k * 4 // n)]
            filas.append({"id_sis": f["id_sis"], "curso": curso, "leccion": f"Tema {k // 3 + 1}",
                          "recurso": f"Recurso {k + 1} · {curso}", "fecha": pd.Timestamp(fechas_r[k]), "horas": dur[k]})
    rec = pd.DataFrame(filas, columns=["id_sis", "curso", "leccion", "recurso", "fecha", "horas"])
    ultima = ((rec.iloc[-1]["recurso"], rec.iloc[-1]["fecha"], rec.iloc[-1]["curso"]) if len(rec) else None)
    return {"sesiones": sesiones, "diario": diario, "cursos": cursos_de(rec), "recursos": rec,
            "ultima_leccion": ultima, "hay_recursos": True}


def proyeccion(f: pd.Series, hoy: pd.Timestamp) -> tuple[str, str]:
    """(valor, nota) de la fecha estimada de culminación al ritmo actual."""
    if f.get("culmino"):
        return C.APROBADO, f"{f['horas_validas']:.1f} h completadas".replace(".", ",")
    inicio = pd.to_datetime(f.get("fi_grupo") if pd.notna(f.get("fi_grupo", pd.NaT)) else f.get("fecha_inicio"))
    fin = pd.to_datetime(f.get("ff_grupo") if pd.notna(f.get("ff_grupo", pd.NaT)) else f.get("fecha_fin"))
    if pd.isna(inicio) or hoy <= inicio:
        return "–", "aún no inicia su grupo"
    dias = max(1, (hoy - inicio).days)
    ritmo = float(f["horas_validas"]) / dias  # horas por día calendario
    if ritmo <= 0:
        return "Sin avance", "no registra horas todavía"
    faltan = max(0.0, C.HORAS_CULMINACION - float(f["horas_validas"]))
    fecha = hoy + pd.Timedelta(days=int(np.ceil(faltan / ritmo)))
    if pd.notna(fin) and fecha > fin:
        al_cierre = float(f["horas_validas"]) + ritmo * max(0, (fin - hoy).days)
        return "No alcanza", f"a su ritmo llegaría a {al_cierre:.0f} h al cierre ({fin:%d/%m/%Y})".replace(".", ",")
    return f"{fecha:%d/%m/%Y}", f"a su ritmo actual ({ritmo * 7:.1f} h por semana)".replace(".", ",")
