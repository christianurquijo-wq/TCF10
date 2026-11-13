-- TCF10 · asistencia agregada por grupo y sesión (sin datos personales).
-- @ids_sis ARRAY<INT64>: beneficiarios de la base.
SELECT
  group_name                                   AS grupo,
  session_id,
  ANY_VALUE(session_number)                    AS sesion,
  ANY_VALUE(session_date)                      AS fecha,
  COUNT(DISTINCT incremental)                  AS convocados,
  SUM(attended)                                AS asistieron,
  SUM(not_attended)                            AS no_asistieron,
  SUM(not_registered)                          AS sin_registro,
  MAX(last_updated_class_session)              AS actualizado
FROM `{dataset}.VTD10_student_attendance_detail`
WHERE is_past_session
  AND SAFE_CAST(incremental AS INT64) IN UNNEST(@ids_sis)
GROUP BY grupo, session_id
