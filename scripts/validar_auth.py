"""Revisa el bloque [auth] de .streamlit/secrets.toml SIN mostrar secretos.

    python scripts/validar_auth.py

Imprime qué claves hay, el redirect_uri (no es secreto) y avisa lo que falta para que st.login funcione.
Para Streamlit Cloud: pega el mismo bloque en Settings › Secrets.
"""
import tomllib
from pathlib import Path

RUTA = Path(__file__).resolve().parent.parent / ".streamlit" / "secrets.toml"
OBLIGATORIAS = ["client_id", "client_secret", "server_metadata_url"]

s = tomllib.loads(RUTA.read_text(encoding="utf-8"))
auth = s.get("auth")
if auth is None:
    raise SystemExit("✖ No hay bloque [auth] en el nivel principal (¿quedó dentro de [tcf10]?).")
print("Claves en [auth]:", ", ".join(auth.keys()))
redirect = auth.get("redirect_uri", "")
print("redirect_uri:", redirect or "✖ FALTA")
if redirect and not redirect.endswith("/oauth2callback"):
    print("✖ redirect_uri debe terminar en /oauth2callback")
if redirect and "dash-general-tcf10.streamlit.app" not in redirect and "localhost" not in redirect:
    print("⚠ redirect_uri apunta a otra app: para Streamlit Cloud debe ser "
          "https://dash-general-tcf10.streamlit.app/oauth2callback")
cs = auth.get("cookie_secret", "")
print("cookie_secret:", f"{len(cs)} caracteres" if cs else "✖ FALTA")
proveedores = {k: v for k, v in auth.items() if isinstance(v, dict)}
bloques = proveedores or {"(plano)": auth}
for nombre, b in bloques.items():
    faltan = [k for k in OBLIGATORIAS if not b.get(k)]
    print(f"Proveedor {nombre}:", "✔ completo" if not faltan else "✖ faltan " + ", ".join(faltan))
    if b.get("server_metadata_url") and "accounts.google.com" not in b["server_metadata_url"]:
        print("  ⚠ server_metadata_url no es el de Google: "
              "https://accounts.google.com/.well-known/openid-configuration")
try:
    import authlib  # noqa: F401
    print("Authlib instalado ✔")
except ImportError:
    print("✖ Falta Authlib: pip install Authlib")
