import os
import asyncio
import httpx
import re
import logging
import http.server
import socketserver
import threading
from dotenv import load_dotenv
from telegram import Update, ChatMember
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from bs4 import BeautifulSoup
from functools import wraps
from time import time

# Cargar variables de entorno
load_dotenv()


class TTLCache:
    def __init__(self, ttl_seconds: int = 300):
        self.cache = {}
        self.ttl = ttl_seconds

    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            key = (func.__name__, args, tuple(sorted(kwargs.items())))
            now = time()
            if key in self.cache and now - self.cache[key]['time'] < self.ttl:
                return self.cache[key]['value']
            result = await func(*args, **kwargs)
            self.cache[key] = {'value': result, 'time': now}
            return result
        return wrapper


# --- Configuración y Constantes ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY")  # Movido aquí para consistencia
CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1002700094661"))

FIRME = os.getenv("SIGNATURE", "\n\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ")

# Estados de la conversación
SELECCIONANDO = 11

# --- SISTEMA ANTISPAM MEJORADO ---

# Palabras clave de spam (en minúsculas) - VERSIÓN MEJORADA
SPAM_KEYWORDS = [
    # Criptomonedas/Casino
    "eth libre",
    "Ethereum gratis",
    "jetacas",
    "casino",
    "bonificación",
    "código promocional",
    "bienvenido1k",
    "lanzamiento aéreo",
    "cripto",
    "cartera",
    "btc",
    "bitcoin",
    "freeether.net",
    "eth alerta",
    "etéreo",
    "bono instantáneo",
    "plataforma con licencia",
    "apuesta",
    "retirar",
    "depósito",
    "tragaperras",
    "póker",
    "ruleta",
    "blackjack",
    "bingo",
    "lotería",
    "jackpot",
    "giros gratis",
    "registro",
    "verificación",
    "sin identificación",
    "instantáneo",
    "24/7 soporte",
    "mínimo depósito",
    "pagos justos",
    "retiros rápidos",
    "seguro",
    "tarjetas",
    "e-wallets",
    "live casino",
    "online casino",
    "online gambling",
    "online betting",
    "slots",
    "poker",
    "roulette",
    "free spins",
    "welcome bonus",
    "deposit bonus",
    "no strings attached",
    "no id required",
    "instant bonus activation",
    "top-tier providers",
    "licensed platform",
    "fair payouts",

    # Términos financieros sospechosos
    "ganar dinero",
    "dinero gratis",
    "dinero fácil",
    "ingresos pasivos",
    "inversión",
    "ganancia",
    "roi",
    "comercio",
    "forex",
    "binario",
    "ganador",
    "premio",
    "recompensa",
    "regalo",
    "sin tarifas",
    "libre de riesgos",
    "garantizado",

    # Llamadas a la acción urgentes
    "haga clic aquí",
    "visitar",
    "regístrate ahora",
    "registrarse",
    "actúa ahora",
    "fecha prisa",
    "tiempo limitado",
    "no te lo pierdas",
    "exclusivo",
    "instante",
    "por tiempo limitado",
    "no dura para siempre",
    "lanzamiento aire limitado",
    "reclama ahora",

    # URLs y entrelaza sospechosos
    "telegrama.yo",
    "t.me",
    "enlace",
    "url",

    # Términos de marketing agresivo
    "oferta",
    "trato",
    "trabajar desde casa",
    "mlm",
    "pirámide",
    "Soporte 24 horas al día, 7 días a la semana",
    "depósito mío",
    "retiros",
    "carteras eléctricas",
    "se requiere verificación",
    "sin condiciones",
    "implementar registro",
    "conecta tu billetera",
    "verificar",
    "el equilibrio cree"
]

# URLs sospechosas - VERSIÓN MEJORADA
SPAM_URLS = [
    "jetacas.com", "freeether.net", "freecrypto", "lanzamiento aéreo",
    "reclamar dinero", "gana", "bitcoins de Pecar", "cryptogift", "freetokens",
    "casino", "bonificación", "promoción", "reclamar", "gratis", "ganar",
    "dinero", "jetacas.com", "freeether.net", "onlinecasino.com",
    "gamblingsite.net", "bettingplatform.org"
]

# Patrones de emojis sospechosos
SPAM_EMOJI_PATTERNS = [
    "🚨", "💰", "🔥", "🔑", "📥", "🔒", "⚡️", "🎮", "🕐", "💵", "✅", "💳", "🤑", "⚡️",
    "⏳", "👉", "🟢", "🎰", "🎲", "👑", "💎"
]


def is_spam_message(texto: str) -> bool:
    """Detecta si un mensaje es spam - VERSIÓN SUPER MEJORADA"""
    if not texto:
        return False

    texto_inferior = texto.lower()

    # 1. Palabras clave con regex (coincidencia exacta de palabras)
    spam_count = 0
    for palabra_clave in SPAM_KEYWORDS:
        if re.search(rf"\b{re.escape(palabra_clave)}\b", texto_inferior):
            spam_count += 1

    # 2. URL con expresiones regulares
    is_spam_url = False
    for url in SPAM_URLS:
        if url in texto_inferior:
            is_spam_url = True
            break

    # 3. Nombres específicos de casinos y términos relacionados
    nombres_casino = [
        "jetacas", "casino", "online casino", "online gambling",
        "online betting", "freeether.net"
    ]
    has_casino_name = any(
        re.search(rf"\b{nombre}\b", texto_inferior)
        for nombre in nombres_casino)

    # 4. Patrones de spam de casino específicos
    patron_casino_especifico = re.search(
        r"(\b(?:jetacas|casino|online casino|online gambling|online betting)\b.*(?:bonus|promo|free spins|launch bonus)|\$1000.*bonus.*promo|\b(?:no id|no verification) required)",
        texto_inferior)

    # 5. Combinación de elementos (emojis + palabras clave de casino/bono + URL)
    has_spam_combo = (
        sum(1 for emoji in SPAM_EMOJI_PATTERNS if emoji in texto) >= 2
        and  # Al menos 2 emojis sospechosos
        any(palabra_clave in texto_inferior for palabra_clave in [
            "casino", "bonificación", "promoción", "jetacas", "bonus",
            "promo code"
        ]) and
        ("jetacas.com" in texto_inferior or "t.me" in texto_inferior
         or "telegram.me" in texto_inferior or "http" in texto_inferior))

    # 6. Estructura de spam (múltiples líneas con emojis)
    lineas = texto.split('\n')
    lineas_emoji = sum(1 for linea in lineas
                       if any(emoji in linea for emoji in SPAM_EMOJI_PATTERNS))
    has_spam_structure = lineas_emoji >= 4

    # 7. Verificar longitud excesiva (spam típico es muy largo)
    is_too_long = len(
        texto) > 250  # Ajustado a 250 para ser más sensible

    # 8. Detección de mayúsculas excesivas (indicador de spam)
    mayusculas_count = sum(1 for char in texto if char.isupper())
    total_letras = sum(1 for char in texto if char.isalpha())
    has_suspicious_caps = False
    if total_letras > 0:
        porcentaje_mayusculas = (mayusculas_count / total_letras) * 100
        if porcentaje_mayusculas > 50 and len(
                texto) > 50:  # Más del 50% de mayúsculas en mensajes largos
            has_suspicious_caps = True

    # Condiciones de detección (más restricciones)
    return (spam_count >= 3 or  # Aumentado a 3 para mayor precisión
            is_spam_url or has_casino_name or
            patron_casino_especifico is not None or has_spam_combo or
            (has_spam_structure and spam_count >= 1) or
            (is_too_long
             and spam_count >= 1) or has_suspicious_caps)


