"""Consulta del estado de formación por participante (con inicio de sesión: muestra datos por persona)."""
import pandas as pd
import streamlit as st

from tcf10 import config as C
from tcf10 import metrics as M
from tcf10 import ui

ui.inicio("Consulta por participante", "Estado de formación de cada persona: filtra por cohorte, grupo o jornada, "
          "o busca por documento")
correo = ui.acceso_restringido()
df = ui.datos()
if correo:
    st.caption(f"Sesión: {correo}")

# ------------------------------------------------------------------ filtros
base = ui.barra_filtros(df, "cp", ("cohorte", "grupo", "franja"))
if base.empty:
    st.warning("No hay participantes con esos filtros o ese documento.", icon=":material/search_off:")
    st.stop()

# ------------------------------------------------------------------ resumen del filtro
base = base.copy()
base["motivo"] = base.apply(M.motivo_riesgo, axis=1)
en_curso = base["riesgo"].isin(["Alto", "Medio", "Bajo"])
k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.tarjeta("Participantes", ui.num(len(base)), f"{ui.num(int(base['enrolado'].sum()))} formalizados", ui.AZUL)
with k2:
    ui.tarjeta("En formación", ui.num(int(en_curso.sum())), "enrolados que aún no culminan", ui.NOCHE)
with k3:
    ui.tarjeta("Riesgo alto", ui.num(int(base["riesgo"].eq("Alto").sum())),
               f"{ui.num(int(base['riesgo'].eq('Medio').sum()))} en riesgo medio", ui.ROJO)
with k4:
    prom = base.loc[base["enrolado"], "horas_validas"].mean()
    ui.tarjeta("Horas válidas promedio", ui.num(prom, 1), f"meta: {ui.num(C.HORAS_CULMINACION)} h", ui.NARANJA)

# ------------------------------------------------------------------ ficha individual
if len(base) == 1:
    f = base.iloc[0]
    st.subheader(f"Ficha · {ui.iniciales(f['nombre'])}")
    color = ui.COLOR_RIESGO.get(f["riesgo"], ui.GRIS)
    a, b = st.columns([1, 1.4])
    with a:
        st.markdown(
            f"<div class='tarjeta'><h4>Estado</h4><div class='valor' style='color:{color}'>{f['riesgo']}</div>"
            f"<div class='sub'>{f['motivo'] or 'Sin alertas'}</div>"
            f"<div style='margin-top:10px'>{ui.pill(str(f['estado']), ui.AZUL)}</div></div>",
            unsafe_allow_html=True)
    with b:
        filas = {
            "ID SIS": int(f["id_sis"]) if f["id_sis"] > 0 else "Sin usuario en el SIS",
            "Cohorte": f["cohorte"], "Grupo": f["grupo"], "Jornada": f["franja"], "Perfil": f["perfil"],
            "Nivel": f["nivel"],
            "Horas sincrónicas": f"{ui.num(f['horas_sinc_val'], 1)} de {ui.num(C.HORAS_SINCRONICAS, 1)} h",
            "Horas asincrónicas": f"{ui.num(f['horas_asinc_val'], 1)} de {ui.num(C.HORAS_ASINCRONICAS, 1)} h",
            "Horas válidas": f"{ui.num(f['horas_validas'], 1)} de {ui.num(C.HORAS_CULMINACION)} h para culminar",
            "Sesiones": (f"asistió a {int(f['sesiones_asistidas'])} de {int(f['sesiones_registradas'])} registradas"
                         if pd.notna(f.get("sesiones_registradas")) else "–"),
            "Ruta al 70 %": (f"{f['tipo_ruta']} · faltan {ui.num(f['faltan_h'], 1)} h "
                             f"({ui.num(f['faltan_plataforma_h'], 1)} h en plataforma)"
                             if f.get("tipo_ruta") and f.get("tipo_ruta") != "Ya aprobó" else (f.get("tipo_ruta") or "–")),
            "Caso crítico": f.get("motivo_critico") or "No",
            "Última actividad": ui.fecha_corta(f.get("ultima_actividad")),
            "Días sin actividad": ui.num(f.get("dias_sin_actividad")),
        }
        st.dataframe(pd.DataFrame({"Dato": list(filas), "Valor": [str(v) for v in filas.values()]}),
                     hide_index=True, width="stretch")
    st.markdown(ui.barra(f["horas_validas"] / C.HORAS_CULMINACION, None, color), unsafe_allow_html=True)
    st.caption(f"Avance hacia la culminación: {ui.pct(min(1, f['horas_validas'] / C.HORAS_CULMINACION))}")

# ------------------------------------------------------------------ listado
st.subheader(f"Participantes · {ui.num(len(base))}")
base["persona"] = base["nombre"].map(ui.iniciales)
base["id_sis_v"] = base["id_sis"].where(base["id_sis"] > 0)
base["_orden"] = base["riesgo"].map({"Alto": 0, "Medio": 1, "Bajo": 2, "Culminó": 3}).fillna(4)
vista = base.sort_values(["_orden", "horas_validas"])[
    ["id_sis_v", "persona", "cohorte", "grupo", "franja", "estado", "horas_sinc_val", "horas_asinc_val",
     "horas_validas", "tipo_ruta", "faltan_h", "sesiones_asistidas", "sesiones_registradas", "ultima_actividad",
     "riesgo", "motivo"]]
st.dataframe(
    vista, hide_index=True, width="stretch", height=480,
    column_config={
        "id_sis_v": st.column_config.NumberColumn("ID SIS", format="%d"), "persona": "Iniciales",
        "cohorte": "Cohorte", "grupo": "Grupo", "franja": "Jornada", "estado": "Estado",
        "horas_sinc_val": st.column_config.NumberColumn("Sincrónicas (h)", format="%.1f"),
        "horas_asinc_val": st.column_config.NumberColumn("Asincrónicas (h)", format="%.1f"),
        "horas_validas": st.column_config.ProgressColumn("Horas válidas", format="%.1f", min_value=0,
                                                         max_value=C.HORAS_CULMINACION),
        "tipo_ruta": "Ruta al 70 %", "faltan_h": st.column_config.NumberColumn("Faltan (h)", format="%.1f"),
        "sesiones_asistidas": st.column_config.NumberColumn("Asistió", format="%d"),
        "sesiones_registradas": st.column_config.NumberColumn("Registradas", format="%d"),
        "ultima_actividad": st.column_config.DateColumn("Última actividad", format="DD/MM/YYYY"),
        "riesgo": "Riesgo", "motivo": "Por qué",
    })
st.download_button("Descargar (CSV)", vista.to_csv(index=False).encode("utf-8-sig"), "tcf10_participantes.csv",
                   "text/csv", icon=":material/download:")
st.caption("Por privacidad se muestran ID SIS e iniciales; el documento solo se usa para buscar y no se guarda.")
