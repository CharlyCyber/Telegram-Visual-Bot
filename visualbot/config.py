"""Configuración compartida; los secretos se leen únicamente del entorno."""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")
CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1002700094661"))

FIRME = "\n\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ"

# Estados de la conversación
SELECCIONANDO = 11
SELECCIONANDO_TEMPORADA = 12

# --- Separadores visuales ---
SEP = "━━━━━━━━━━━━━━━━━━━━━━"
SEP_SOFT = "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
SEP_STAR = "･ﾟ✧ ━━━━━━━━━━━━━ ✧ﾟ･"

ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"]) if os.getenv("ADMIN_CHAT_ID") else None
