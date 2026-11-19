"""Configuración compartida; los secretos se leen únicamente del entorno."""
import os
from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return max(minimum, value)


BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
CHAT_ID = int(os.environ["GROUP_CHAT_ID"]) if os.getenv("GROUP_CHAT_ID") else None

FIRME = "\n\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ"

# Estados de la conversación
SELECCIONANDO = 11
SELECCIONANDO_TEMPORADA = 12

# --- Separadores visuales ---
SEP = "━━━━━━━━━━━━━━━━━━━━━━"
SEP_SOFT = "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
SEP_STAR = "･ﾟ✧ ━━━━━━━━━━━━━ ✧ﾟ･"

ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"]) if os.getenv("ADMIN_CHAT_ID") else None

# URL pública externa para auto-ping 24/7 (Render y Hugging Face Spaces la rellenan si no se define PUBLIC_URL).
_space_host = (os.getenv("SPACE_HOST") or "").strip()
_default_public = f"https://{_space_host}" if _space_host else ""
PUBLIC_URL = (
    os.getenv("PUBLIC_URL") or os.getenv("RENDER_EXTERNAL_URL") or _default_public
).strip().rstrip("/")

# Intervalo del auto-ping interno a /health en segundos (0 lo desactiva; por defecto 300 s = 5 min).
SELF_PING_INTERVAL = _env_int("SELF_PING_INTERVAL", 300, minimum=0)
