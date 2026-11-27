"""Cortes semanales de la DB Formación TCF10 (Cohorte 1 y 2): copia de cada archivo «como si se hubiera generado el
domingo a las 11:59 p. m.», congelada en valores, en la carpeta de cortes. Detalle en tcf10/cortes.py.

    python scripts/cortes_semanales.py                       # genera TODOS los domingos que falten (reconstrucción
                                                             # del pasado y, cada semana, el domingo que acaba de pasar)
    python scripts/cortes_semanales.py --corte 2026-11-22    # solo ese domingo (otra fecha = el domingo anterior)
    python scripts/cortes_semanales.py --corte 2026-11-22 --forzar   # lo rehace y manda el anterior a la papelera
    python scripts/cortes_semanales.py --listar              # solo muestra qué domingos tocan y cuáles ya están

Sin argumentos también lee CORTES_FECHA y CORTES_FORZAR (así lo llaman el Panel y GitHub Actions, que no pasan
argumentos). Lo corre el workflow .github/workflows/db_formacion_cortes.yml cada domingo a las 11:59 p. m.
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
    from tcf10 import cortes

    p = argparse.ArgumentParser()
    p.add_argument("--corte", default=os.getenv("CORTES_FECHA", "").strip() or None,
                   help="Solo el corte de ese domingo (AAAA-MM-DD). Por defecto, todos los que falten.")
    p.add_argument("--forzar", action="store_true",
                   default=os.getenv("CORTES_FORZAR", "").strip().lower() in {"1", "true", "si", "sí", "yes"},
                   help="Rehace el corte aunque ya exista (el anterior va a la papelera de la unidad compartida).")
    p.add_argument("--listar", action="store_true", help="Solo lista los domingos de cada cohorte y cuáles faltan.")
    a = p.parse_args()

    if a.listar:
        lista, hechos = cortes.estado(log=print)
        for c in lista:
            for f in c.domingos:
                ok = (c.sheet_id, f"{f:%Y-%m-%d}") in hechos
                print(f"  {'✔' if ok else '·'} {c.titulo} · semana {c.semana(f)} · domingo {f:%d/%m/%Y}")
        return 0

    resultados = cortes.generar(fecha=a.corte, forzar=a.forzar)
    cuenta: dict[str, int] = {}
    for r in resultados:
        cuenta["error" if "error" in r else r["estado"]] = cuenta.get("error" if "error" in r else r["estado"], 0) + 1
    print("Cortes: " + (", ".join(f"{k} {v}" for k, v in cuenta.items()) or "nada que generar"))
    return 1 if cuenta.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
