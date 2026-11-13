-- TCF10 · base de beneficiarios desde el SIS (se usa SOLO mientras no exista el Google Sheet operativo).
-- Un registro por estudiante con su grupo más reciente. La cohorte se arma con la fecha de inicio del grupo.
-- Privacidad: el nombre no sale de BigQuery; solo se devuelven el ID SIS y las iniciales.
WITH por_estudiante AS (
  SELECT
    SAFE_CAST(incremental AS INT64) AS id_sis,
    ANY_VALUE(student_name)         AS nombre,
    ARRAY_AGG(STRUCT(program_name, section_name, group_name, group_start_date, group_end_date)
              ORDER BY group_start_date DESC LIMIT 1)[OFFSET(0)] AS g
  FROM `{dataset}.VTD10_student_progress_per_course_summary`
  WHERE SAFE_CAST(incremental AS INT64) IS NOT NULL
  GROUP BY id_sis
)
SELECT
  id_sis,
  ARRAY_TO_STRING(ARRAY(
    SELECT CONCAT(UPPER(SUBSTR(p, 1, 1)), '.')
    FROM UNNEST(SPLIT(REGEXP_REPLACE(TRIM(COALESCE(nombre, '')), r'\s+', ' '), ' ')) AS p WITH OFFSET o
    WHERE p != ''
    ORDER BY o LIMIT 4), '')  AS iniciales,
  g.program_name              AS perfil,
  g.section_name              AS nivel,
  g.group_name                AS grupo,
  g.group_start_date          AS fecha_inicio,
  g.group_end_date            AS fecha_fin
FROM por_estudiante