# --- Funciones de Utilidad ---
async def is_user_in_group(context: ContextTypes.DEFAULT_TYPE,
                           user_id: int) -> bool:
    """Verifica si un usuario es miembro del grupo especificado"""
    try:
        chat_member = await context.bot.get_chat_member(CHAT_ID, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error verificando membresía del usuario {user_id}: {e}")
        return False  # Denegar acceso cuando hay errores


# --- Diccionarios de Emojis ---

genero_emojis_dict = {
    'Acción': '🔥',
    'Aventura': '🗺️',
    'Animación': '🎨',
    'Comedia': '😂',
    'Crimen': '🕵️',
    'Documental': '🎥',
    'Drama': '🎭',
    'Familia': '👨‍👩‍👧‍👦',
    'Fantasía': '🧚',
    'Historia': '📜',
    'Terror': '👻',
    'Música': '🎵',
    'Misterio': '🕵️‍♂️',
    'Romance': '❤️',
    'Ciencia ficción': '🤖',
    'Película de TV': '📺',
    'Suspense': '😱',
    'Bélica': '⚔️',
    'Western': '🤠',
    'Ballet': '🩰',
    'Deportes': '🏅',
    'Aviación': '✈️',
    'Superhéroes': '🦸',
}

title_keyword_emojis = {
    'luna': '🌙', 'espacio': '🚀', 'estrella': '⭐', 'mar': '🌊', 'amor': '❤️',
    'avión': '✈️', 'fuego': '🔥', 'guerra': '⚔️', 'robot': '🤖', 'fantasma': '👻',
    'música': '🎵', 'superhéroe': '🦸', 'deporte': '🏅', 'misterio': '🕵️',
    'terror': '👻', 'comedia': '😂', 'drama': '🎭', 'historia': '📜',
    'fantasía': '🧚', 'familia': '👨‍👩‍👧‍👦', 'dragón': '🐉', 'magia': '✨',
    'aventura': '🗺️', 'crimen': '🕵️‍♂️', 'suspenso': '😱', 'animación': '🎨',
    'perro': '🐶', 'gato': '🐱', 'viaje': '✈️', 'tiempo': '⏳', 'muerte': '💀',
    'vida': '🌱', 'mundo': '🌍', 'batalla': '⚔️', 'poder': '⚡', 'secreto': '🤫',
    'ninja': '🥷', 'samurai': '⚔️', 'pirata': '🏴‍☠️', 'caballero': '🛡️', 'rey': '👑',
    'reina': '👑', 'princesa': '👸', 'príncipe': '🤴', 'mago': '🧙', 'bruja': '🧙‍♀️',
    'vampiro': '🧛', 'demonio': '😈', 'ángel': '😇', 'zombie': '🧟', 'monstruo': '👹',
    'coche': '🚗', 'moto': '🏍️', 'cohete': '🚀', 'planeta': '🪐', 'universo': '🌌',
    'montaña': '⛰️', 'volcán': '🌋', 'desierto': '🏜️', 'bosque': '🌲', 'ciudad': '🏙️',
    'castillo': '🏰', 'cueva': '🕳️', 'tesoro': '💎', 'espada': '⚔️', 'escudo': '🛡️',
    'libro': '📚', 'mapa': '🗺️', 'brújula': '🧭', 'reloj': '⏰', 'llave': '🔑',
    'fútbol': '⚽', 'boxeo': '🥊', 'lucha': '🥊', 'carrera': '🏎️', 'surf': '🏄',
    'guerrero': '⚔️', 'soldado': '🎖️', 'espía': '🕵️‍♂️', 'policía': '👮', 'piloto': '✈️',
    'médico': '👨‍⚕️', 'abogado': '👨‍⚖️', 'científico': '🔬', 'explorador': '🗺️', 'tesoro': '💎',
    'venganza': 'venge', 'traición': '🐍', 'redención': '🙏', 'destino': '🔮', 'guerra': '⚔️',
    'paz': '☮️', 'amor': '❤️', 'odio': '💔', 'muerte': '💀', 'vida': '🌱',
    'sueño': '💤', 'pesadilla': '😱', 'magia': '✨', 'hechizo': '🧙', 'poción': '🧪',
    'corona': '👑', 'trono': '🪑', 'reino': '🏰', 'imperio': '🏛️', 'batalla': '⚔️',
    'espada': '⚔️', 'arco': '🏹', 'bomba': '💣', 'pistola': '🔫', 'cuchillo': '🔪',
    'escudo': '🛡️', 'armadura': '🛡️', 'casco': '⛑️', 'hacha': '🪓', 'lanza': '🗡️',
    'dragon': '🐉', 'fénix': '🔥', 'unicornio': '🦄', 'grifo': '🦅', 'hidra': '🐉',
    'lobo': '🐺', 'oso': '🐻', 'león': '🦁', 'tigre': '🐅', 'águila': '🦅',
    'ballena': '🐋', 'tiburón': '🦈', 'pulpo': '🐙', 'serpiente': '🐍', 'araña': '🕷️',
    'robó': '🤖', 'cyborg': '🤖', 'android': '🤖', 'alien': '👽', 'UFO': '🛸',
    'nave': '🚀', 'estación espacial': '🛰️', 'laboratorio': '🔬', 'invento': '💡', 'futuro': '🔮',
    'pasado': '🕰️', 'tiempo': '⏳', 'viaje en el tiempo': '⏰', 'realidad virtual': '🥽', 'simulación': '💻',
    'internet': '🌐', 'hacker': '💻', 'virus': '🦠', 'inteligencia artificial': '🤖', ' IA ': '🤖',
    'asesino': '🔪', 'detective': '🕵️‍♂️', 'crimen': '🕵️', 'misterio': '🕵️', 'secreto': '🤫',
    'conspiración': '🤫', 'espionaje': '🕵️‍♂️', 'traición': '🐍', 'mента': '💰', 'droga': '💊',
    'ladrón': '🦹', 'atracón': '💰', 'robo': '💰', 'hurto': '💰', 'estafa': '💰',
    'coche de policía': '🚔', 'ambulancia': '🚑', 'bombero': '🚒', 'helicoptero': '🚁', 'submarino': '🚢',
    'tren': '🚂', 'barco': '🚢', 'avión': '✈️', 'cohete': '🚀', 'nave espacial': '🚀',
    'comida': '🍔', 'restaurante': '🍽️', 'cocina': '👨‍🍳', 'chef': '👨‍🍳', 'café': '☕',
    'cerveza': '🍺', 'vino': '🍷', 'cóctel': '🍸', 'baile': '💃', 'fiesta': '🎉',
    'concierto': '🎵', 'festival': '🎪', 'carnaval': '🎭', 'máscara': '🎭', 'payaso': '🤡',
    'circo': '🎪', 'magia': '✨', 'ilusión': '✨', 'truco': '✨', 'truco': '✨',
    'escuela': '🏫', 'universidad': '🎓', 'biblioteca': '📚', 'museo': '🏛️', 'teatro': '🎭',
    'cine': '🎬', 'televisión': '📺', 'radio': '📻', 'periodista': '📰', 'reportero': '📰',
    'deportes': '🏅', 'campeonato': '🏆', 'medalla': '🥇', 'copa': '🏆', 'torneo': '🏆',
    'fútbol': '⚽', 'baloncesto': '🏀', 'tenis': '🎾', 'golf': '⛳', 'natación': '🏊',
    'esquí': '🎿', 'surf': '🏄', 'boxeo': '🥊', 'artes marciales': '🥋', 'carrera': '🏎️',
    'aventura': '🗺️', 'exploración': '🧭', 'descubrimiento': '🔍', 'expedición': '🧭', 'mapa': '🗺️',
    'tesoro': '💎', 'pirata': '🏴‍☠️', 'tesoro escondido': '💎', 'cofre': '📦', 'moneda': '🪙',
    'medieval': '⚔️', 'caballero': '🛡️', 'castillo': '🏰', 'reino': '🏰', 'princesa': '👸',
    'dragón': '🐉', 'mago': '🧙', 'espada': '⚔️', 'armadura': '🛡️', 'corona': '👑',
    'espacial': '🚀', 'alienígena': '👽', 'planeta': '🪐', 'galaxia': '🌌', 'universo': '🌌',
    'nave': '🚀', 'estación espacial': '🛰️', 'astronauta': '🧑‍🚀', 'cosmonauta': '🧑‍🚀', 'cometa': '☄️',
    'apocalipsis': '💥', 'post-apocalíptico': '☢️', 'zombie': '🧟', 'virus': '🦠', 'pandemia': '🦠',
    'catástrofe': '💥', 'terremoto': '🌋', 'tsunami': '🌊', 'tormenta': '⛈️', 'inundación': '🌊',
    'romance': '❤️', 'comedia': '😂', 'drama': '🎭', 'thriller': '😱', 'horror': '👻',
    'ciencia ficción': '🚀', 'fantasía': '🧚', 'western': '🤠', 'bélico': '⚔️', 'musical': '🎵',
    'documental': '🎥', 'biopic': '🎭', 'noir': '🕵️', 'slasher': '🔪', 'whodunit': '🕵️',
}

synopsis_keyword_emojis = {
    'asesino': '🔪', 'misterio': '🕵️', 'amor': '❤️', 'guerra': '⚔️', 'espacio': '🚀',
    'luna': '🌙', 'robot': '🤖', 'futuro': '🔮', 'ballet': '🩰', 'familia': '👨‍👩‍👧‍👦',
    'venganza': 'venge', 'crimen': '🕵️', 'viaje': '✈️', 'mar': '🌊', 'monstruo': '👹',
    'música': '🎵', 'superhéroe': '🦸', 'magia': '✨', 'batalla': '⚔️', 'sueño': '💤',
    'dinero': '💰', 'rescate': '🆘', 'explosión': '💥', 'coche': '🚗', 'dragón': '🐉',
    'fuego': '🔥', 'espada': '⚔️', 'reino': '🏰', 'bosque': '🌲', 'ciudad': '🏙️',
    'policía': '👮', 'detective': '🕵️‍♂️', 'prisión': '⛓️', 'huida': '🏃',
    'secreto': '🤫', 'traición': '🐍', 'amistad': '🤝', 'escuela': '🏫',
    'universidad': '🎓', 'tecnología': '💻', 'virus': '🦠', 'zombie': '🧟',
    'alienígena': '👽', 'planeta': '🪐', 'tiempo': '⏳', 'pasado': '🕰️',
    'ninja': '🥷', 'samurai': '⚔️', 'pirata': '🏴‍☠️', 'caballero': '🛡️', 'rey': '👑',
    'reina': '👑', 'princesa': '👸', 'príncipe': '🤴', 'mago': '🧙', 'bruja': '🧙‍♀️',
    'vampiro': '🧛', 'hombre lobo': '🐺', 'demonio': '😈', 'ángel': '😇', 'muerto': '💀',
    'lucha': '🥊', 'boxeo': '🥊', 'fútbol': '⚽', 'baloncesto': '🏀', 'tenis': '🎾',
    'carrera': '🏎️', 'coche': '🚗', 'moto': '🏍️', 'avión': '✈️', 'cohete': '🚀',
    'oceano': '🌊', 'río': '🏞️', 'montaña': '⛰️', 'volcán': '🌋', 'desierto': '🏜️',
    'bosque': '🌲', 'jungla': '🌴', 'ciudad': '🏙️', 'pueblo': '🏘️', 'castillo': '🏰',
    'torre': '🗼', 'puente': '🌉', 'templo': '⛩️', 'pirámide': '🏛️', 'cueva': '🕳️',
    'tesoro': '💎', 'oro': '🥇', 'corona': '👑', 'trono': '🪑', 'espada': '⚔️',
    'escudo': '🛡️', 'arco': '🏹', 'flecha': '🏹', 'bomba': '💣', 'pistola': '🔫',
    'cuchillo': '🔪', 'lanza': '🗡️', 'armadura': '🛡️', 'casco': '⛑️', 'hacha': '🪓',
    'libro': '📚', 'mapa': '🗺️', 'brújula': '🧭', 'reloj': '⏰', 'calendario': '📅',
    'carta': '✉️', 'sobre': '💌', 'regalo': '🎁', 'caja': '📦', 'llave': '🔑',
    'cerradura': '🔒', 'candado': '🔒', 'cadena': '⛓️', 'puerta': '🚪',
    'escalera': '🪜', 'ascensor': '🛗', 'camión': '🚚', 'autobús': '🚌',
    'tren': '🚂', 'barco': '🚢', 'helicóptero': '🚁',
    'bicicleta': '🚲', 'moto': '🏍️', 'surf': '🏄',
    'esquí': '🎿', 'snowboard': '🏂', 'paracaídas': '🪂',
    'fuego': '🔥', 'humo': '💨', 'niebla': '🌫️', 'lluvia': '🌧️', 'nieve': '❄️',
    'hielo': '🧊', 'rayo': '⚡', 'arcoíris': '🌈', 'sol': '☀️',
    'luna': '🌙', 'estrella': '⭐', 'cometa': '☄️', 'meteorito': '☄️',
    'aurora': '🌌', 'galaxia': '🌌', 'universo': '🌌', 'nebulosa': '🌌',
    'cielo': '🌤️', 'nube': '☁️', 'tormenta': '⛈️', 'viento': '💨', 'tornado': '🌪️',
    'huracán': '🌀', 'tsunami': '🌊', 'terremoto': '🌋', 'inundación': '🌊',
    'incendio': '🔥', 'colisión': '💥', 'golpe': '👊', 'puñetazo': '👊',
    'abrazo': '🤗', 'beso': '💋', 'sonrisa': '😊', 'risa': '😂', 'llanto': '😢',
    'susto': '😱', 'sorpresa': '😲', 'enfado': '😠', 'tristeza': '😢', 'alegría': '😄',
    'amor': '❤️', 'odio': '💔', 'amistad': '🤝', 'enemistad': '⚔️', 'alianza': '🤝',
    'traición': '🐍', 'perdón': '🙏', 'esperanza': '🌟', 'fe': '🙏',
    'miedo': '😱', 'valor': '💪', 'sabiduría': '🧠', 'fuerza': '💪',
    'velocidad': '⚡', 'agilidad': '🏃', 'resistencia': '💪', 'flexibilidad': '🧘',
    'paz': '☮️', 'guerra': '⚔️', 'batalla': '⚔️', 'lucha': '🥊', 'combate': '⚔️',
    'duelo': '⚔️', 'rivalidad': '⚔️', 'competencia': '🏆', 'campeonato': '🏆',
    'torneo': '🏆', 'copa': '🏆', 'medalla': '🥇', 'podio': '🏆',
    'trofeo': '🏆', 'premio': '🎁', 'recompensa': '🎁', 'sorpresa': '🎁',
    'misterio': '🕵️', 'secreto': '🤫', 'acertijo': '🧩', 'puzzle': '🧩',
    'búsqueda': '🔍', 'investigación': '🔍', 'descubrimiento': '🔍',
    'ciencia': '🔬', 'experimento': '🧪', 'laboratorio': '🔬', 'invento': '💡',
    'tecnología': '💻', 'computadora': '💻', 'internet': '🌐', 'robot': '🤖',
    'futuro': '🔮', 'pasado': '🕰️', 'presente': '⏳', 'tiempo': '⏳', 'historia': '📜',
    'leyenda': '📜', 'mito': '📜', 'cuento': '📖', 'novela': '📖', 'libro': '📚',
    'biblioteca': '📚', 'escritor': '✍️', 'escritura': '✍️',
    'pintura': '🎨', 'artista': '🎨', 'música': '🎵', 'músico': '🎸', 'cantante': '🎤',
    'baile': '💃', 'danza': '💃', 'teatro': '🎭', 'actor': '🎭',
    'película': '🎬', 'cine': '🎬', 'serie': '📺', 'televisión': '📺',
    'juego': '🎮', 'videojuego': '🎮', 'deporte': '🏅', 'atleta': '🏅',
    'guerrero': '⚔️', 'soldado': '🎖️', 'general': '🎖️', 'capitán': '🎖️',
    'rey': '👑', 'reina': '👑', 'príncipe': '🤴', 'princesa': '👸', 'noble': '👑',
    'campesino': '👨‍🌾', 'granjero': '👨‍🌾', 'aldeano': '🏘️', 'ciudadano': '🏙️',
    'viajero': '✈️', 'explorador': '🗺️', 'aventurero': '🗺️', 'pionero': '🗺️',
    'pirata': '🏴‍☠️', 'corsario': '🏴‍☠️', 'bucanero': '🏴‍☠️', 'tesoro': '💎', 'botín': '💰',
    'dinero': '💰', 'riqueza': '💰', 'fortuna': '💰', 'herencia': '💰',
    'familia': '👨‍👩‍👧‍👦', 'padre': '👨', 'madre': '👩', 'hijo': '👦', 'hija': '👧',
    'hermano': '👦', 'hermana': '👧', 'abuelo': '👴', 'abuela': '👵',
    'esposo': '👨', 'esposa': '👩', 'novio': '👦', 'novia': '👧', 'amigo': '🤝',
    'enemigo': '⚔️', 'rival': '⚔️', 'aliado': '🤝', 'compañero': '🤝',
    'maestro': '🧑‍🏫', 'alumno': '🧑‍🎓', 'estudiante': '🧑‍🎓', 'profesor': '🧑‍🏫',
    'médico': '👨‍⚕️', 'enfermera': '👩‍⚕️', 'hospital': '🏥', 'ambulancia': '🚑',
    'policía': '👮', 'detective': '🕵️‍♂️', 'agente': '🕵️‍♂️', 'espía': '🕵️‍♂️',
    'abogado': '👨‍⚖️', 'juez': '👨‍⚖️', 'criminal': '😈', 'preso': '⛓️',
    'prisión': '⛓️', 'cárcel': '⛓️', 'celda': '⛓️', 'juicio': '⚖️',
    'comida': '🍔', 'restaurante': '🍽️', 'cocina': '👨‍🍳', 'chef': '👨‍🍳',
    'pizza': '🍕', 'sushi': '🍣', 'taco': '🌮', 'hamburguesa': '🍔',
    'café': '☕', 'cerveza': '🍺', 'vino': '🍷', 'cóctel': '🍸',
    'postre': '🍰', 'pastel': '🎂', 'helado': '🍦', 'chocolate': '🍫',
    'fruta': '🍎', 'manzana': '🍎', 'naranja': '🍊', 'fresa': '🍓',
    'verdura': '🥬', 'tomate': '🍅', 'cebolla': '🧅', 'chile': '🌶️',
    'pan': '🍞', 'queso': '🧀', 'carne': '🥩', 'pollo': '🍗', 'pescado': '🐟',
    'amor': '❤️', 'corazón': '💔', 'boda': '💒', 'anillo': '💍', 'beso': '💋',
    'romance': '❤️', 'pareja': '💑', 'noviazgo': '💑', 'matrimonio': '💒',
    'bebé': '👶', 'embarazo': '🤰', 'parto': '👶', 'criatura': '👶',
    'niño': '👦', 'niña': '👧', 'adolescente': '🧑', 'adulto': '🧑', 'anciano': '👴',
    'mascota': '🐶', 'perro': '🐶', 'gato': '🐱', 'pájaro': '🐦', 'pez': '🐟',
    'caballo': '🐴', 'vaca': '🐄', 'cerdo': '🐷', 'oveja': '🐑', 'gallina': '🐔',
    'árbol': '🌳', 'flor': '🌸', 'planta': '🌱', 'hoja': '🍃', 'raíz': '🌱',
    'jardín': '🌻', 'bosque': '🌲', 'selva': '🌴', 'campo': '🌾', 'pradera': '🌿',
    'montaña': '⛰️', 'colina': '⛰️', 'valle': '🏞️', 'río': '🏞️', 'lago': '🏞️',
    'mar': '🌊', 'océano': '🌊', 'playa': '🏖️', 'isla': '🏝️', 'costa': '🏖️',
    'desierto': '🏜️', 'nieve': '❄️', 'hielo': '🧊', 'volcán': '🌋',
    'sol': '☀️', 'luna': '🌙', 'estrella': '⭐', 'cielo': '🌤️', 'nube': '☁️',
    'lluvia': '🌧️', 'viento': '💨', 'tormenta': '⛈️', 'trueno': '⚡', 'rayo': '⚡',
    'fuego': '🔥', 'agua': '💧', 'tierra': '🌍', 'aire': '💨',
    'diamante': '💎', 'oro': '🥇', 'plata': '🥈', 'bronce': '🥉',
    'perla': '⚪', 'cristal': '💎', 'rubi': '🔴', 'zafiro': '🔵', 'esmeralda': '🟢',
    'roca': '🪨', 'piedra': '🪨', 'madera': '🪵', 'metal': '⚙️', 'hierro': '⚙️',
    'fuerza': '💪', 'velocidad': '⚡', 'poder': '⚡', 'energía': '⚡', 'electricidad': '⚡',
    'inteligencia': '🧠', 'sabiduría': '🧠', 'conocimiento': '📚', 'educación': '🎓',
    'ciencia': '🔬', 'tecnología': '💻', 'invento': '💡', 'descubrimiento': '🔍',
    'arte': '🎨', 'música': '🎵', 'pintura': '🎨', 'escultura': '🗿', 'fotografía': '📷',
    'baile': '💃', 'teatro': '🎭', 'cine': '🎬', 'literatura': '📚', 'poesía': '📝',
    'comida': '🍔', 'bebida': '🥤', 'cerveza': '🍺', 'vino': '🍷', 'café': '☕',
    'deporte': '🏅', 'juego': '🎮', 'competencia': '🏆', 'campeonato': '🏆',
    'viaje': '✈️', 'aventura': '🗺️', 'exploración': '🧭', 'descubrimiento': '🔍',
    'guerra': '⚔️', 'paz': '☮️', 'batalla': '⚔️', 'combate': '⚔️', 'lucha': '🥊',
    'amor': '❤️', 'odio': '💔', 'amistad': '🤝', 'enemistad': '⚔️', 'familia': '👨‍👩‍👧‍👦',
    'miedo': '😱', 'alegría': '😄', 'tristeza': '😢', 'enfado': '😠', 'sorpresa': '😲',
    'esperanza': '🌟', 'fe': '🙏', 'perdón': '🙏', 'venganza': 'venge', 'redención': '🙏',
    'destino': '🔮', 'suerte': '🍀', 'milagro': '✨', 'magia': '✨', 'hechizo': '🧙',
    'sueño': '💤', 'pesadilla': '😱', 'alucinación': '🤪', 'delirio': '🤪',
    'locura': '🤪', 'razón': '🧠', 'verdad': '✅', 'mentira': '🤥', 'secreto': '🤫',
}

# --- Funciones de Formato de Texto ---


def get_genre_emojis(genres):
    return ' '.join(sorted({genero_emojis_dict.get(g, '🎬') for g in genres}))


def get_keyword_emojis(title):
    t = title.lower()
    return ' '.join({e for k, e in title_keyword_emojis.items() if k in t})


def get_synopsis_with_emojis(synopsis):
    if not synopsis:
        return ''
    synopsis_lower = synopsis.lower()
    found_emojis = []
    for keyword, emoji in synopsis_keyword_emojis.items():
        if keyword in synopsis_lower and emoji not in found_emojis:
            found_emojis.append(emoji)
            if len(found_emojis) >= 8: # Aumentado para mejor distribución
                break
    
    if not found_emojis:
        return synopsis

    # Distribuir emojis: inicio, medio y fin
    n = len(found_emojis)
    start_emojis = ' '.join(found_emojis[:n//3])
    mid_emojis = ' '.join(found_emojis[n//3:2*n//3])
    end_emojis = ' '.join(found_emojis[2*n//3:])

    # Insertar en el medio (aproximadamente)
    mid_point = len(synopsis) // 2
    # Buscar el espacio más cercano para no romper palabras
    space_idx = synopsis.find(' ', mid_point)
    if space_idx == -1: space_idx = mid_point

    result = f"{start_emojis} {synopsis[:space_idx]} {mid_emojis} {synopsis[space_idx:]} {end_emojis}"
    return result.strip()


def get_dynamic_closing():
    return "🤖 Automatización creada por Charli AI, ofrecemos servicios generales de IA 🚀✨"


# --- Funciones de Búsqueda en APIs (Refactorizadas a async) ---


@TTLCache(ttl_seconds=300)
async def search_tvmaze(query: str):
    """Buscar en TVmaze API"""
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://api.tvmaze.com/search/shows?q={query}"
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

        if not data:
            return None, None

        show = data[0]['show']
        title = show.get('name', 'Sin título')
        summary = show.get('summary', '').replace('<p>', '').replace(
            '</p>', '').replace('<b>', '').replace('</b>', '')
        image_url = show.get('image',
                             {}).get('original') if show.get('image') else None
        premiered = show.get('premiered', '')
        rating = show.get('rating', {}).get('average', 'N/D')
        genres = show.get('genres', [])

        caption = f"📺 <b>{title} ({premiered[:4] if premiered else 'N/D'})</b>\n\n"
        if summary:
            caption += f"📝 <b>Sinopsis:</b>\n{get_synopsis_with_emojis(summary)}\n\n"
        if genres:
            caption += f"🎞️ <b>Géneros:</b> {', '.join(genres)}\n"
        if rating != 'N/D':
            caption += f"⭐️ <b>Calificación:</b> {rating}/10\n"
        if premiered:
            caption += f"📅 <b>Estreno:</b> {premiered}\n"

        caption += f"\n{get_dynamic_closing()}{FIRME}"

        return image_url, caption

    except Exception as e:
        logger.error(f"Error en TVmaze: {e}")
        return None, None


@TTLCache(ttl_seconds=300)
async def search_omdb(query: str):
    """Buscar en OMDb API (necesita API key)"""
    if not OMDB_API_KEY:
        logger.warning("OMDB_API_KEY no está configurada.")
        return None, None
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://www.omdbapi.com/?t={query}&apikey={OMDB_API_KEY}"
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

        if data.get('Response') == 'False':
            return None, None

        title = data.get('Title', 'Sin título')
        year = data.get('Year', 'N/D')
        plot = data.get('Plot', '')
        poster_url = data.get('Poster') if data.get(
            'Poster') != 'N/A' else None
        rating = data.get('imdbRating', 'N/D')
        genre = data.get('Genre', '')
        runtime = data.get('Runtime', '')
        director = data.get('Director', '')
        actors = data.get('Actors', '')

        caption_parts = [f"🎬 <b>{title} ({year})</b>"]
        if plot and plot != 'N/A':
            caption_parts.append(
                f"\n📝 <b>Sinopsis:</b>\n{get_synopsis_with_emojis(plot)}")
        if director and director != 'N/A':
            caption_parts.append(f"\n🎬 <b>Director:</b> {director}")
        if actors and actors != 'N/A':
            caption_parts.append(f"\n🎭 <b>Reparto:</b> {actors}")
        if genre and genre != 'N/A':
            caption_parts.append(f"\n🎞️ <b>Géneros:</b> {genre}")
        if rating and rating != 'N/A':
            caption_parts.append(f"\n⭐️ <b>Calificación IMDb:</b> {rating}/10")

        caption_parts.append(f"\n{get_dynamic_closing()}{FIRME}")
        caption = '\n'.join(caption_parts)

        return poster_url, caption

    except Exception as e:
        logger.error(f"Error en OMDb: {e}")
        return None, None


async def search_tmdb_and_show_options(update: Update,
                                       context: ContextTypes.DEFAULT_TYPE,
                                       query: str):
    try:
        async with httpx.AsyncClient() as client:
            url_movie = f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=es-ES'
            url_tv = f'https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&language=es-ES'

            r_movie, r_tv = await asyncio.gather(
                client.get(url_movie, timeout=10),
                client.get(url_tv, timeout=10))
            data_movie = r_movie.json()
            data_tv = r_tv.json()
            logger.info(f'TMDb movie: {data_movie}')
            logger.info(f'TMDb tv: {data_tv}')

        results = []
        for item in data_movie.get('results', []):
            item['is_movie'] = True
            results.append(item)
        for item in data_tv.get('results', []):
            item['is_movie'] = False
            results.append(item)

        if not results:
            return False

        if len(results) == 1:
            item = results[0]
            await publish_tmdb_item(update, context, item, item['is_movie'])
            return True

        # Mostrar opciones
        context.user_data['matches'] = results
        msg = 'Se encontraron varias coincidencias. Responde con el número de la opción que deseas publicar:\n\n'
        for idx, item in enumerate(results, 1):
            title = item.get('title') or item.get('name', 'Sin título')
            date = item.get('release_date') or item.get('first_air_date', '')
            tipo = 'Película' if item['is_movie'] else 'Serie'
            msg += f"{idx}. {title} ({date[:4] if date else 'N/D'}) [{tipo}]\n"
        await update.message.reply_text(msg)
        return True

    except httpx.RequestError as e:
        logger.error(f"Error de red en TMDb: {e}")
        return False


async def publish_tmdb_item(update: Update,
                            context,
                            item,
                            is_movie,
                            year=None):
    try:
        async with httpx.AsyncClient() as client:
            if is_movie:
                title = item.get('title', 'Sin título')
                id_ = item['id']
                details_url = f'https://api.themoviedb.org/3/movie/{id_}?api_key={TMDB_API_KEY}&language=es-ES&append_to_response=credits'
            else:
                title = item.get('name', 'Sin título')
                id_ = item['id']
                details_url = f'https://api.themoviedb.org/3/tv/{id_}?api_key={TMDB_API_KEY}&language=es-ES&append_to_response=credits'

            r = await client.get(details_url)
            details = r.json()

        overview = details.get('overview') or ''
        genres_raw = details.get('genres') or []
        genres = [g['name'] for g in genres_raw if g and 'name' in g]
        genre_emojis = get_genre_emojis(genres)
        keyword_emojis = get_keyword_emojis(title)
        poster_path = details.get('poster_path')
        poster_url = f'https://image.tmdb.org/t/p/original{poster_path}' if poster_path else None
        release_date = details.get('release_date') or details.get(
            'first_air_date') or ''
        
        runtime_val = details.get('runtime')
        episode_run_time = details.get('episode_run_time')
        if runtime_val:
            runtime = f"{runtime_val} min"
        elif episode_run_time and isinstance(episode_run_time, list) and len(episode_run_time) > 0:
            runtime = f"{episode_run_time[0]} min"
        else:
            runtime = ""

        vote_average = details.get('vote_average')
        credits = details.get('credits') or {}
        cast_list = credits.get('cast') or []
        cast = ', '.join([c['name'] for c in cast_list[:4] if c and 'name' in c])
        director = ''
        crew_list = credits.get('crew') or []
        for c in crew_list:
            if c and c.get('job') in ['Director', 'Directora']:
                director = c.get('name', '')
                break
        lines = [
            f"{keyword_emojis} {genre_emojis} 🎬 <b>{title} ({release_date[:4] if release_date else 'N/D'})</b> 🎬 {keyword_emojis} {genre_emojis}",
            f"🎬 Tipo: Película" if is_movie else "📺 Tipo: Serie"
        ]
        if overview:
            lines.append(
                f"\n📝 <b>Sinopsis:</b>\n{get_synopsis_with_emojis(overview)}")
        if cast: lines.append(f"\n🎭 <b>Reparto:</b> {cast}")
        if director: lines.append(f"\n🎬 <b>Dirección:</b> {director}")
        if release_date: lines.append(f"\n📅 <b>Estreno:</b> {release_date}")
        if vote_average:
            lines.append(f"\n⭐️ <b>Calificación IMDb:</b> {vote_average}/10")
        if genres:
            lines.append(
                f"\n🎞️ <b>Géneros:</b> {', '.join(genres)} {genre_emojis}")
        lines.append(f"\n{get_dynamic_closing()}{FIRME}")
        caption = '\n'.join(lines)

        # --- TRUNCADO DE CAPTION PARA TELEGRAM (Límite 1024 caracteres) ---
        if poster_url and len(caption) > 1024:
            logger.warning(f"Caption demasiado larga ({len(caption)} chars). Truncando...")
            # Intentar reducir la sinopsis primero
            if overview:
                max_overview_len = 1024 - (len(caption) - len(overview)) - 10
                if max_overview_len > 100:
                    truncated_overview = overview[:max_overview_len] + "..."
                    # Regenerar caption con sinopsis truncada
                    lines = []
                    lines.append(f"{keyword_emojis} {genre_emojis} 🎬 <b>{title} ({release_date[:4] if release_date else 'N/D'})</b> 🎬 {keyword_emojis} {genre_emojis}")
                    lines.append(f"🎬 Tipo: Película" if is_movie else "📺 Tipo: Serie")
                    lines.append(f"\n📝 <b>Sinopsis:</b>\n{get_synopsis_with_emojis(truncated_overview)}")
                    if cast: lines.append(f"\n🎭 <b>Reparto:</b> {cast}")
                    if director: lines.append(f"\n🎬 <b>Dirección:</b> {director}")
                    if release_date: lines.append(f"\n📅 <b>Estreno:</b> {release_date}")
                    if vote_average: lines.append(f"\n⭐️ <b>Calificación IMDb:</b> {vote_average}/10")
                    if genres: lines.append(f"\n🎞️ <b>Géneros:</b> {', '.join(genres)} {genre_emojis}")
                    lines.append(f"\n{get_dynamic_closing()}{FIRME}")
                    caption = '\n'.join(lines)
            
            # Si aún es demasiado larga, truncar a lo bruto
            if len(caption) > 1024:
                caption = caption[:1021] + "..."

        if poster_url:
            try:
                await update.message.reply_photo(photo=poster_url,
                                             caption=caption,
                                             parse_mode='HTML')
            except Exception as e:
                logger.error(f"Error enviando foto (posiblemente caption): {e}")
                # Reintento enviando solo texto si falla la foto con caption
                await update.message.reply_text(text=caption, parse_mode='HTML')
        else:
            await update.message.reply_text(text=caption,
                                           parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error publicando item de TMDb: {e}")
        await update.message.reply_text(
            "Hubo un error al procesar la información. Intenta de nuevo.")


async def search_danfra(query: str):
    """Buscar en Danfra.com"""
    try:
        async with httpx.AsyncClient() as client:
            url = "https://www.danfra.com/ajax/search"
            response = await client.post(url, data={'search_text': query}, timeout=10)
            response.raise_for_status()
            data = response.json()

        if not data:
            return None, None

        # Tomamos el primer resultado
        item = data[0]
        title = item.get('nombre', 'Sin título')
        slug = item.get('slug', '')
        image_path = item.get('foto', '')
        image_url = f"https://www.danfra.com/{image_path}" if image_path else None
        page_url = f"https://www.danfra.com/serie/{slug}/" if item.get('tipo') == 'serie' else f"https://www.danfra.com/novela/{slug}/"

        caption = f"🎬 <b>{title} (Danfra)</b>\n\n"
        caption += f"🔗 <a href='{page_url}'>Ver en Danfra</a>\n"
        caption += f"\n¡No te pierdas esta emocionante historia! 🚀{FIRME}"

        return image_url, caption

    except Exception as e:
        logger.error(f"Error en Danfra: {e}")
        return None, None


async def search_lamparaturca(query: str):
    """Buscar en Lamparaturca.com"""
    try:
        async with httpx.AsyncClient() as client:
            url = f"https://lamparaturca.com/?s={query}"
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            
        soup = BeautifulSoup(response.text, 'html.parser')
        article = soup.find('article')
        
        if not article:
            return None, None

        title_tag = article.find('h2', class_='entry-title') or article.find('h1', class_='entry-title')
        if not title_tag:
            return None, None
            
        title = title_tag.get_text(strip=True)
        link = title_tag.find('a')['href'] if title_tag.find('a') else f"https://lamparaturca.com/?s={query}"
        
        img_tag = article.find('img')
        image_url = img_tag['src'] if img_tag else None

        caption = f"🎬 <b>{title} (Lámpara Turca)</b>\n\n"
        caption += f"🔗 <a href='{link}'>Ver en Lámpara Turca</a>\n"
        caption += f"\n¡Una historia fascinante te espera! ✨{FIRME}"

        return image_url, caption

    except Exception as e:
        logger.error(f"Error en Lámpara Turca: {e}")
        return None, None


async def _send_formatted_reply(update: Update, image_url: str | None,
                                caption: str):
    """Envía un mensaje con foto si la URL existe, de lo contrario solo texto."""
    if image_url:
        await update.message.reply_photo(photo=image_url,
                                         caption=caption,
                                         parse_mode='HTML')
    elif caption:
        await update.message.reply_text(caption, parse_mode='HTML')


# --- Manejadores del Bot ---


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /start recibido de usuario {update.message.from_user.id}")
    await update.message.reply_text(
        'Envíame el nombre de la película o serie (ejemplo: Inception)')
    context.user_data.clear()
    return ConversationHandler.END


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"handle_message llamado con texto: '{update.message.text}' de usuario {update.message.from_user.id}")
    # FILTRO 1: Verificar si es spam
    if is_spam_message(update.message.text):
        logger.info(
            f"Mensaje de spam ignorado de usuario {update.message.from_user.id}: {update.message.text[:50]}..."
        )
        return  # Ignorar silenciosamente

    # FILTRO 2: Verificar si el usuario es miembro del grupo
    if not await is_user_in_group(context, update.message.from_user.id):
        logger.info(
            f"Usuario no autorizado {update.message.from_user.id} intentó usar el bot"
        )
        return  # Ignorar silenciosamente

    text = update.message.text.strip()

    # Log de uso legítimo
    logger.info(
        f"Procesando búsqueda legítima de usuario {update.message.from_user.id}: {text}"
    )

    # Intentar separar nombre y año
    try:
        name, year = text.rsplit(' ', 1)
        year = year.strip()
        if not year.isdigit():
            name = text
            year = None
    except ValueError:
        name = text
        year = None

    async with httpx.AsyncClient() as client:
        # Buscar en TMDb (películas)
        url_movie = f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={name}&language=es-ES'
        if year:
            url_movie += f'&year={year}'
        r_movie = await client.get(url_movie)
        data_movie = r_movie.json().get('results', [])

        # Buscar en TMDb (series)
        url_tv = f'https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={name}&language=es-ES'
        if year:
            url_tv += f'&first_air_date_year={year}'
        r_tv = await client.get(url_tv)
        data_tv = r_tv.json().get('results', [])

    # Combinar resultados y marcar tipo
    combined = []
    for item in data_movie:
        item['__type'] = 'movie'
        combined.append(item)
    for item in data_tv:
        item['__type'] = 'tv'
        combined.append(item)

    if not combined:
        # Buscar en TVmaze como último recurso
        poster_url, caption = await search_tvmaze(name)
        if not caption:
            # Intentar en Danfra
            poster_url, caption = await search_danfra(name)
        if not caption:
            # Intentar en Lámpara Turca
            poster_url, caption = await search_lamparaturca(name)
            
        if not caption:
            await update.message.reply_text(
                'No se encontró el material en ninguna de nuestras fuentes. Intenta con otro nombre o año.')
            return
        if poster_url:
            await context.bot.send_photo(chat_id=CHAT_ID,
                                         photo=poster_url,
                                         caption=caption,
                                         parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=CHAT_ID,
                                           text=caption,
                                           parse_mode='HTML')
        return

    # Si hay más de una coincidencia, mostrar opciones
    if len(combined) > 1:
        context.user_data['options'] = combined
        msg = 'Se encontraron varias coincidencias. Responde con el número de la opción que deseas publicar:\n\n'
        for idx, item in enumerate(combined, 1):
            if item['__type'] == 'movie':
                title = item.get('title', 'Sin título')
                date = item.get('release_date', '')
                tipo = '🎬 Película'
            else:
                title = item.get('name', 'Sin título')
                date = item.get('first_air_date', '')
                tipo = '📺 Serie'
            msg += f"{idx}. {title} ({date[:4]}) {tipo}\n"
        await update.message.reply_text(msg)
        logger.info(f"Cambiando a estado SELECCIONANDO para usuario {update.message.from_user.id}")
        return SELECCIONANDO

    # Si solo hay una coincidencia, publicar directamente
    item = combined[0]
    is_movie = item.get('__type') == 'movie'
    year = (item.get('release_date') or item.get('first_air_date') or '')[:4]
    await publish_tmdb_item(update, context, item, is_movie, year)


async def select_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"select_option llamado con texto: '{update.message.text}' de usuario {update.message.from_user.id}")
    # FILTRO: Verificar si el usuario es miembro del grupo
    if not await is_user_in_group(context, update.message.from_user.id):
        logger.info(
            f"Usuario no autorizado {update.message.from_user.id} intentó seleccionar opción"
        )
        return ConversationHandler.END

    try:
        idx = int(update.message.text.strip()) - 1
        options = context.user_data.get('options', [])
        if idx < 0 or idx >= len(options):
            await update.message.reply_text(
                'Opción inválida. Intenta de nuevo.')
            return SELECCIONANDO
        item = options[idx]
        is_movie = item.get('__type') == 'movie'
        year = (item.get('release_date') or item.get('first_air_date') or '')[:4]
        await publish_tmdb_item(update, context, item, is_movie, year)
        context.user_data.clear()
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text(
            'Por favor, responde con el número de la opción.')
        return SELECCIONANDO


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la operación actual."""
    await update.message.reply_text(
        'Operación cancelada. Puedes empezar de nuevo cuando quieras.')
    context.user_data.clear()
    return ConversationHandler.END


class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logger.debug(f"Health server: {format % args}")


def _run_health_server():
    port = int(os.environ.get('PORT', 10000))
    server = socketserver.TCPServer(("", port), HealthHandler)
    server.serve_forever()


def main() -> None:
    """Inicia el bot."""
    if not all([BOT_TOKEN, TMDB_API_KEY]):
        logger.critical(
            "Faltan variables de entorno críticas (BOT_TOKEN, TMDB_API_KEY). El bot no puede iniciar."
        )
        return

    health_thread = threading.Thread(target=_run_health_server, daemon=True)
    health_thread.start()
    logger.info("Health server iniciado...")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        ],
        states={
            SELECCIONANDO:
            [MessageHandler(filters.Regex(r'^\d+$'), select_option)]
        },
        fallbacks=[
            CommandHandler('start', start),
            CommandHandler('cancel', cancel)
        ])

    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)

    logger.info("Bot iniciado...")
    app.run_polling()


if __name__ == '__main__':
    main()
