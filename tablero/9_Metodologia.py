"""Definiciones, fórmulas y supuestos (todo sale de tcf10/config.py)."""
import pandas as pd
import streamlit as st

from tcf10 import config as C
from tcf10 import ui

ui.inicio("Cómo se calcula", "Definiciones del contrato y supuestos del tablero")
ui.tablas_parametros()

st.markdown(f"""
**Formación.** {ui.num(C.HORAS_TOTALES)} h por perfil: {ui.num(C.HORAS_SINCRONICAS, 1)} h de {C.ETQ_SINC.lower()}
(35 %, sesiones con docente) y {ui.num(C.HORAS_ASINCRONICAS, 1)} h de {C.ETQ_ASINC.lower()} (65 %, plataforma). Cada
componente cuenta hasta su tope: horas de más en uno no compensan el otro. **Aprueba** quien supera el
{ui.pct(C.UMBRAL_CULMINACION)}: **{ui.num(C.HORAS_CULMINACION)} h completadas**.

**Fuente del avance.** Vistas VTD10 del SIS (BigQuery o su copia en Google Sheets), cruzadas por ID SIS: sincrónicas = sesiones pasadas con
asistencia × 4 h por sesión; asincrónicas = Horas_Plataforma_Acreditadas: tiempo pedagógico acreditado
(pedagogical_time de VTD10_student_progress_detail, en segundos ÷ 3.600, solo en recursos completados:
component_category = "resource" e is_completed = TRUE, igual que en Looker Studio) sumado por persona; cuenta hasta 58,5 h. Se excluyen los usuarios de prueba. La base de beneficiarios, grupos, docentes, retiros,
certificación y situación laboral sale del Google Sheet operativo.

**Estados del participante** (cuadro de parámetros de Kuepa EduTech, nov-2026):
- **Estado de formación** (grupo en curso y aún sin el 70 %), según el ICP con los rangos del cuadro.
  **ICP (Índice de Cumplimiento del Plan)** = (horas completadas ÷ 90 h) ÷ línea base. La **línea base** es el % del
  curso que el plan cubre a hoy: horas planeadas acumuladas (sesiones sincrónicas y recursos asincrónicos del plan de
  cada curso y nivel) ÷ 90 h, por semana desde el inicio del grupo e interpolada día a día (p. ej. Marketing Básico:
  21 % al cerrar la semana 1, 64 % la 3, 88 % la 4 y 100 % la 8).
  Igual que la hoja «Seg.Formación» de la DB Formación, pero con la semana de cada grupo (no una sola para todos).
  El día de inicio del grupo queda en *{C.EN_FORMACION}*. Formalizado sin usuario en el SIS = *{C.INACTIVO}*.
- **{C.APROBADO}:** apenas supera el 70 % ({ui.num(C.HORAS_CULMINACION)} h completadas).
- **Al cerrar su grupo** sin llegar al 70 %: *{C.NO_APROBADO}*; si no registró ninguna hora, *{C.ABANDONO}*.
  Quien se retira: *{C.ABANDONO}* (voluntaria) en cualquier momento.
- Además: *{C.POR_INICIAR}* (su grupo no ha empezado) y *{C.NO_FORMALIZADO}*.

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
- **Proyección del pago 2:** aprobados + personas en curso × probabilidad de aprobar según su estado de formación
  (supuesto ajustable en `tcf10/config.py`).
""")

st.subheader("Ruta al 70 % y casos críticos")
st.markdown(f"""
- **Meta:** {ui.num(C.HORAS_CULMINACION)} h completadas (70 % de {ui.num(C.HORAS_TOTALES)} h). Con la plataforma al 100 %
  ({ui.num(C.HORAS_ASINCRONICAS, 1)} h) faltan {ui.num(C.HORAS_CULMINACION - C.HORAS_ASINCRONICAS, 1)} h con docente;
  cada clase asistida vale {ui.num(C.HORAS_POR_SESION)} h, así que se necesitan **2 clases** en total.
- **Ruta:** con 2 o más clases → *Solo plataforma*; con 1 → *1 clase + plataforma*; sin clases → *2 clases +
  plataforma*. *No alcanza*: le faltan más clases de las que quedan en su grupo (o el grupo cerró sin llegar).
  *Ya aprobó*: ya tiene {ui.num(C.HORAS_CULMINACION)} h.
- **Faltan (h):** {ui.num(C.HORAS_CULMINACION)} h menos sus horas completadas. **En plataforma (h):** lo que debe
  completar en plataforma si asiste solo a las clases mínimas de su ruta.
- **Caso crítico** (solo grupos en curso): 0 h en plataforma con el grupo iniciado hace {C.DIAS_SIN_PLATAFORMA}+ días,
  {C.DIAS_SIN_PLATAFORMA}+ días sin entrar a la plataforma, *No alcanza*, o {C.FEEDBACK_ATRASO_CRITICO} o más Feedbacks
  pendientes.
""")

st.subheader("Feedbacks")
st.markdown(f"""
- **Qué cuenta:** los componentes «Feedback 1» a «Feedback {C.FEEDBACKS_TOTAL}» de la plataforma marcados como
  completados (`is_completed = TRUE` en `VTD10_student_progress_detail`).
- **Meta a hoy:** un Feedback por clase dictada a su grupo, hasta {C.FEEDBACKS_TOTAL}. Cuentan las clases de días
  anteriores; la de hoy todavía no se exige.
- **Pendientes:** meta menos Feedbacks hechos. **Estado:** Al día, 1 pendiente, 2 pendientes o 3 o más pendientes.
- Con {C.FEEDBACK_ATRASO_CRITICO} o más pendientes y el grupo en curso, el estudiante es **caso crítico**.
""")

st.subheader("Datos personales")
st.markdown("La vista interna solo la ven los correos autorizados en `[atenea] internos` (con Google). La página "
            "«Grupos y casos críticos» muestra nombre y documento para poder contactar a cada estudiante; el resto "
            "de páginas internas usa ID SIS e iniciales.")
