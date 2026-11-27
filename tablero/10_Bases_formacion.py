"""Actualiza la DB Formación TCF10 (Cohorte 1 y 2) con las cifras del tablero. Solo vista interna (Kuepa)."""
import streamlit as st

import pandas as pd

from tcf10 import cortes, db_formacion, ui

ui.inicio("Bases de formación", "Grupo, fechas, horas por modalidad y % de avance en la DB Formación de cada cohorte")

st.markdown(f"""
Escribe en la pestaña **Seg.Formación** de cada archivo, por documento:
**GRUPO DE FORMACIÓN**, **FECHA_INICIO_FORMACIÓN**, **FECHA_FIN_FORMACIÓN**, **SÍNCRONO (35%)** y
**ASÍNCRONO (65%)** en horas completadas, **PORCENTAJE_AVANCE_FORMACIÓN** (horas completadas ÷ 90 h) y la
**semana** de la cohorte en N3. Las fórmulas de ICP y estado no se tocan. Quien no cruza con el SIS queda en blanco
con 0 h y aparece en la pestaña «{db_formacion.PESTANA_CONTROL}».

Se actualiza solo de lunes a sábado a las 7:05 a. m. y el domingo a las 11:59 p. m.; usa este botón si necesitas los datos de este momento.
""")
st.caption("Archivos: " + " · ".join(f"[{i[:8]}…](https://docs.google.com/spreadsheets/d/{i}/edit)"
                                      for i in db_formacion.ids_archivos()))

if st.button("Actualizar bases de formación ahora", type="primary", icon=":material/sync:"):
    mensajes = []
    with st.status("Actualizando…", expanded=True) as estado:
        try:
            resultados = db_formacion.actualizar_todo(log=lambda m: (mensajes.append(m), st.write(m)))
        except Exception as e:  # noqa: BLE001
            resultados = [{"archivo": "Datos del tablero", "error": f"{type(e).__name__}: {e}"}]
        errores = [r for r in resultados if "error" in r]
        estado.update(label="Listo" if not errores else f"Terminó con {len(errores)} error(es)",
                      state="complete" if not errores else "error")
    for r in resultados:
        if "error" in r:
            st.error(f"{r['archivo']}: {r['error']}", icon=":material/error:")
        else:
            st.success(f"{r['archivo']}: {r['personas']} personas · {r['sin_cruce']} sin cruce · semana {r['semana']}",
                       icon=":material/check_circle:")


# ------------------------------------------------------------------ cortes semanales (tcf10/cortes.py)
st.divider()
st.subheader("Cortes semanales · domingo 11:59 p. m.")
st.markdown("""
Cada domingo a las 11:59 p. m. se guarda una **copia completa** del archivo de cada cohorte, con las cifras
reconstruidas **hasta ese domingo** y todas las pestañas **congeladas en valores** (ICP y estado incluidos). Las copias
quedan en la carpeta de cortes y no cambian después. Cuando la cohorte cierra (domingo después del último
FECHA_FIN de sus grupos), deja de generar cortes.
""")
carpeta = cortes.carpeta_cortes()
if not carpeta:
    st.warning("Falta la carpeta de cortes: agrega `carpeta_cortes = \"<ID>\"` en la sección `[db_formacion]` de los "
               "Secrets. Debe estar en una unidad compartida, con la cuenta de servicio como «Administrador de "
               "contenido».", icon=":material/folder_off:")
    st.stop()
st.caption(f"[Abrir la carpeta de cortes](https://drive.google.com/drive/folders/{carpeta})")

@st.cache_data(ttl=300, show_spinner="Revisando cortes…")
def _estado():
    return cortes.estado()


try:
    lista, hechos = _estado()
except Exception as e:  # noqa: BLE001
    st.error(f"No pude leer las cohortes o la carpeta de cortes: {type(e).__name__}: {e}", icon=":material/error:")
    st.stop()

filas, opciones = [], {}
for c in lista:
    for f in c.domingos:
        previo = hechos.get((c.sheet_id, f"{f:%Y-%m-%d}"))
        filas.append({"Cohorte": c.titulo, "Semana": c.semana(f), "Domingo": f.date(),
                      "Estado": "✔ Generado" if previo else "Falta", "Abrir": (previo or {}).get("webViewLink")})
        opciones[f"{c.titulo} · semana {c.semana(f)} · domingo {f:%d/%m/%Y}"] = (c.sheet_id, f)
if filas:
    st.dataframe(pd.DataFrame(filas), hide_index=True, use_container_width=True,
                 column_config={"Domingo": st.column_config.DateColumn(format="DD/MM/YYYY"),
                                "Abrir": st.column_config.LinkColumn(display_text="Abrir copia")})
else:
    st.info("Todavía no hay domingos cumplidos en ninguna cohorte.", icon=":material/event_upcoming:")

faltan = sum(1 for f in filas if f["Estado"] == "Falta")


def _mostrar(resultados):
    _estado.clear()  # la tabla se actualiza en la siguiente interacción
    for r in resultados:
        if "error" in r:
            st.error(f"{r['archivo']} · {r['corte']}: {r['error']}", icon=":material/error:")
        elif r["estado"] in ("generado", "reemplazado"):
            st.success(f"{r['archivo']} · {r['corte']}: {r['estado']} · semana {r['semana']} · "
                       f"{r['sin_cruce']} sin cruce", icon=":material/check_circle:")
            for a in r.get("avisos", []):
                st.warning(a, icon=":material/warning:")


izq, der = st.columns(2)
with izq:
    st.markdown("**Generar los que falten**")
    st.caption(f"{faltan} corte(s) pendiente(s). Cada uno tarda cerca de un minuto.")
    if st.button("Generar cortes faltantes", type="primary", icon=":material/history:", disabled=not faltan):
        with st.status("Generando cortes…", expanded=True) as estado_ui:
            try:
                res = cortes.generar(log=st.write)
            except Exception as e:  # noqa: BLE001
                res = [{"archivo": "Cortes", "corte": "", "error": f"{type(e).__name__}: {e}"}]
            err = [r for r in res if "error" in r]
            estado_ui.update(label="Listo" if not err else f"Terminó con {len(err)} error(es)",
                             state="complete" if not err else "error")
        _mostrar(res)
with der:
    st.markdown("**Rehacer un corte**")
    if opciones:
        elegido = st.selectbox("Corte", list(opciones), index=len(opciones) - 1, label_visibility="collapsed")
        st.caption("Crea la copia otra vez con los datos de hoy del SIS y manda la anterior a la papelera.")
        if st.button("Rehacer este corte", icon=":material/restart_alt:"):
            sid, f = opciones[elegido]
            with st.status("Rehaciendo…", expanded=True):
                try:
                    res = cortes.generar(fecha=f, forzar=True, solo=[sid], log=st.write)
                except Exception as e:  # noqa: BLE001
                    res = [{"archivo": elegido, "corte": "", "error": f"{type(e).__name__}: {e}"}]
            _mostrar(res)
