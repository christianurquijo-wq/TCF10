"""Cómo se calcula cada cifra de la vista Atenea (transparencia: fuente, fórmula y fecha de corte). nov-2026."""
import streamlit as st

from tcf10 import config as C
from tcf10 import data, ui
from vista_atenea import estilo

estilo.pagina("Cómo se calcula", "Fuentes, definiciones y supuestos de las cifras de esta herramienta")
ui.tablas_parametros()
horas_cache = data.TTL // 3600

st.markdown(f"""
#### Fuentes y actualización
- **Base de formalización del programa** (Google Sheets del operador): participantes, cohorte, estado de
  formalización, retiros y certificación.
- **Asignación docente** (Google Sheets): programa, nivel, grupo y jornada de cada participante.
- **Plataforma académica (SIS) de Kuepa EduTech** (BigQuery): sesiones, asistencia, horas en plataforma y avance en
  los cursos.
- Las fuentes se leen de nuevo cada {horas_cache} h o al pulsar **Actualizar**. Cada página muestra abajo la fecha de
  corte y la última actualización del SIS. Las asistencias de las últimas {C.REGISTRO_GRACIA_HORAS} h pueden estar
  pendientes de registro por el docente.

#### Estados del participante
- **Estado de formación** (grupo en curso, aún sin el 70 %), según su ICP — **{C.EN_FORMACION}** (≥ 75 %),
  **{C.EN_SEGUIMIENTO}** (60 % a < 75 %), **{C.RIESGO_BAJO}** (40 % a < 60 %), **{C.RIESGO_ALTO}** (10 % a < 40 %) y
  **{C.INACTIVO}** (< 10 %).
  **ICP (Índice de Cumplimiento del Plan)** = (horas completadas ÷ 90 h) ÷ línea base. La **línea base** es el % del
  curso que el plan cubre a hoy: horas planeadas acumuladas (sesiones sincrónicas y recursos asincrónicos del plan de
  cada curso y nivel) ÷ 90 h, por semana desde el inicio del grupo e interpolada día a día (p. ej. Marketing Básico:
  21 % al cerrar la semana 1, 64 % la 3, 88 % la 4 y 100 % la 8).
- **{C.APROBADO}:** supera el 70 % ({ui.num(C.HORAS_CULMINACION)} h completadas de {ui.num(C.HORAS_TOTALES)} h), en
  cuanto lo alcanza.
- **{C.NO_APROBADO}:** su grupo cerró y no superó el 70 %.
- **{C.ABANDONO}:** se retiró voluntariamente o su grupo cerró sin que realizara la formación (0 h).
- **{C.POR_INICIAR}:** su grupo aún no empieza. **{C.NO_FORMALIZADO}:** está en la base entregada pero no completó la
  formalización. Cada persona formalizada está en un solo estado.

#### Horas y asistencia
- **{C.ETQ_SINC} (35 %):** sesiones con docente a las que asistió × {ui.num(C.HORAS_POR_SESION)} h, hasta
  {ui.num(C.HORAS_SINCRONICAS, 1)} h.
- **{C.ETQ_ASINC} (65 %):** tiempo pedagógico acreditado en los recursos completados de la plataforma, hasta
  {ui.num(C.HORAS_ASINCRONICAS, 1)} h. Las horas de más en un componente no compensan el otro.
- **Horas completadas** = sincrónico + asincrónico, cada uno hasta su tope. **Avance a {ui.num(C.HORAS_CULMINACION)} h** =
  horas completadas ÷ {ui.num(C.HORAS_CULMINACION)} (máximo 100 %).
- **% asistencia** = sesiones asistidas ÷ sesiones con asistencia registrada.
- **Aprobación estimada (ficha):** proyección lineal al ritmo de horas completadas desde el inicio de su grupo. Es una
  estimación, no un resultado: cambia si el ritmo cambia.

#### Caracterización
- **Sexo, estrato, nivel educativo y discapacidad** vienen de la base de formalización (campos SDIS). Se muestran tal
  como están registrados; si el campo está vacío, «Sin información».
- La condición y el tipo de discapacidad son datos sensibles: sirven para filtrar y para conteos agregados, pero con
  ese filtro activo no se listan personas, y los grupos de menos de 5 personas aparecen como «< 5».

#### Metas del contrato
- **Enrolamiento:** formalizados ÷ {ui.num(C.CUPOS_CONTRATADOS)} cupos contratados.
- **Culminación (contrato):** personas aprobadas, con {ui.num(C.HORAS_CULMINACION)} h completadas o más.
- **Índice de éxito:** certificados de industria ÷ culminados.
- **Tránsito laboral:** personas formales en PILA a 3 meses de terminar ÷ culminados (solo convocatoria abierta).
- Las metas se calculan sobre toda la base, sin filtros, y se liquidan al cierre de las cohortes según el contrato
  ATENEA-497-2026. Las cifras de esta herramienta son de seguimiento; la liquidación oficial se hace con los soportes
  del contrato.
""")
