"""
Talento Capital Formación 10 · enlace anterior del tablero interno.

Desde nov-2026 la app es UNA sola (atenea_app.py): vista Atenea por defecto y vista interna para los correos de
[atenea] internos. Este archivo solo la ejecuta, para que el enlace viejo siga funcionando (con inicio de sesión;
ya no muestra datos internos sin autenticar).
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parent / "atenea_app.py"), run_name="__main__")
