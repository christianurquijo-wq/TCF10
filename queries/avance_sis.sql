-- TCF10 · avance por beneficiario desde el SIS de Kuepa (BigQuery).
-- Parámetros (los pone tcf10/data.py):
--   @ids_sis      ARRAY<INT64>  ID SIS (INCREMENTAL_USER_CODE) de los beneficiarios de la base de Atenea
--   @horas_sesion FLOAT64       horas que vale cada sesión sincrónica asistida
-- {dataset} se reemplaza por el dataset del SIS de TCF10 (secrets: [tcf10] sis_dataset, ej. potent-poetry-284019.DSS3_SIS).
-- Misma estructura de tablas que usa el flujo «ENTREGABLES LOGS SDDE - STC 3.0».
WITH usuarios AS (
  SELECT U._ID AS user_id, U.INCREMENTAL_USER_CODE AS id_sis
  FROM `{dataset}.ES3100010_user` U
  WHERE U.INCREMENTAL_USER_CODE IN UNNEST(@ids_sis)
),
-- Asincrónico: tiempo en cada lección (un registro por lección: el de mayor avance y más reciente)
lecciones AS (
  SELECT u.id_sis,
         COALESCE(STAT_DET.TIME_VIEW, 0) / 3600 AS horas,
         STAT.UPDATED_AT AS actualizado
  FROM usuarios u
  JOIN `{dataset}.ES3100200_user_statistic` STAT ON STAT.USER = u.user_id
  JOIN `{dataset}.ES3100201_statistics` STAT_DET ON STAT_DET.__MODEL = STAT._ID
  WHERE STAT.DELETED IS NOT TRUE
  QUALIFY ROW_NUMBER() OVER (PARTITION BY u.id_sis, STAT_DET.ACADEMIC_COMPONENT
                             ORDER BY STAT_DET.COMPLETED_STATUS DESC, STAT.UPDATED_AT DESC) = 1
),
asincronico AS (
  SELECT id_sis, SUM(horas) AS horas_asinc, MAX(actualizado) AS ultima_leccion
  FROM lecciones GROUP BY id_sis
),
-- Sincrónico: sesiones de clase con asistencia registrada
sesiones AS (
  SELECT u.id_sis, COUNT(DISTINCT CS._ID) AS sesiones_asistidas, MAX(CS.START_DATE) AS ultima_sesion
  FROM usuarios u
  JOIN `{dataset}.ES3100411_participants` P ON P.USER = u.user_id
  JOIN `{dataset}.ES3100410_class_session` CS ON P.__CLASSSESSION = CS._ID
  WHERE P.ATTENDANCE_STATUS IS NOT NULL AND P.ATTENDANCE_STATUS NOT LIKE '%no-asistio%'
  GROUP BY u.id_sis
)
SELECT
  u.id_sis,
  ROUND(COALESCE(s.sesiones_asistidas, 0) * @horas_sesion, 2) AS horas_sinc,
  ROUND(COALESCE(a.horas_asinc, 0), 2)                       AS horas_asinc,
  COALESCE(s.sesiones_asistidas, 0)                         AS sesiones_asistidas,
  DATE(GREATEST(COALESCE(a.ultima_leccion, TIMESTAMP '1970-01-01'),
                COALESCE(s.ultima_sesion, TIMESTAMP '1970-01-01'))) AS ultima_actividad
FROM usuarios u
LEFT JOIN asincronico a USING (id_sis)
LEFT JOIN sesiones s USING (id_sis)
