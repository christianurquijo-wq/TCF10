"""Valida unidades del SIS en el Sheet (solo cifras agregadas, sin datos personales).

    python scripts/validar_unidades_sheet.py <ID_SHEET_SIS> [credenciales.json]

1) course_time_view por estudiante: ¿segundos o minutos?  → divisor_time_view (3600 o 60)
2) Duración real de las sesiones                          → horas_por_sesion
"""
import json
import sys
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread.utils import DateTimeOption, ValueRenderOption

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tcf10.sis_sheet import _fecha, _num  # noqa: E402


def leer(libro, titulo, columnas):
    v = libro.worksheet(titulo).get_all_values(value_render_option=ValueRenderOption.unformatted,
                                               date_time_render_option=DateTimeOption.formatted_string)
    df = pd.DataFrame([(f + [""] * len(v[0]))[:len(v[0])] for f in v[1:]], columns=v[0])
    return df[columnas]


def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: python scripts/validar_unidades_sheet.py <ID_SHEET_SIS> [credenciales.json]")
    sa = json.loads(Path(sys.argv[2] if len(sys.argv) > 2 else "credenciales.json").read_text(encoding="utf-8"))
    gc = gspread.authorize(Credentials.from_service_account_info(
        sa, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]))
    libro = gc.open_by_key(sys.argv[1])

    pc = leer(libro, "VTD10_student_progress_per_course_summary", ["incremental", "course_time_view"])
    t = _num(pc["course_time_view"]).groupby(pc["incremental"]).sum()
    t = t[t > 0]
    print("1) course_time_view sumado por estudiante (solo quienes tienen tiempo):")
    print(f"   estudiantes: {len(t):,}")
    print(f"   crudo  p25 / mediana / p90 / máx: {t.quantile(.25):,.0f} / {t.median():,.0f} / "
          f"{t.quantile(.9):,.0f} / {t.max():,.0f}")
    print(f"   si son SEGUNDOS → horas mediana {t.median() / 3600:,.1f} · máx {t.max() / 3600:,.1f}")
    print(f"   si son MINUTOS  → horas mediana {t.median() / 60:,.1f} · máx {t.max() / 60:,.1f}")
    print("   (lo razonable hoy es entre 0 y ~60 h por estudiante)")

    ad = leer(libro, "VTD10_student_attendance_detail", ["session_id", "session_start_date", "session_end_date"])
    ad = ad.drop_duplicates("session_id")
    horas = ((_fecha(ad["session_end_date"]) - _fecha(ad["session_start_date"])).dt.total_seconds() / 3600).round(2)
    print("\n2) Duración de las sesiones (horas → cantidad de sesiones):")
    print(horas.value_counts().head(8).to_string())


if __name__ == "__main__":
    main()
