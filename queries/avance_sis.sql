-- TCF10 · avance por beneficiario desde las vistas VTD10 del SIS (DSTD).
-- Parámetros (los pone tcf10/data.py):
--   @ids_sis          ARRAY<INT64>  ID SIS (incremental) de los beneficiarios del Sheet
--   @horas_sesion     FLOAT64       horas que vale cada sesión sincrónica asistida   (secrets: horas_por_sesion)
--   @divisor_tiempo   FLOAT64       time_view ÷ divisor = horas (3600 si viene en segundos, 60 si en minutos)
-- {dataset} = dataset de las vistas (secrets: sis_dataset = "potent-poetry-284019.DVTD_SIS").
-- Privacidad: no se seleccionan nombre, documento, correo ni teléfono; solo el ID SIS.

WITH asistencia AS (
  -- Sincrónico: sesiones pasadas con asistencia (un registro por estudiante × grupo)
  SELECT
    SAFE_CAST(incremental AS INT64)             AS id_sis,
    SUM(attended_sessions)                      AS sesiones_asistidas,
    SUM(total_sessions_to_date)                 AS sesiones_a_la_fecha,
    SUM(unregistered_sessions)                  AS sesiones_sin_registro,
    MAX(DATE(last_attendance_date))             AS ultima_asistencia,
    -- grupo principal: el que más sesiones tiene (completa el Sheet si el grupo viene vacío)
    ARRAY_AGG(group_name IGNORE NULLS ORDER BY total_sessions DESC LIMIT 1)[SAFE_OFFSET(0)] AS grupo_sis,
    MAX(last_updated_class_session)             AS actualizado_asistencia
  FROM `{dataset}.VTD10_student_attendance_per_group_summary`
  WHERE SAFE_CAST(incremental AS INT64) IN UNNEST(@ids_sis)
  GROUP BY id_sis
),

plataforma AS (
  -- Asincrónico: tiempo visto, a nivel de curso (una fila por estudiante × grupo × curso → sin doble conteo
  -- de lecciones y recursos)
  SELECT
    SAFE_CAST(incremental AS INT64)                         AS id_sis,
    SUM(COALESCE(course_time_view, 0)) / @divisor_tiempo    AS horas_asinc,
    SUM(lessons_completed)                                  AS lecciones_completadas,
    SUM(lessons_active)                                     AS lecciones_activas
  FROM `{dataset}.VTD10_student_progress_per_course_summary`
  WHERE SAFE_CAST(incremental AS INT64) IN UNNEST(@ids_sis)
  GROUP BY id_sis
),

ultima_plataforma AS (
  -- Última lección/recurso completado (la vista de curso no trae fecha)
  SELECT
    SAFE_CAST(incremental AS INT64)       AS id_sis,
    MAX(DATE(completed_date, 'America/Bogota')) AS ultimo_completado,
    MAX(last_updated_statistics)          AS actualizado_plataforma
  FROM `{dataset}.VTD10_student_progress_detail`
  WHERE SAFE_CAST(incremental AS INT64) IN UNNEST(@ids_sis)
  GROUP BY id_sis
),

ids AS (
  SELECT id_sis FROM asistencia
  UNION DISTINCT SELECT id_sis FROM plataforma
  UNION DISTINCT SELECT id_sis FROM ultima_plataforma
)

SELECT
  ids.id_sis,
  ROUND(COALESCE(a.sesiones_asistidas, 0) * @horas_sesion, 2)  AS horas_sinc,
  ROUND(COALESCE(p.horas_asinc, 0), 2)                         AS horas_asinc,
  COALESCE(a.sesiones_asistidas, 0)                            AS sesiones_asistidas,
  COALESCE(a.sesiones_a_la_fecha, 0)                           AS sesiones_a_la_fecha,
  COALESCE(a.sesiones_sin_registro, 0)                         AS sesiones_sin_registro,
  COALESCE(p.lecciones_completadas, 0)                         AS lecciones_completadas,
  COALESCE(p.lecciones_activas, 0)                             AS lecciones_activas,
  a.grupo_sis,
  GREATEST(COALESCE(a.ultima_asistencia, DATE '1970-01-01'),
           COALESCE(u.ultimo_completado, DATE '1970-01-01'))   AS ultima_actividad,
  LEAST(COALESCE(a.actualizado_asistencia, u.actualizado_plataforma),
        COALESCE(u.actualizado_plataforma, a.actualizado_asistencia)) AS actualizado_sis
FROM ids
LEFT JOIN asistencia a        USING (id_sis)
LEFT JOIN plataforma p        USING (id_sis)
LEFT JOIN ultima_plataforma u USING (id_sis)
WHERE ids.id_sis IS NOT NULL
