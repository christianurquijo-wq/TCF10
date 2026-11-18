"""Genera el bloque de Secrets para un usuario de la vista Atenea (usuario y contraseña).

    python scripts/crear_usuario_atenea.py

Pide usuario, nombre y contraseña (la contraseña no se muestra) e imprime el bloque TOML con el HASH,
listo para pegar en .streamlit/secrets.toml y en Streamlit Cloud › Settings › Secrets.
La contraseña nunca se guarda en texto plano.
"""
import getpass
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import hashlib  # noqa: E402


def hash_contrasena(contrasena: str, sal: bytes, iteraciones: int = 200_000) -> str:  # misma fórmula de acceso.py
    h = hashlib.pbkdf2_hmac("sha256", contrasena.encode("utf-8"), sal, iteraciones)
    return f"pbkdf2_sha256${iteraciones}${sal.hex()}${h.hex()}"


usuario = input("Usuario (ej. prueba.atenea): ").strip().lower()
if not re.fullmatch(r"[a-z0-9._-]{3,40}", usuario):
    sys.exit("Usuario inválido: usa letras minúsculas, números, punto, guion o guion bajo (3 a 40).")
nombre = input("Nombre para mostrar: ").strip() or usuario
clave = getpass.getpass("Contraseña (mínimo 10 caracteres): ")
if len(clave) < 10 or getpass.getpass("Repite la contraseña: ") != clave:
    sys.exit("La contraseña no coincide o es muy corta.")
print("\nPega esto en los Secrets:\n")
print(f'[atenea.usuarios."{usuario}"]')
print(f'nombre = "{nombre}"')
print(f'hash = "{hash_contrasena(clave, os.urandom(16))}"')
