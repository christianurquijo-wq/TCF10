"""Ficha integral y dinámica de un participante: estado actual, trayectoria de horas, asistencia sesión por
sesión, avance por curso y comparación con su grupo y su cohorte."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from tcf10 import config as C
from tcf10 import data
from tcf10 import ui
from vista_atenea import comun, estilo
from vista_atenea import ficha_datos as FD

COLOR_SESION = {"Asistió": ui.AZUL, "No asistió": ui.NARANJA, "Sin registro": "#9AA3B5", "Programada": ui.CELESTE}

estilo.pagina("Ficha del participante", "Estado actual, trayectoria de horas, asistencia y avance en los cursos")
todos = comun.todos()
base = comun.filtrado(todos)

# ------------------------------------------------------------------ buscador
ident = data.identidades()
df = base.drop(columns=[c for c in ("nombre_completo", "tipo_documento", "documento") if c in base])
df = (df.merge(ident.drop(columns=[c for c in ("id_sis",) if c in ident]), on="huella", how="left")
      if "huella" in df and "huella" in ident else df.merge(ident, on="id_sis", how="left"))
df = df[df["enrolado"]].copy()
df["etiqueta"] = (df["nombre_completo"].fillna("Sin nombre") + " · " + df["tipo_documento"].fillna("").astype(str)
                  + " " + df["documento"].fillna("").astype(str)).str.replace(r"\s+", " ", regex=True)
df = df.sort_values("etiqueta")
ids = df["id_sis"].astype(int).tolist()
previo = st.session_state.get("at_ficha_id")
indice = ids.index(previo) if previo in ids else None
elegido = st.selectbox("Buscar participante", ids, index=indice, key="at_ficha_sel",
                       format_func=lambda i: df.loc[df["id_sis"] == i, "etiqueta"].iloc[0],
                       placeholder="Escribe el nombre o el número de documento")
if elegido is None:
    st.info("Busca a un participante por nombre o documento, o selecciónalo en la pestaña «Participantes». "
            "La lista respeta los filtros de la banda superior.", icon=":material/person_search:")
    st.stop()
st.session_state["at_ficha_id"] = int(elegido)
f = df[df["id_sis"] == elegido].iloc[0]
hoy = comun.hoy()
det = FD.detalle(f, hoy)

# ------------------------------------------------------------------ cabecera
estado = f["estado_atenea"]
chips = [(estado, comun.COLOR_ESTADO.get(estado, ui.GRIS))] + [
    (str(f[c]), ui.AZUL_PROFUNDO) for c in ("cohorte", "grupo", "franja", "nivel", "perfil")
    if str(f.get(c, "")) not in ("", "Sin dato", "nan")]
st.markdown(
    f"<div class='ficha-cab'><div class='ficha-nombre'>{f['nombre_completo'] or 'Participante'}</div>"
    f"<div class='ficha-datos'>{f['tipo_documento'] or ''} {f['documento'] or ''}"
    + ("" if f["id_sis"] > 0 else " · sin usuario en la plataforma") + "</div>"
    + "".join(f"<span class='chip' style='background:{c}'>{t}</span>" for t, c in chips) + "</div>",
    unsafe_allow_html=True)

# ------------------------------------------------------------------ estado actual
ses = det["sesiones"]
pasadas = ses[ses["estado"].isin(["Asistió", "No asistió"])]
asistio = int((pasadas["estado"] == "Asistió").sum())
pct_asis = asistio / len(pasadas) if len(pasadas) else None
valor_proy, nota_proy = FD.proyeccion(f, hoy)
dias_sin = f.get("dias_sin_actividad")
k = estilo.fila(5, "ficha")
with k[0]:
    estilo.kpi("Asistencia", ui.pct(pct_asis), f"asistió a {asistio} de {len(pasadas)} sesiones registradas", "azul")
with k[1]:
    estilo.kpi("Horas válidas", ui.num(f["horas_validas"], 1),
               f"{ui.pct(min(1, f['horas_validas'] / C.HORAS_CULMINACION))} de las {ui.num(C.HORAS_CULMINACION)} h "
               "para culminar", "noche")
with k[2]:
    estilo.kpi("Con docente + plataforma", f"{ui.num(f['horas_sinc_val'], 1)} + {ui.num(f['horas_asinc_val'], 1)}",
               f"topes: {ui.num(C.HORAS_SINCRONICAS, 1)} h con docente y {ui.num(C.HORAS_ASINCRONICAS, 1)} h en plataforma",
               "profundo")
with k[3]:
    estilo.kpi("Culminación estimada", valor_proy, nota_proy, "naranja")
with k[4]:
    estilo.kpi("Última actividad", ui.fecha_corta(f.get("ultima_actividad")),
               "sin registros" if pd.isna(dias_sin) else f"hace {int(dias_sin)} días", "celeste")

# ------------------------------------------------------------------ trayectoria de horas
estilo.seccion("Trayectoria de horas")
inicio = pd.to_datetime(f.get("fi_grupo") if pd.notna(f.get("fi_grupo", pd.NaT)) else f.get("fecha_inicio"))
fin = pd.to_datetime(f.get("ff_grupo") if pd.notna(f.get("ff_grupo", pd.NaT)) else f.get("fecha_fin"))
diario = det["diario"].copy()
if diario.empty or pd.isna(inicio):
    st.info("Todavía no hay horas registradas para este participante.")
else:
    diario["fecha"] = pd.to_datetime(diario["fecha"])
    dias = pd.date_range(min(inicio, diario["fecha"].min()), min(hoy, fin) if pd.notna(fin) else hoy, freq="D")
    d = diario.groupby("fecha")[["h_sinc", "h_asinc"]].sum().reindex(dias, fill_value=0).cumsum()
    d["sinc"] = d["h_sinc"].clip(upper=C.HORAS_SINCRONICAS)
    d["asinc"] = d["h_asinc"].clip(upper=C.HORAS_ASINCRONICAS)
    d["validas"] = d["sinc"] + d["asinc"]
    fig = go.Figure()
    fig.add_scatter(x=d.index, y=d["validas"], name="Horas válidas", mode="lines", line=dict(color=ui.NOCHE, width=3),
                    fill="tozeroy", fillcolor="rgba(32,81,160,.10)")
    fig.add_scatter(x=d.index, y=d["sinc"], name="Sincrónicas", mode="lines", line=dict(color=ui.AZUL, width=2))
    fig.add_scatter(x=d.index, y=d["asinc"], name="Asincrónicas", mode="lines", line=dict(color=ui.NARANJA, width=2))
    if pd.notna(fin):
        fig.add_scatter(x=[inicio, fin], y=[0, C.HORAS_TOTALES], name="Ritmo esperado", mode="lines",
                        line=dict(color="#9AA3B5", width=2, dash="dot"))
    fig.add_hline(y=C.HORAS_CULMINACION, line_dash="dash", line_color=ui.NARANJA,
                  annotation_text=f"Culminación: {ui.num(C.HORAS_CULMINACION)} h", annotation_position="top left")
    fig.update_layout(yaxis_title="Horas acumuladas", hovermode="x unified", legend=dict(orientation="h", y=1.12),
                      xaxis=dict(range=[inicio, fin if pd.notna(fin) else hoy]), separators=",.")
    st.plotly_chart(ui.dark_layout(fig, 360), width="stretch")
    st.caption("Sincrónicas: sesiones asistidas con el docente. Asincrónicas: horas acreditadas en la plataforma, "
               "distribuidas según los días de ingreso. La línea punteada es el avance esperado para completar 90 h al cierre.")

# ------------------------------------------------------------------ asistencia sesión por sesión
izq, der = st.columns([1.35, 1])
with izq:
    estilo.seccion("Asistencia sesión por sesión")
    if ses.empty:
        st.info("Sin sesiones en la plataforma para este participante.")
    else:
        fig = go.Figure()
        # Eje por categoría: solo los días con sesión, sin huecos entre una clase y otra.
        orden = ses.sort_values("fecha")
        orden = orden.assign(etiqueta=orden["fecha"].map(ui.etiqueta_dia))
        for e in FD.ESTADOS_SESION:
            x = orden[orden["estado"] == e]
            if len(x):
                fig.add_scatter(x=x["etiqueta"], y=[""] * len(x), mode="markers", name=e,
                                marker=dict(size=18, color=COLOR_SESION[e], line=dict(width=1, color="#fff")),
                                customdata=x["sesion"], hovertemplate="Sesión %{customdata} · %{x}<extra>" + e + "</extra>")
        fig.update_layout(xaxis=dict(type="category", categoryorder="array",
                                     categoryarray=orden["etiqueta"].drop_duplicates().tolist()),
                          yaxis=dict(visible=False), legend=dict(orientation="h", y=1.25), margin=dict(t=30))
        st.plotly_chart(ui.dark_layout(fig, 170), width="stretch")
        racha, maxr = 0, 0
        for e in pasadas.sort_values("fecha")["estado"]:
            racha = racha + 1 if e == "No asistió" else 0
            maxr = max(maxr, racha)
        actual = 0
        for e in pasadas.sort_values("fecha")["estado"][::-1]:
            if e != "No asistió":
                break
            actual += 1
        st.markdown(f"**{asistio}** asistencias · **{len(pasadas) - asistio}** inasistencias · "
                    f"**{int((ses['estado'] == 'Sin registro').sum())}** sin registro del docente · "
                    f"**{int((ses['estado'] == 'Programada').sum())}** por venir")
        st.caption(f"Inasistencias seguidas hoy: {actual} · máximo en el programa: {maxr}")

# ------------------------------------------------------------------ cursos
with der:
    estilo.seccion("Avance por curso")
    cur = det["cursos"]
    if cur.empty:
        st.info("Sin avance registrado en los cursos.")
    else:
        cur = cur.assign(nombre=cur["curso"].map(ui.curso_corto))
        fig = go.Figure(go.Bar(x=cur["avance"], y=cur["nombre"], orientation="h", marker_color=ui.AZUL,
                               text=[f"{a:.0%} · {c} de {t} lecciones" for a, c, t in
                                     zip(cur["avance"], cur["completadas"], cur["activas"])],
                               textposition="auto"))
        fig.update_layout(xaxis=dict(range=[0, 1], tickformat=".0%"), yaxis=dict(autorange="reversed", title=None))
        st.plotly_chart(ui.dark_layout(fig, 60 + 48 * len(cur)), width="stretch")
    if det["ultima_leccion"]:
        nombre, fecha, curso = det["ultima_leccion"]
        st.caption(f"Última lección terminada: **{nombre}**" + (f" ({ui.curso_corto(curso)})" if curso else "")
                   + f" · {ui.fecha_corta(fecha)}")

# ------------------------------------------------------------------ comparación
estilo.seccion("Comparación con su grupo y su cohorte")
activos = todos[todos["estado_atenea"].isin(["En formación", "Culminó"])].assign(
    asistencia=comun.asistencia_personas(todos))
grupo = activos[activos["grupo"] == f["grupo"]]
cohorte = activos[activos["cohorte"] == f["cohorte"]]
yo_asis = pct_asis if pct_asis is not None else comun.asistencia_personas(pd.DataFrame([f])).iloc[0]
serie = {"Participante": (yo_asis, f["horas_sinc_val"], f["horas_asinc_val"], f["horas_validas"]),
         f"Grupo {f['grupo']}": (grupo["asistencia"].mean(), grupo["horas_sinc_val"].mean(),
                                 grupo["horas_asinc_val"].mean(), grupo["horas_validas"].mean()),
         f"{f['cohorte']}": (cohorte["asistencia"].mean(), cohorte["horas_sinc_val"].mean(),
                             cohorte["horas_asinc_val"].mean(), cohorte["horas_validas"].mean())}
colores = [ui.NARANJA, ui.AZUL, ui.CELESTE]
a, b = st.columns([1, 1.6])
with a:
    fig = go.Figure(go.Bar(x=list(serie), y=[v[0] for v in serie.values()], marker_color=colores,
                           text=[ui.pct(v[0]) for v in serie.values()], textposition="outside"))
    fig.update_layout(title="Asistencia", yaxis=dict(tickformat=".0%", range=[0, 1.15]))
    st.plotly_chart(ui.dark_layout(fig, 300), width="stretch")
with b:
    fig = go.Figure()
    for (nombre, v), color in zip(serie.items(), colores):
        fig.add_bar(name=nombre, x=["Sincrónicas", "Asincrónicas", "Válidas"], y=list(v[1:]), marker_color=color,
                    text=[ui.num(x, 1) for x in v[1:]], textposition="outside")
    fig.update_layout(title="Horas", barmode="group", legend=dict(orientation="h", y=-0.18, x=0))
    st.plotly_chart(ui.dark_layout(fig, 300), width="stretch")
st.caption(f"Promedios de las personas en formación o que culminaron: {ui.num(len(grupo))} en el grupo y "
           f"{ui.num(len(cohorte))} en la cohorte.")
