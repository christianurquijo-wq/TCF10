"""Definiciones, fórmulas y supuestos (todo sale de tcf10/config.py)."""
import pandas as pd
import streamlit as st

from tcf10 import config as C
from tcf10 import ui

ui.inicio("Cómo se calcula", "Definiciones del contrato y supuestos del tablero")

st.markdown(f"""
**Formación.** {ui.num(C.HORAS_TOTALES)} h por perfil: {ui.num(C.HORAS_SINCRONICAS, 1)} h sincrónicas (asistencia a
sesiones con docente) y {ui.num(C.HORAS_ASINCRONICAS, 1)} h asincrónicas (plataforma). Cada componente cuenta hasta
su tope: horas de más en uno no compensan el otro. **Culmina** quien llega al {ui.pct(C.UMBRAL_CULMINACION)}:
**{ui.num(C.HORAS_CULMINACION)} h válidas**.

**Fuente del avance.** Vistas VTD10 del SIS (BigQuery o su copia en Google Sheets), cruzadas por ID SIS: sincrónicas = sesiones pasadas con
asistencia × 4 h por sesión; asincrónicas = Horas_Plataforma_Acreditadas: tiempo pedagógico acreditado
(pedagogical_time de VTD10_student_progress_detail, en segundos ÷ 3.600, solo en recursos completados:
component_category = "resource" e is_completed = TRUE, igual que en Looker Studio) sumado por persona; cuenta hasta 58,5 h. Se excluyen los usuarios de prueba. La base de beneficiarios, grupos, docentes, retiros,
certificación y situación laboral sale del Google Sheet operativo.

**Riesgo (Anexo 8).** Se compara el avance con el esperado a la fecha según el calendario de la cohorte
(90 h × días transcurridos ÷ duración):
- **Alto:** ritmo menor a {ui.pct(C.RIESGO['alto']['ritmo_menor_a'])} del esperado o
  {C.RIESGO['alto']['dias_sin_actividad']} días o más sin actividad.
- **Medio:** ritmo menor a {ui.pct(C.RIESGO['medio']['ritmo_menor_a'])} o {C.RIESGO['medio']['dias_sin_actividad']}
  días o más sin actividad.
- **Bajo:** el resto. El ritmo se evalúa cuando ya se esperaban {ui.num(C.RIESGO_MIN_ESPERADO_H)} h y la inactividad
  después de {C.RIESGO_GRACIA_DIAS} días de iniciada la cohorte, para no alertar en falso la primera semana.

**Primeras dos semanas de cada grupo:** el ritmo de horas todavía no es representativo, así que manda la asistencia. Con al menos 2 sesiones registradas: **alto** si no asistió a ninguna y no tiene avance en la plataforma; **medio** si asistió a menos de la mitad.

Los umbrales son una propuesta inicial: se validan con Atenea y el coordinador académico.
""")

st.subheader("Pagos e índices")
filas = []
for clave, p in C.PAGOS.items():
    if clave == "culminacion":
        monto = f"{ui.plata(C.VALOR_POR_CULMINADO * C.CUPOS_CONTRATADOS)} máx. (${ui.num(C.VALOR_POR_CULMINADO)} por persona)"
        meta = "—"
    else:
        monto = ui.plata(p["pct_contrato"] * C.VALOR_CONTRATO) + f" ({ui.pct(p['pct_contrato'])})"
        meta = ui.pct(p["indice_ofertado"])
    filas.append({"Pago": p["nombre"], "Meta ofertada": meta, "Monto": monto, "Fórmula": p["formula"]})
st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
st.markdown("""
- Los índices son **todo o nada** y se redondean a entero antes de compararlos con la meta (nota general 3 del ET).
- Si no se alcanza un índice se pierde su pago (hasta 15 % del contrato según la Adenda 4) y Atenea restringe la
  participación en 1 a 3 convocatorias futuras.
- **Tránsito al mercado laboral:** solo convocatoria abierta, encuesta de empleabilidad al inicio y PILA en t3
  (tres meses después de terminar). No cuentan los contratos de aprendizaje.
- **Proyección del pago 2:** culminados + activos × probabilidad de culminar según su riesgo
  (supuesto ajustable en `tcf10/config.py`).
""")

st.subheader("Datos personales")
st.markdown("La app es pública (cualquiera con el enlace): nunca muestra nombres completos, documentos, correos ni "
            "teléfonos. Las listas de seguimiento usan el ID SIS y las iniciales.")
