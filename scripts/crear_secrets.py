"""Genera .streamlit/secrets.toml a partir de credenciales.json (cuenta de servicio) para correr la app local.

    python scripts/crear_secrets.py credenciales.json

- No imprime la llave. El archivo generado y el .json están en .gitignore: nunca se suben al repo.
- Para Streamlit Cloud: abre el secrets.toml generado y pega TODO su contenido en Settings › Secrets.
- Sin sheet_id la app corre en modo «solo SIS» (la base son los estudiantes del SIS).
"""
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def toml_str(v: str) -> str:
    return json.dumps(v, ensure_ascii=False)  # comillas dobles y \n escapados: válido en TOML


def main() -> None:
    origen = Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "credenciales.json")
    sa = json.loads(origen.read_text(encoding="utf-8"))
    if sa.get("type") != "service_account":
        sys.exit("El archivo no es una llave de cuenta de servicio (type != service_account).")
    destino = RAIZ / ".streamlit" / "secrets.toml"
    if destino.exists() and "--forzar" not in sys.argv:
        sys.exit(f"{destino} ya existe. Usa --forzar para reemplazarlo.")
    lineas = [
        "[tcf10]",
        '# sheet_id = ""                               # cuando exista el Google Sheet operativo',
        'sis_dataset = "potent-poetry-284019.DVTD_SIS"',
        'bq_project = "potent-poetry-284019"         # la cuenta necesita BigQuery Job User aquí',
        "horas_por_sesion = 3.0",
        "divisor_time_view = 3600",
        "",
        "[gcp_service_account]",
        *[f"{k} = {toml_str(v)}" for k, v in sa.items()],
        "",
    ]
    destino.parent.mkdir(exist_ok=True)
    destino.write_text("\n".join(lineas), encoding="utf-8")
    print(f"OK: {destino.relative_to(RAIZ)} creado para {sa.get('client_email')}")
    print("Siguiente: streamlit run app.py")


if __name__ == "__main__":
    main()
