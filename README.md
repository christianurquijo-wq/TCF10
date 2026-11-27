# TCF10 · Tablero de seguimiento contractual

Talento Capital Formación 10 · Contrato ATENEA-497-2026 · Kuepa EduTech.
Streamlit + Google Sheet operativo + SIS Kuepa (BigQuery). Costo de infraestructura: $0 (Streamlit Community Cloud + sandbox/cuota gratuita de BigQuery).

## Páginas
| Página | Qué responde |
|---|---|
| Metas y pagos | Cuánto del contrato está asegurado, proyección del pago 2 (por culminado) y estado de los índices de enrolamiento, éxito y TML |
| Avance y riesgo | Horas válidas vs 63 h, riesgo alto/medio/bajo (Anexo 8) y lista priorizada para gestores |
| Cohortes y equipo | Enrolamiento, deserción y culminación por cohorte; topes de 30 activos/grupo, 3 grupos/docente, gestor y 3 franjas |
| Cómo se calcula | Fórmulas y supuestos (salen de `tcf10/config.py`) |

## Correr local
```bash
python -m venv .venv && .venv\Scripts\activate      # Windows
pip install -r requirements.txt
streamlit run app.py          # sin secrets arranca en MODO DEMO (datos sintéticos)
pytest -q
```

## Conectar datos reales
1. Google Sheet con dos pestañas (encabezados tolerantes a mayúsculas/tildes):
   - **BENEFICIARIOS**: id_sis, documento, nombre, cohorte, poblacion (Abierta/Cerrada), perfil, nivel, grupo, docente, gestor, franja, enrolado (SI/NO), estado (Entregado/Enrolado/Activo/Retirado/Culminó), lab_inicio (Desempleado/No formal/Formal), certificado (SI/NO), formal_t3 (SI/NO)
   - **COHORTES**: cohorte, fecha_inicio, fecha_fin, tipo
2. Compartir el Sheet (lector) con la cuenta de servicio y darle `BigQuery Data Viewer` + `Job User` sobre el dataset del SIS.
3. Copiar `.streamlit/secrets.toml.example` → secrets (local) o pegar en Streamlit Cloud › Settings › Secrets.
4. Correr `queries/validar_unidades.sql` en la consola de BigQuery y ajustar `horas_por_sesion` y `divisor_time_view`.
5. La cuenta de servicio necesita `BigQuery Data Viewer` sobre `DVTD_SIS` **y** sobre `DSTD_SIS`/`DSGE_SIS` (las vistas leen esas tablas), más `BigQuery Job User` en `bq_project`.

## Privacidad
La app es pública por enlace: **nunca** muestra nombre, documento, correo ni teléfono; solo ID SIS + iniciales.
`.gitignore` excluye secrets, llaves `.json` y cualquier dato real en `data/` (solo `data/demo/` es versionable).

## Parámetros del contrato
Todo en `tcf10/config.py` (cupos, valor, horas, metas, % de pagos, umbrales de riesgo). Cambiar ahí, no en las páginas.

## Asistente de datos (vista interna)

Botón flotante **«Asistente de datos»** en todas las páginas de la vista interna (`vista_atenea/asistente.py`; lógica
en `tcf10/consultas.py`, pruebas en `tests/test_consultas.py`). Sin IA: las cifras salen de la misma tabla que las
páginas internas.

- **Consultas frecuentes** (conversación guiada): solo les falta plataforma, 1 o 2 clases + plataforma, no alcanzan
  el 70 %, casos críticos, sin actividad desde una fecha, formalizados sin SIS, lista por estado, Feedbacks
  pendientes, quién faltó a clase, asistencia por grupo y fecha, resumen por cohorte/grupo/docente/franja/programa y
  distribución por estado, ruta o Feedbacks. Cada una se puede acotar con «Más filtros».
- **Constructor**: qué necesitas + universo + filtros combinables (cohorte, programa, nivel, grupo, franja, docente,
  gestor, estado, ruta, Feedbacks, caracterización, marcas de caso crítico, rangos de horas/ICP/días y fechas).
- **Fecha de corte** propia (por defecto la de la banda) y **rango de fechas** para asistencia.
- **CSV** para Excel en español («;», coma decimal, UTF-8 con BOM). Las listas traen documento, nombre, teléfono y
  correo (columnas de la base de Formalización; la ventana muestra de qué columnas salieron) y cada descarga queda en
  el registro de seguridad con el usuario y los filtros.
- **Discapacidad** (dato sensible): solo en resumen y distribución, con conteos de 1 a 4 como «< 5»; nunca en listas.

## Cortes semanales de la DB Formación (domingo 11:59 p. m.)

Copia completa del archivo de cada cohorte «como si se hubiera generado el domingo a las 11:59 p. m.», con las
cifras reconstruidas hasta ese día y **todas las pestañas congeladas en valores** (`tcf10/cortes.py`,
`scripts/cortes_semanales.py`, pruebas en `tests/test_cortes.py`). La pestaña viva «Seg.Formación» no se toca.

- **Cuándo**: `.github/workflows/db_formacion_cortes.yml`, domingo 11:59 p. m. (lunes 04:59 UTC). Luego actualiza la
  pestaña viva. Genera el domingo que acaba de pasar y cualquier domingo anterior que haya quedado sin corte.
- **Qué domingos**: desde el primer domingo después del inicio de la cohorte (inicio más frecuente de sus grupos) hasta
  el domingo de cierre (primer domingo en o después del último FECHA_FIN). Después la cohorte no genera más.
- **Reconstrucción del pasado**: la primera corrida (manual, sin fecha) genera todos los domingos ya cumplidos.
- **Fórmulas**: `HOY()`/`AHORA()` se cambian por la fecha del corte antes de congelar, para que ICP y estado salgan
  como ese domingo.
- **Configuración**: carpeta en una **unidad compartida**, con la cuenta de servicio como «Administrador de
  contenido». ID en `[db_formacion] carpeta_cortes` (Secrets de Streamlit) y en la variable del repositorio
  `DB_FORMACION_CARPETA_CORTES` (GitHub › Settings › Secrets and variables › Actions › Variables).
- **A mano**: página «Bases de formación» (generar faltantes / rehacer uno) o
  `python scripts/cortes_semanales.py [--listar | --corte AAAA-MM-DD [--forzar]]`.
