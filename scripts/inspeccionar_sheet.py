"""Muestra la estructura de un Google Sheet (pestañas, filas, columnas y % lleno) SIN imprimir datos.

    python scripts/inspeccionar_sheet.py <ID_DEL_SHEET> [credenciales.json]

Sirve para adaptar la app sin compartir datos personales: copia la salida y pégala en el chat.
Requisito: compartir el Sheet como Lector con el client_email de la cuenta de servicio.
"""
import json
import re
import sys
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials


def tipo(valores: list[str]) -> str:
    vals = [v for v in valores if v.strip()]
    if not vals:
        return "vacía"
    if all(re.fullmatch(r"-?\d+", v.replace(".", "").replace(",", "")) for v in vals):
        return "número"
    if all(re.fullmatch(r"-?[\d.,]+", v) for v in vals):
        return "decimal"
    if all(re.match(r"\d{1,4}[-/]\d{1,2}[-/]\d{1,4}", v) for v in vals):
        return "fecha"
    if all(v.upper() in {"TRUE", "FALSE", "VERDADERO", "FALSO", "SI", "NO", "SÍ", "0", "1"} for v in vals):
        return "sí/no"
    return f"texto ({len(set(vals))} distintos)"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Uso: python scripts/inspeccionar_sheet.py <ID_DEL_SHEET> [credenciales.json]")
    clave = sys.argv[1]
    llave = Path(sys.argv[2] if len(sys.argv) > 2 else "credenciales.json")
    sa = json.loads(llave.read_text(encoding="utf-8"))
    gc = gspread.authorize(Credentials.from_service_account_info(
        sa, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]))
    try:
        libro = gc.open_by_key(clave)
    except gspread.exceptions.APIError as e:
        sys.exit(f"Sin acceso ({e.response.status_code}). Comparte el Sheet como Lector con {sa['client_email']}")
    print(f"Sheet: {libro.title}")
    for ws in libro.worksheets():
        valores = ws.get_all_values()
        if not valores:
            print(f"\n## {ws.title}: vacía")
            continue
        enc, filas = valores[0], valores[1:]
        print(f"\n## {ws.title}: {len(filas):,} filas × {len(enc)} columnas")
        for i, nombre in enumerate(enc):
            col = [f[i] if i < len(f) else "" for f in filas]
            lleno = sum(1 for v in col if v.strip()) / len(col) if col else 0
            print(f"  - {nombre or '(sin nombre)'} | {tipo(col)} | {lleno:.0%} lleno")


if __name__ == "__main__":
    main()
