"""¿Por qué salen menos franjas de las esperadas? Muestra de dónde sale la franja de cada grupo.

    python scripts/diagnostico_franjas.py credenciales.json potent-poetry-284019.DVTD_SIS [proyecto_de_consultas]

La app toma la franja de VTD10_student_attendance_detail.session_start_date: por grupo, la hora de inicio más
frecuente de sus sesiones, redondeada a la franja oficial más cercana (8:00, 13:00 o 17:00).
No imprime datos personales: solo el tipo de la columna, horas de inicio y número de grupos.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.cloud import bigquery  # noqa: E402
from google.oauth2.service_account import Credentials  # noqa: E402

from tcf10 import sis_sheet as S  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    creds = Credentials.from_service_account_file(sys.argv[1], scopes=["https://www.googleapis.com/auth/bigquery"])
    ds = sys.argv[2].strip("`")
    cli = bigquery.Client(credentials=creds, project=sys.argv[3] if len(sys.argv) > 3 else creds.project_id)
    proyecto, dataset = ds.split(".", 1)
    vista = S.PESTANAS["asis_det"]

    tipo = cli.query(f"SELECT data_type FROM `{proyecto}.{dataset}`.INFORMATION_SCHEMA.COLUMNS "
                     f"WHERE table_name = '{vista}' AND column_name = 'session_start_date'"
                     ).to_dataframe(create_bqstorage_client=False)
    print(f"Tipo de session_start_date: {tipo['data_type'].iloc[0] if len(tipo) else 'NO EXISTE'}")
    print("  (TIMESTAMP = UTC, la app lo pasa a hora de Bogotá; DATETIME/STRING = la app asume que ya es hora de Bogotá)\n")

    crudo = cli.query(f"SELECT CAST(session_start_date AS STRING) v FROM `{ds}.{vista}` "
                      "WHERE session_start_date IS NOT NULL LIMIT 3").to_dataframe(create_bqstorage_client=False)
    print("Ejemplos tal como vienen:", ", ".join(crudo["v"]), "\n")

    ad = cli.query(f"SELECT DISTINCT group_name, session_id, session_start_date FROM `{ds}.{vista}`"
                   ).to_dataframe(create_bqstorage_client=False)
    ini = S._fecha(ad["session_start_date"])
    print("Sesiones por hora de inicio (como la lee la app):")
    print(ini.dt.strftime("%H:%M").value_counts().sort_index().to_string(), "\n")

    fr = S.franjas_por_grupo(ad["group_name"], ad["session_start_date"])
    print(f"Grupos por franja asignada ({len(fr)} grupos con sesiones):")
    print(fr["franja"].value_counts().to_string())


if __name__ == "__main__":
    main()
