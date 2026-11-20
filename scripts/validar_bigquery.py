"""Comprueba que la cuenta de servicio puede leer las vistas VTD10 en BigQuery, antes de configurar la app.

    python scripts/validar_bigquery.py credenciales.json potent-poetry-284019.DVTD_SIS [proyecto_de_consultas]

No imprime datos personales: solo vistas encontradas, columnas que faltan y número de filas.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.cloud import bigquery  # noqa: E402
from google.oauth2.service_account import Credentials  # noqa: E402

from tcf10 import config as C  # noqa: E402
from tcf10 import sis_sheet as S  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    creds = Credentials.from_service_account_file(sys.argv[1], scopes=["https://www.googleapis.com/auth/bigquery"])
    ds = sys.argv[2].strip("`")
    proyecto_consultas = sys.argv[3] if len(sys.argv) > 3 else creds.project_id
    cli = bigquery.Client(credentials=creds, project=proyecto_consultas)
    print(f"Cuenta: {creds.service_account_email}\nConsultas en: {proyecto_consultas}\nDataset: {ds}\n")
    proyecto, dataset = ds.split(".", 1)
    try:
        info = cli.query(f"SELECT table_name, column_name FROM `{proyecto}.{dataset}`.INFORMATION_SCHEMA.COLUMNS").to_dataframe(
            create_bqstorage_client=False)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"ERROR al listar columnas ({getattr(e, 'code', '')}): {getattr(e, 'message', e)}\n"
                 "→ Falta «BigQuery Job User» en el proyecto de consultas o «BigQuery Data Viewer» en el dataset.")
    cols = info.groupby("table_name")["column_name"].apply(set).to_dict()
    excl = ", ".join(str(x) for x in C.USUARIOS_PRUEBA)
    for clave, vista in S.PESTANAS.items():
        if vista not in cols:
            print(f"✗ {vista}: NO EXISTE" + ("" if clave in S.OPCIONALES else "  (obligatoria)"))
            continue
        faltan = [c for c in S.COLUMNAS[clave] if c not in cols[vista]]
        idc = "user_incremental" if clave == "basica" else "incremental"
        n = cli.query(f"SELECT COUNT(*) n FROM `{ds}.{vista}` WHERE SAFE_CAST({idc} AS INT64) NOT IN ({excl})"
                      ).to_dataframe(create_bqstorage_client=False)["n"][0]
        print(f"{'✗' if faltan else '✓'} {vista}: {n:,} filas" + (f" · faltan columnas: {', '.join(faltan)}" if faltan else ""))
    det = cols.get("VTD10_student_progress_detail", set())
    falt = {"pedagogical_time", "component_category", "is_completed"} - det
    print("\nHoras de plataforma (pedagogical_time de recursos completados): "
          + ("✓ columnas presentes" if not falt else f"✗ faltan {', '.join(sorted(falt))}"))


if __name__ == "__main__":
    main()
