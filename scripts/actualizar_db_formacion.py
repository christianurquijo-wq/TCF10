"""Actualiza la DB Formación TCF10 de cada cohorte con los datos del tablero (grupo, fechas, horas y % de avance) y,
después, las tablas del Looker de Atenea (tcf10/looker.py) en el Sheet «TCF10 · Datos Looker Atenea».

    python scripts/actualizar_db_formacion.py               # desde la raíz del repo (lee .streamlit/secrets.toml)
    python scripts/actualizar_db_formacion.py --corte 2026-11-30
    python scripts/actualizar_db_formacion.py --solo-looker  # solo las tablas del Looker

Lo corren el cron de GitHub Actions (.github/workflows/db_formacion_cron.yml), el botón del panel de operaciones y
el botón «Actualizar bases de formación» de la vista interna. Detalle en tcf10/db_formacion.py.
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
os.chdir(RAIZ)                      # st.secrets lee .streamlit/secrets.toml desde la carpeta actual
sys.path.insert(0, str(RAIZ))
warnings.filterwarnings("ignore")


def main() -> int:
    import logging
    logging.getLogger("streamlit").setLevel(logging.ERROR)
    import pandas as pd
    from tcf10 import db_formacion

    p = argparse.ArgumentParser()
    p.add_argument("--corte", help="Fecha para la semana de la cohorte (AAAA-MM-DD). Por defecto, hoy.")
    p.add_argument("--solo-looker", action="store_true", help="solo las tablas del Looker de Atenea")
    p.add_argument("--sin-looker", action="store_true", help="solo la DB Formación")
    a = p.parse_args()
    hoy = pd.Timestamp(a.corte) if a.corte else None
    fallas = 0
    if not a.solo_looker:
        resultados = db_formacion.actualizar_todo(hoy)
        errores = [r for r in resultados if "error" in r]
        print(f"DB Formación: {len(resultados) - len(errores)} archivo(s) actualizados, {len(errores)} con error.")
        fallas += 1 if errores or not resultados else 0
    if not a.sin_looker:
        # Tablas del Looker de Atenea: mismas cifras de la vista Atenea (tcf10/looker.py)
        from tcf10 import looker
        try:
            r = looker.actualizar(hoy)
            print(f"Looker Atenea: {r.pop('archivo')} · " + ", ".join(f"{k} {v}" for k, v in r.items()))
        except Exception as e:  # noqa: BLE001 -- la DB Formación ya quedó; se informa y se marca la falla
            print(f"ERROR Looker Atenea: {type(e).__name__}: {str(e)[:300]}")
            fallas += 1
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
