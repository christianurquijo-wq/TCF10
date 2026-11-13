-- TCF10 · avance en plataforma agregado por grupo y curso (sin datos personales).
-- @ids_sis ARRAY<INT64>: beneficiarios de la base.
SELECT
  group_name                                           AS grupo,
  course_name                                          AS curso,
  COUNT(DISTINCT incremental)                          AS estudiantes,
  COUNTIF(progress_status = 'completado')              AS completado,
  COUNTIF(progress_status = 'en_progreso')             AS en_progreso,
  COUNTIF(progress_status = 'sin_iniciar')             AS sin_iniciar,
  AVG(course_completed_status) / 100                   AS avance_promedio,
  SAFE_DIVIDE(SUM(lessons_completed), SUM(lessons_active)) AS pct_lecciones
FROM `{dataset}.VTD10_student_progress_per_course_summary`
WHERE SAFE_CAST(incremental AS INT64) IN UNNEST(@ids_sis)
GROUP BY grupo, curso
