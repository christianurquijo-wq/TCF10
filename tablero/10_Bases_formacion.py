"""Actualiza la DB Formación TCF10 (Cohorte 1 y 2) con las cifras del tablero. Solo vista interna (Kuepa)."""
import streamlit as st

from tcf10 import db_formacion, ui

ui.inicio("Bases de formación", "Grupo, fechas, horas por modalidad y % de avance en la DB Formación de cada cohorte")

st.markdown(f"""
Escribe en la pestaña **Seg.Formación** de cada archivo, por documento:
**GRUPO DE FORMACIÓN**, **FECHA_INICIO_FORMACIÓN**, **FECHA_FIN_FORMACIÓN**, **SÍNCRONO (35%)** y
**ASÍNCRONO (65%)** en horas completadas, **PORCENTAJE_AVANCE_FORMACIÓN** (horas completadas ÷ 90 h) y la
**semana** de la cohorte en N3. Las fórmulas de ICP y estado no se tocan. Quien no cruza con el SIS queda en blanco
con 0 h y aparece en la pestaña «{db_formacion.PESTANA_CONTROL}».

Se actualiza solo de lunes a sábado a las 7:05 a. m.; usa este botón si necesitas los datos de este momento.
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
