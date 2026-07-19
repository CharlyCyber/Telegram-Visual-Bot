import os
import asyncio
import html
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

FIRME = "\n\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ"

# Estados de la conversación
SELECCIONANDO = 11

# --- Separadores visuales ---
SEP = "━━━━━━━━━━━━━━━━━━━━━━"
SEP_SOFT = "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"
SEP_STAR = "･ﾟ✧ ━━━━━━━━━━━━━ ✧ﾟ･"

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
    "sin identificación",
    "24/7 soporte",
    "mínimo depósito",
    "pagos justos",
    "retiros rápidos",
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
    "roi",
    "forex",
    "sin tarifas",
    "libre de riesgos",
    "garantizado",

    # Llamadas a la acción urgentes
    "haga clic aquí",
    "regístrate ahora",
    "actúa ahora",
    "tiempo limitado",
    "no te lo pierdas",
    "por tiempo limitado",
    "no dura para siempre",
    "lanzamiento aire limitado",
    "reclama ahora",

    # URLs y enlaces sospechosos
    "telegrama.yo",

    # Términos de marketing agresivo
    "trabajar desde casa",
    "mlm",
    "pirámide",
    "Soporte 24 horas al día, 7 días a la semana",
    "depósito mío",
    "carteras eléctricas",
    "se requiere verificación",
    "sin condiciones",
    "implementar registro",
    "conecta tu billetera",
    "el equilibrio cree"
]

