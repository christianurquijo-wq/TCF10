"""Cómo se calcula cada cifra de la vista Atenea (transparencia: fuente, fórmula y fecha de corte). nov-2026."""
import streamlit as st

from tcf10 import config as C
from tcf10 import data, ui
from vista_atenea import estilo

estilo.pagina("Cómo se calcula", "Fuentes, definiciones y supuestos de las cifras de esta herramienta")
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
- **No formalizado:** está en la base entregada pero no completó la formalización.
- **Desistió:** se retiró del programa.
- **Culminó:** alcanzó **{ui.num(C.HORAS_CULMINACION)} h válidas** ({ui.pct(C.UMBRAL_CULMINACION)} de
  {ui.num(C.HORAS_TOTALES)} h).
- **Por iniciar:** su cohorte aún no empieza. **En formación:** el resto de formalizados.
- Cada persona formalizada está en un solo estado.

#### Horas y asistencia
- **Horas sincrónicas válidas:** sesiones con docente a las que asistió × {ui.num(C.HORAS_POR_SESION)} h, hasta
  {ui.num(C.HORAS_SINCRONICAS, 1)} h.
- **Horas asincrónicas válidas:** tiempo pedagógico acreditado en los recursos completados de la plataforma, hasta
  {ui.num(C.HORAS_ASINCRONICAS, 1)} h. Las horas de más en un componente no compensan el otro.
- **Horas válidas** = sincrónicas válidas + asincrónicas válidas. **Avance a {ui.num(C.HORAS_CULMINACION)} h** =
  horas válidas ÷ {ui.num(C.HORAS_CULMINACION)} (máximo 100 %).
- **% asistencia** = sesiones asistidas ÷ sesiones con asistencia registrada.
- **Culminación estimada (ficha):** proyección lineal al ritmo de horas válidas desde el inicio de su grupo. Es una
  estimación, no un resultado: cambia si el ritmo cambia.

#### Metas del contrato
- **Enrolamiento:** formalizados ÷ {ui.num(C.CUPOS_CONTRATADOS)} cupos contratados.
- **Culminación:** personas con {ui.num(C.HORAS_CULMINACION)} h válidas o más.
- **Índice de éxito:** certificados de industria ÷ culminados.
- **Tránsito laboral:** personas formales en PILA a 3 meses de terminar ÷ culminados (solo convocatoria abierta).
- Las metas se calculan sobre toda la base, sin filtros, y se liquidan al cierre de las cohortes según el contrato
  ATENEA-497-2026. Las cifras de esta herramienta son de seguimiento; la liquidación oficial se hace con los soportes
  del contrato.
""")
