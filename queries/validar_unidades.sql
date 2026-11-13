-- TCF10 · correr UNA VEZ en la consola de BigQuery antes de activar los datos reales.
-- Objetivo: confirmar en qué unidad viene time_view y cuántas horas dura una sesión sincrónica.

-- 1) time_view: si "horas_si_segundos" da valores razonables (0-60 h por estudiante) → divisor 3600.
--    Si da casi cero y "horas_si_minutos" es razonable → divisor 60.
SELECT
  COUNT(DISTINCT incremental)                                         AS estudiantes,
  APPROX_QUANTILES(t, 4)                                              AS cuartiles_time_view_crudo,
  ROUND(AVG(t) / 3600, 1)                                             AS horas_si_segundos,
  ROUND(AVG(t) / 60, 1)                                               AS horas_si_minutos,
  ROUND(MAX(t) / 3600, 1)                                             AS max_horas_si_segundos
FROM (
  SELECT incremental, SUM(COALESCE(course_time_view, 0)) AS t
  FROM `potent-poetry-284019.DVTD_SIS.VTD10_student_progress_per_course_summary`
  GROUP BY incremental
);

-- 2) Duración real de las sesiones (para fijar horas_por_sesion)
SELECT
  ROUND(DATETIME_DIFF(session_end_date, session_start_date, MINUTE) / 60, 2) AS horas_sesion,
  COUNT(DISTINCT session_id) AS sesiones
FROM `potent-poetry-284019.DVTD_SIS.VTD10_student_attendance_detail`
GROUP BY horas_sesion
ORDER BY sesiones DESC
LIMIT 10;

-- 3) ¿El incremental es numérico para todos? (la app cruza por INT64)
SELECT
  COUNTIF(SAFE_CAST(incremental AS INT64) IS NULL) AS incrementales_no_numericos,
  COUNT(*) AS filas
FROM `potent-poetry-284019.DVTD_SIS.VTD10_student_attendance_per_group_summary`;