# Dominios/URLs de scam conocidos (coincidencia por substring).
# Solo dominios reales: las palabras genéricas ("gratis", "dinero", "casino")
# provocaban falsos positivos en títulos legítimos.
SPAM_URLS = [
    "jetacas.com", "freeether.net", "freecrypto", "cryptogift", "freetokens",
    "onlinecasino.com", "gamblingsite.net", "bettingplatform.org"
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

    # 3. Nombres de servicios de scam específicos (NO "casino" a secas: es un
    # título de película legítimo). Solo marcas/dominios inequívocos.
    nombres_casino = ["jetacas", "freeether.net"]
    has_casino_name = any(
        re.search(rf"\b{re.escape(nombre)}\b", texto_inferior)
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
    'vida': '🌱', 'mundo': '🌍', 'batalla': '⚔️', 'poder': '⚡', 'secreto': '🤫'
}

synopsis_keyword_emojis = {
    'asesino': '🔪', 'misterio': '🕵️', 'amor': '❤️', 'guerra': '⚔️', 'espacio': '🚀',
    'luna': '🌙', 'robot': '🤖', 'futuro': '🔮', 'ballet': '🩰', 'familia': '👨‍👩‍👧‍👦',
    'venganza': '😠', 'crimen': '🕵️', 'viaje': '✈️', 'mar': '🌊', 'monstruo': '👹',
    'música': '🎵', 'superhéroe': '🦸', 'magia': '✨', 'batalla': '⚔️', 'sueño': '💤',
    'dinero': '💰', 'rescate': '🆘', 'explosión': '💥', 'coche': '🚗', 'dragón': '🐉',
    'fuego': '🔥', 'espada': '⚔️', 'reino': '🏰', 'bosque': '🌲', 'ciudad': '🏙️',
    'policía': '👮', 'detective': '🕵️‍♂️', 'prisión': '⛓️', 'huida': '🏃',
    'secreto': '🤫', 'traición': '🐍', 'amistad': '🤝', 'escuela': '🏫',
    'universidad': '🎓', 'tecnología': '💻', 'virus': '🦠', 'zombie': '🧟',
    'alienígena': '👽', 'planeta': '🪐', 'tiempo': '⏳', 'pasado': '🕰️'
}

# --- Funciones de Formato de Texto ---


def esc(value) -> str:
    """Escapa texto para insertarlo de forma segura en captions HTML de Telegram."""
    if value is None:
        return ''
    return html.escape(str(value))


def get_genre_emojis(genres):
    return ' '.join(sorted({genero_emojis_dict.get(g, '🎬') for g in genres}))


def get_keyword_emojis(title):
    t = title.lower()
    return ' '.join({e for k, e in title_keyword_emojis.items() if k in t})


MAX_SYNOPSIS_EMOJIS = 30


def get_synopsis_with_emojis(synopsis):
    """Inserta un emoji junto a cada palabra que coincida con una keyword.

    Recorre la sinopsis palabra por palabra y añade el emoji correspondiente
    inmediatamente después de la palabra relevante. Limita el total con
    MAX_SYNOPSIS_EMOJIS para no exceder el tope de 1024 chars del caption.
    """
    if not synopsis:
        return ''

    tokens = re.split(r'(\s+)', synopsis)  # conserva los espacios
    result = []
    added = 0
    for token in tokens:
        result.append(token)
        if not token.strip() or added >= MAX_SYNOPSIS_EMOJIS:
            continue
        clean = re.sub(r'[^\wáéíóúüñ]', '', token.lower())
        if not clean:
            continue
        for keyword, emoji in synopsis_keyword_emojis.items():
            if keyword == clean or keyword in clean:
                result.append(f' {emoji}')
                added += 1
                break

    if added == 0:
        return synopsis
    return ''.join(result)


def get_dynamic_closing(_synopsis=None):
    return "🤖 Automatización creada por Charli AI, ofrecemos servicios generales de IA 🚀✨"


# --- Funciones de Búsqueda en APIs (Refactorizadas a async) ---


@TTLCache(ttl_seconds=300)
async def search_tvmaze(query: str):
    """Buscar en TVmaze API"""
    try:
        async with httpx.AsyncClient() as client:
            url = "https://api.tvmaze.com/search/shows"
            response = await client.get(url, params={"q": query}, timeout=10)
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

        caption = f"📺✨ <b>{esc(title)} ({esc(premiered[:4]) if premiered else 'N/D'})</b> ✨📺\n"
        caption += f"{SEP}\n"
        if summary:
            caption += f"📝 <b>Sinopsis:</b>\n{esc(get_synopsis_with_emojis(summary))}\n\n{SEP_SOFT}\n"
        if genres:
            caption += f"🎞️ <b>Géneros:</b> {esc(', '.join(genres))} {get_genre_emojis(genres)}\n"
        if rating != 'N/D':
            caption += f"⭐️ <b>Calificación:</b> {esc(rating)}/10\n"
        if premiered:
            caption += f"📅 <b>Estreno:</b> {esc(premiered)}\n"

        caption += f"\n{SEP_STAR}\n{get_dynamic_closing()}{FIRME}"

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
            url = "https://www.omdbapi.com/"
            response = await client.get(
                url, params={"t": query, "apikey": OMDB_API_KEY}, timeout=10)
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

        caption_parts = [f"🎬🍿 <b>{esc(title)} ({esc(year)})</b> 🍿🎬", SEP]
        if plot and plot != 'N/A':
            caption_parts.append(
                f"📝 <b>Sinopsis:</b>\n{esc(get_synopsis_with_emojis(plot))}\n\n{SEP_SOFT}")
        if runtime and runtime != 'N/A':
            caption_parts.append(f"⏱️ <b>Duración:</b> {esc(runtime)}")
        if director and director != 'N/A':
            caption_parts.append(f"🎬 <b>Director:</b> {esc(director)}")
        if actors and actors != 'N/A':
            caption_parts.append(f"🎭 <b>Reparto:</b> {esc(actors)}")
        if genre and genre != 'N/A':
            caption_parts.append(f"🎞️ <b>Géneros:</b> {esc(genre)}")
        if rating and rating != 'N/A':
            caption_parts.append(f"⭐️ <b>Calificación IMDb:</b> {esc(rating)}/10")

        caption_parts.append(f"\n{SEP_STAR}\n{get_dynamic_closing()}{FIRME}")
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
            params = {
                "api_key": TMDB_API_KEY,
                "query": query,
                "language": "es-ES",
            }
            url_movie = 'https://api.themoviedb.org/3/search/movie'
            url_tv = 'https://api.themoviedb.org/3/search/tv'

            r_movie, r_tv = await asyncio.gather(
                client.get(url_movie, params=params, timeout=10),
                client.get(url_tv, params=params, timeout=10))
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
                details_url = f'https://api.themoviedb.org/3/movie/{id_}'
            else:
                title = item.get('name', 'Sin título')
                id_ = item['id']
                details_url = f'https://api.themoviedb.org/3/tv/{id_}'

            details_params = {
                "api_key": TMDB_API_KEY,
                "language": "es-ES",
                "append_to_response": "credits,videos",
            }
            r = await client.get(details_url, params=details_params, timeout=10)
            details = r.json()

            overview = details.get('overview') or ''

            # Fallback: si no hay sinopsis en español, intentar en inglés
            if not overview:
                try:
                    fallback_params = {
                        "api_key": TMDB_API_KEY,
                        "language": "en-US",
                        "append_to_response": "credits,videos",
                    }
                    r2 = await client.get(details_url, params=fallback_params, timeout=10)
                    fallback_details = r2.json()
                    overview = fallback_details.get('overview') or ''
                    if 'tagline' not in details or not details.get('tagline'):
                        details['tagline'] = fallback_details.get('tagline') or ''
                except Exception as e:
                    logger.warning(f"No se pudo obtener fallback en inglés: {e}")

            # Fallback 2: si sigue sin sinopsis, buscar en OMDb por IMDb ID
            if not overview and OMDB_API_KEY:
                imdb_id = details.get('imdb_id')
                if imdb_id:
                    try:
                        omdb_r = await client.get(
                            "https://www.omdbapi.com/",
                            params={"i": imdb_id, "apikey": OMDB_API_KEY},
                            timeout=10)
                        omdb_data = omdb_r.json()
                        if omdb_data.get('Response') == 'True':
                            plot = omdb_data.get('Plot')
                            if plot and plot != 'N/A':
                                overview = plot
                    except Exception as e:
                        logger.warning(f"No se pudo obtener sinopsis de OMDb: {e}")

        tagline = details.get('tagline') or ''
        genres_raw = details.get('genres') or []
        genres = [g['name'] for g in genres_raw if g and 'name' in g]
        genre_emojis = get_genre_emojis(genres)
        keyword_emojis = get_keyword_emojis(title)
        poster_path = details.get('poster_path')
        poster_url = f'https://image.tmdb.org/t/p/original{poster_path}' if poster_path else None
        release_date = details.get('release_date') or details.get(
            'first_air_date') or ''

        # Datos específicos de series
        num_seasons = details.get('number_of_seasons')
        num_episodes = details.get('number_of_episodes')

        # Presupuesto / recaudación (solo películas) y país de producción
        budget = details.get('budget') or 0
        revenue = details.get('revenue') or 0
        countries_raw = details.get('production_countries') or []
        countries = ', '.join(c.get('name') for c in countries_raw if c and c.get('name'))

        def fmt_money(v):
            try:
                v = int(v)
            except (TypeError, ValueError):
                return ''
            if v <= 0:
                return ''
            return f"${v:,.0f}".replace(',', '.')

        vote_average = details.get('vote_average')
        vote_count = details.get('vote_count')
        credits = details.get('credits') or {}
        cast_list = credits.get('cast') or []
        cast = ', '.join([c['name'] for c in cast_list[:4] if c and 'name' in c])
        director = ''
        crew_list = credits.get('crew') or []
        for c in crew_list:
            if c and c.get('job') in ['Director', 'Directora']:
                director = c.get('name', '')
                break

        # Estrella visual según calificación
        def rating_stars(v):
            try:
                full = int(round(float(v) / 2))
            except (TypeError, ValueError):
                return ''
            full = max(0, min(5, full))
            return '⭐' * full + '☆' * (5 - full)

        def build_caption(ov):
            lines = [
                f"🎬🍿 {keyword_emojis} {genre_emojis}",
                f"✨ <b>{esc(title)} ({esc(release_date[:4]) if release_date else 'N/D'})</b> ✨",
            ]
            lines.append(SEP)
            lines.append("🎬 <b>Tipo:</b> Película 🎞️" if is_movie else "📺 <b>Tipo:</b> Serie 📺")
            if tagline:
                lines.append(f"💬 <i>«{esc(tagline)}»</i>")
            if ov:
                lines.append(f"\n📝 <b>Sinopsis:</b>\n{esc(get_synopsis_with_emojis(ov))}")
            else:
                lines.append(f"\n📝 <b>Sinopsis:</b>\n<i>Sin descripción disponible.</i>")
            lines.append(f"\n{SEP_SOFT}")
            if cast:
                lines.append(f"🎭 <b>Reparto:</b> {esc(cast)}")
            if director:
                lines.append(f"🎬 <b>Dirección:</b> {esc(director)}")
            if release_date:
                lines.append(f"📅 <b>Estreno:</b> {esc(release_date)}")
            if not is_movie and num_seasons:
                temp_txt = f"📚 <b>Temporadas:</b> {esc(num_seasons)}"
                if num_episodes:
                    temp_txt += f"  •  🎞️ <b>Episodios:</b> {esc(num_episodes)}"
                lines.append(temp_txt)
            if countries:
                lines.append(f"🏳️ <b>País:</b> {esc(countries)}")
            if is_movie:
                b = fmt_money(budget)
                rev = fmt_money(revenue)
                if b:
                    lines.append(f"💵 <b>Presupuesto:</b> {esc(b)}")
                if rev:
                    lines.append(f"🤑 <b>Recaudación:</b> {esc(rev)}")
            if vote_average:
                stars = rating_stars(vote_average)
                count_txt = f" ({esc(vote_count)} votos)" if vote_count else ""
                lines.append(f"⭐️ <b>Calificación:</b> {esc(vote_average)}/10 {stars}{count_txt}")
            if genres:
                lines.append(f"🎞️ <b>Géneros:</b> {esc(', '.join(genres))} {genre_emojis}")
            lines.append(f"\n{SEP_STAR}")
            lines.append(f"{get_dynamic_closing()}{FIRME}")
            return '\n'.join(lines)

        caption = build_caption(overview)

        # --- TRUNCADO DE CAPTION PARA TELEGRAM (Límite 1024 caracteres) ---
        if poster_url and len(caption) > 1024:
            logger.warning(f"Caption demasiado larga ({len(caption)} chars). Truncando...")
            if overview:
                max_overview_len = 1024 - (len(caption) - len(overview)) - 10
                if max_overview_len > 100:
                    truncated_overview = overview[:max_overview_len] + "..."
                    caption = build_caption(truncated_overview)

            if len(caption) > 1024:
                signature = f"\n{SEP_STAR}\n{get_dynamic_closing()}{FIRME}"
                max_body = 1024 - len(signature) - 3
                if max_body > 0:
                    caption = caption[:max_body] + "..." + signature
                else:
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

        caption = f"🎬✨ <b>{esc(title)}</b> ✨🎬\n"
        caption += f"🌐 <i>Fuente: Danfra</i>\n{SEP}\n"
        caption += f"🔗 <a href='{esc(page_url)}'>📺 Ver en Danfra</a>\n"
        caption += f"\n🎉 ¡No te pierdas esta emocionante historia! 🚀🍿\n{SEP_STAR}{FIRME}"

        return image_url, caption

    except Exception as e:
        logger.error(f"Error en Danfra: {e}")
        return None, None


async def search_lamparaturca(query: str):
    """Buscar en Lamparaturca.com"""
    try:
        async with httpx.AsyncClient() as client:
            url = "https://lamparaturca.com/"
            response = await client.get(
                url, params={"s": query}, timeout=10)
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

        caption = f"🎬✨ <b>{esc(title)}</b> ✨🎬\n"
        caption += f"🌐 <i>Fuente: Lámpara Turca</i>\n{SEP}\n"
        caption += f"🔗 <a href='{esc(link)}'>📺 Ver en Lámpara Turca</a>\n"
        caption += f"\n💫 ¡Una historia fascinante te espera! ✨🍿\n{SEP_STAR}{FIRME}"

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
        movie_params = {
            "api_key": TMDB_API_KEY, "query": name, "language": "es-ES"}
        if year:
            movie_params["year"] = year
        r_movie = await client.get(
            'https://api.themoviedb.org/3/search/movie',
            params=movie_params, timeout=10)
        data_movie = r_movie.json().get('results', [])

        # Buscar en TMDb (series)
        tv_params = {
            "api_key": TMDB_API_KEY, "query": name, "language": "es-ES"}
        if year:
            tv_params["first_air_date_year"] = year
        r_tv = await client.get(
            'https://api.themoviedb.org/3/search/tv',
            params=tv_params, timeout=10)
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
