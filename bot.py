importarimportar sistema operativo
importarimportar asyncio
importarimportar httpx
importarimportar aleatorio
importarimportar registro
importsolicitudes de importación
registro.configuración básica(nivel=registro.INFORMACIÓN)configuración básica(nivel=registro.INFORMACIÓN)
desdede dotenv importar load_dotenvimportar load_dotenv
desdede telegram importar Actualización, ChatMemberimport Update, ChatMember
telegrama dede.ext importar ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filtros, ConversationHandlerimportar ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filtros, ConversationHandler

# Cargar variables de entorno
carga_punto()

# --- Configuración y Constantes ---
registro.configuración básica(configuración básica(
 formato='%(asctime)s - %(nombre)s - %(nombre de nivel)s - %(mensaje)s','%(asctime)s - %(nombre)s - %(nombre de nivel)s - %(mensaje)s',
 nivel=registro.INFORMACIÓNINFO
)
registrador = registro.getLogger(__nombre__)getLogger(__nombre__)

BOT_TOKEN = sistema operativo.getenv("BOT_TOKEN")getenv("BOT_TOKEN")
TMDB_API_KEY = sistema operativo.getenv(„TMDB_API_KEY")getenv(„TMDB_API_KEY")
OMDB_API_KEY = sistema operativo.getenv("CLAVE_API_OMDB") # Movido aquí para consistenciagetenv("OMDB_API_KEY") # Movido aquí para consistencia
CHAT_ID = -10027000946611002700094661

FIRME = "\n\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ""\n\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ"

# Estados de la conversación
SELECCIONANDO = 11

# --- SISTEMA ANTISPAM MEJORADO ---

# Palabras clave de spam (en minúsculas) - VERSIÓN MEJORADA
PALABRAS CLAVE_SPAM = [[
 # Criptomonedas/Casino# Cripto/Casino
    'eth libre', 'Ethereum gratis', 'jetacas', 'casino', 'bonificación', 'código promocional', 
    'bienvenido1k', 'lanzamiento aéreo', 'cripto', 'cartera', 'btc', 'bitcoin', 'reclamar',
    'freeether.net', 'eth alerta', 'etéreo', 'bono instantáneo', 'plataforma con licencia',
    
    # Términos financieros sospechosos
    'ganar dinero', 'ganar dinero', 'dinero gratis', 'dinero fácil', 'ingresos pasivos',
    'inversión', 'ganancia', 'roi', 'comercio', 'forex', 'binario', 'lotería',
    'ganador', 'premio', 'recompensa', 'regalo', 'sin tarifas', 'libre de riesgos', 'garantizado',
    
    # Llamadas a la acción urgentes
    'haga clic aquí', 'visitar', 'regístrate ahora', 'registrarse', 'actúa ahora', 'fecha prisa',
    'tiempo limitado', 'no te lo pierdas\', 'exclusivo', 'secreto', 'instante',
    'por tiempo limitado', 'no dura para siempre', 'lanzamiento aire limitado', 'reclama ahora',
    
    # URLs y entrelaza sospechosos 
    'www.', 'http', '.com', '.net', 'telegrama.yo', 't.me', 'enlace', 'url',
    
    # Términos de marketing agresivo
    'oferta', 'trato', 'trabajar desde casa', 'mlm', 'pirámide', 'Soporte 24 horas al día, 7 días a la semana',
    'depósito mío', 'retiros', 'tarjetas', 'cripto', 'carteras eléctricas',
    'se requiere verificación', 'sin condiciones', 'implementar registro',
    'conecta tu billetera', 'verificar', 'el equilibrio cree'
]

# URLs sospechosas - VERSIÓN MEJORADA
SPAM_URLS = [
    'jetacas.com', 'freeether.net', 'freecrypto', 'lanzamiento aéreo', 'reclamar dinero', 
    'gana', 'bitcoins de Pecar', 'cryptogift', 'freetokens', 'casino',
    'bonificación', 'promoción', 'reclamar', 'gratis', 'ganar', 'dinero'
]

# Patrones de emojis sospechosos
PATRÓN_EMOJI_SPAM = [
    '🚨', '💰', '🔥', '🔑', '📥', '🔒', '⚡️', '🎮', '🕐', '💵', 
    '✅', '💳', '🤑', '⚡️', '⏳', '👉', '🟢'
]

importar re

def es_mensaje_spam(texto: str) -> bool:
    """Detecta si un mensaje es spam - VERSIÓN SUPER MEJORADA"""
 si no hay texto:
 retorno Falso
    
 texto_inferior = texto.inferior()
    
    # 1. Palabras clave con regex (coincidencia exacta de palabras)
 encuentro_spam = 0
 para palabra clave en SPAM_PALABRAS CLAVE:
 si re.buscar(rf'\b{re.escapar(palabra clave)}\b', texto_inferior):
 recuento_spam += 1
    
    # 2. URL con expresiones regulares
 url_pattern = re.buscar(
        r'(jetacas\.com|freeether\.net|t\.me|telegram\.me)',
 texto_inferior
    )
    
    # 3. Nombres específicos de casinos
 nombres_casino = ['jetacas', 'éter libre']
 tiene_nombre_casino = cualiera(re.buscar(rf'\b{nombre}\b', texto_inferior) para nombre en nombres_casino)
    
    # 4. Patrones de spam de casino
 patrón_casino = re.buscar(
        r'(\b(?:jetacas|casino)\b.*bonus.*promo|\$1000.*bonus.*promo)',
 texto_inferior
    )
    
    # 5. Combinación sostenida de elementos
 has_spam_combo = (
        cualiera(emoji en texto para emoji en PATRONES_EMOJI_SPAM) y
 cualiera(palabra clave en texto_inferior para palabra clave en ['casino', 'bonificación', 'promoción']) y
        ('.com' en texto_inferior o 't.me' en texto_inferior)
    )
    
 # 6. Estructura física de spam (múltiples líneas con emojis)
 líneas = texto.dividir('\n')
 líneas_emoji = suma(1 para línea en líneas si cualiera(emoji en línea para emoji en PATRONES_EMOJI_SPAM))
 has_spam_structure = emoji_lines >= 4
    
 # Condiciones de detección (más restricciones)
 retorno (
 recuento_spam >= 2 o
 url_patrón es no Ninguno o
 has_casino_nombre o
 patrón_casino es no Ninguno o
 has_spam_combo o
 (tiene_estructura_spam y retorno_spam >= 1)
)
    
 # 7. Verificar longitud excesiva (spam típico es muy largo)
 es_demosiado_largo = len(texto) > 500
    
 # 8. Detectar múltiples líneas con emojis (estructura de spam)
 líneas_con_emojis = suma(1 para línea en texto.dividir('\n') si cualiera(emoji en línea para emoji en PATRONES_EMOJI_SPAM))
 has_spam_structure = líneas_con_emojis >= 4
    
 # Mensaje es spam si cumple cualera de estos criterios:
 regresar (
 encuentro_spam >= 2 o # Reducido de 3 a 2 para mayor sensibilidad
 url_spam o 
 tiene_nombre_casino o
 estructura_casino o 
 cripto_estructura o
 (tiene_emojis_excesivos y tiene_idioma_urgente) o 
 (tiene_caps_sospechosos y encuentro_spam >= 1) o
 (es_demosiado_largo y encuentro_spam >= 1) o
 tiene_estructura_spam
    )


# --- Diccionarios de Emojis ---

genero_emojis_dict = {
    'Acción': '🔥', 'Aventura': '🗺️', 'Animación': '🎨', 'Comedia': '😂',
    'Crimen': '🕵️', 'Documental': '🎥', 'Drama': '🎭', 'Familia': '👨‍👩‍👧‍👦',
    'Fantasía': '🧚', 'Historia': '📜', 'Terror': '👻', 'Música': '🎵',
    'Misterio': '🕵️‍♂️', 'Romance': '❤️', 'Ciencia ficción': '🤖',
    'Película de TV': '📺', 'Suspense': '😱', 'Bélica': '⚔️', 'Western': '🤠',
    'Ballet': '🩰', 'Deportes': '🏅', 'Aviación': '✈️', 'Superhéroes': '🦸',
}

title_keyword_emojis = {
    'luna': '🌙', 'espacio': '🚀', 'estrella': '⭐', 'mar': '🌊',
    'amor': '❤️', 'avión': '✈️', 'fuego': '🔥', 'guerra': '⚔️',
    'robot': '🤖', 'fantasma': '👻', 'música': '🎵', 'superhéroe': '🦸',
    'deporte': '🏅', 'misterio': '🕵️', 'terror': '👻', 'comedia': '😂',
    'drama': '🎭', 'historia': '📜', 'fantasía': '🧚', 'familia': '👨‍👩‍👧‍👦',
}

synopsis_keyword_emojis = {
    'asesino': '🔪', 'misterio': '🕵️', 'amor': '❤️', 'guerra': '⚔️',
    'espacio': '🚀', 'luna': '🌙', 'robot': '🤖', 'futuro': '🔮',
    'ballet': '🩰', 'familia': '👨‍👩‍👧‍👦', 'venganza': '😠', 'crimen': '🕵️',
    'viaje': '✈️', 'mar': '🌊', 'monstruo': '👹', 'música': '🎵',
    'superhéroe': '🦸', 'magia': '✨', 'batalla': '⚔️', 'sueño': '💤',
    'dinero': '💰', 'rescate': '🆘', 'explosión': '💥', 'coche': '🚗',
}

# --- Funciones de Formato de Texto ---

def get_genre_emojis(genres):
    return ' '.join(sorted({genre_emojis_dict.get(g, '🎬') for g in genres}))

def get_keyword_emojis(title):
    t = title.lower()
    return ' '.join({e for k, e in title_keyword_emojis.items() if k in t})

def get_synopsis_with_emojis(synopsis):
    if not synopsis:
        return ''
    synopsis_lower = synopsis.lower()
    found_emojis = set()
    for keyword, emoji in synopsis_keyword_emojis.items():
        if keyword in synopsis_lower and emoji not in found_emojis:
            found_emojis.add(emoji)
            if len(found_emojis) >= 3:
                break
    return f"{synopsis} {' '.join(found_emojis)}" if found_emojis else synopsis

def get_dynamic_closing(synopsis):
    s = synopsis.lower()
    if any(x in s for x in ['misterio', 'secreto']):        return "¡Una historia de misterio! 🕵️‍♂️"
    if any(x in s for x in ['aventura', 'viaje']):          return "¡Sumérgete en esta aventura única! 🗺️"
    if any(x in s for x in ['acción', 'batalla']):          return "¡Prepárate para la acción! 🔥"
    if any(x in s for x in ['amor', 'romance']):            return "¡Déjate llevar por esta historia de amor! ❤️"
    if any(x in s for x in ['familia', 'hermano', 'padre']):return "¡Una historia que celebra la familia! 👨‍👩‍👧‍👦"
    if any(x in s for x in ['espacio', 'planeta']):         return "¡Viaja más allá de las estrellas! 🌌"
    if any(x in s for x in ['terror', 'miedo']):            return "¡Prepárate a sentir el terror! 👻"
    if any(x in s for x in ['música', 'canción']):          return "¡Déjate llevar por la música! 🎵"
    if any(x in s for x in ['magia', 'fantasía']):          return "¡Descubre un mundo de magia! ✨"
    return random.choice([
        "¡No te pierdas esta emocionante historia! 🚀",
        "¡Una experiencia que no olvidarás! ⭐"
    ])

# --- Funciones de Búsqueda en APIs (Refactorizadas a async) ---

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
        summary = show.get('summary', '').replace('<p>', '').replace('</p>', '').replace('<b>', '').replace('</b>', '')
        image_url = show.get('image', {}).get('original') if show.get('image') else None
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
        
        caption += f"\n{get_dynamic_closing(summary)}{SIGNATURE}"
        
        return image_url, caption
        
    except Exception as e:
        logger.error(f"Error en TVmaze: {e}")
        return None, None

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
        poster_url = data.get('Poster') if data.get('Poster') != 'N/A' else None
        rating = data.get('imdbRating', 'N/D')
        genre = data.get('Genre', '')
        runtime = data.get('Runtime', '')
        director = data.get('Director', '')
        actors = data.get('Actors', '')
        
        caption_parts = [f"🎬 <b>{title} ({year})</b>"]
        if plot and plot != 'N/A':       caption_parts.append(f"\n📝 <b>Sinopsis:</b>\n{get_synopsis_with_emojis(plot)}")
        if director and director != 'N/A': caption_parts.append(f"\n🎬 <b>Director:</b> {director}")
        if actors and actors != 'N/A':   caption_parts.append(f"\n🎭 <b>Reparto:</b> {actors}")
        if runtime and runtime != 'N/A': caption_parts.append(f"\n🕒 <b>Duración:</b> {runtime}")
        if genre and genre != 'N/A':     caption_parts.append(f"\n🎞️ <b>Géneros:</b> {genre}")
        if rating and rating != 'N/A':   caption_parts.append(f"\n⭐️ <b>Calificación IMDb:</b> {rating}/10")
        
        caption_parts.append(f"\n{get_dynamic_closing(plot)}{SIGNATURE}")
        caption = '\n'.join(caption_parts)
        
        return poster_url, caption
        
    except Exception as e:
        logger.error(f"Error en OMDb: {e}")
        return None, None

async def search_tmdb_and_show_options(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    try:
        async with httpx.AsyncClient() as client:
            url_movie = f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=es-ES'
            url_tv = f'https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&language=es-ES'

            r_movie, r_tv = await asyncio.gather(
                client.get(url_movie, timeout=10),
                client.get(url_tv, timeout=10)
            )
            data_movie = r_movie.json()
            data_tv = r_tv.json()
            logging.info(f'TMDb movie: {data_movie}')
            logging.info(f'TMDb tv: {data_tv}')

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
            await publish_tmdb_item(update, results[0])
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

async def publish_tmdb_item(update: Update, context, item, is_movie, year=None):
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

        overview = details.get('overview', '')
        genres = [g['name'] for g in details.get('genres', [])]
        genre_emojis = get_genre_emojis(genres)
        keyword_emojis = get_keyword_emojis(title)
        poster_path = details.get('poster_path')
        poster_url = f'https://image.tmdb.org/t/p/original{poster_path}' if poster_path else None
        release_date = details.get('release_date') or details.get('first_air_date', '')
        runtime = details.get('runtime') or (details.get('episode_run_time', [''])[0] if details.get('episode_run_time') else '')
        if runtime:
            runtime = f"{runtime} min"
        vote_average = details.get('vote_average')
        credits = details.get('credits', {})
        cast = ', '.join([c['name'] for c in credits.get('cast', [])[:4]])
        director = ''
        for c in credits.get('crew', []):
            if c['job'] in ['Director', 'Directora']:
                director = c['name']
                break
        lines = [
            f"{keyword_emojis} {genre_emojis} 🎬 <b>{title} ({release_date[:4] if release_date else 'N/D'})</b> 🎬 {keyword_emojis} {genre_emojis}",
            f"🎬 Tipo: Película" if is_movie else "📺 Tipo: Serie"
        ]
        if overview:   lines.append(f"\n📝 <b>Sinopsis:</b>\n{get_synopsis_with_emojis(overview)}")
        if cast:       lines.append(f"\n🎭 <b>Reparto:</b> {cast}")
        if director:   lines.append(f"\n🎬 <b>Dirección:</b> {director}")
        if runtime:    lines.append(f"\n🕒 <b>Duración:</b> {runtime}")
        if release_date: lines.append(f"\n📅 <b>Estreno:</b> {release_date}")
        if vote_average: lines.append(f"\n⭐️ <b>Calificación IMDb:</b> {vote_average}/10")
        if genres:     lines.append(f"\n🎞️ <b>Géneros:</b> {', '.join(genres)} {genre_emojis}")
        lines.append(f"\n{get_dynamic_closing(overview)}{SIGNATURE}")
        caption = '\n'.join(lines)
        if poster_url:
            await context.bot.send_photo(chat_id=CHAT_ID, photo=poster_url, caption=caption, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error publicando item de TMDb: {e}")
        await update.message.reply_text("Hubo un error al procesar la información. Intenta de nuevo.")

async def _send_formatted_reply(update: Update, image_url: str | None, caption: str):
    """Envía un mensaje con foto si la URL existe, de lo contrario solo texto."""
    if image_url:
        await update.message.reply_photo(photo=image_url, caption=caption, parse_mode='HTML')
    elif caption:
        await update.message.reply_text(caption, parse_mode='HTML')

# --- Manejadores del Bot ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("start llamado")  # Esto nos ayudará a ver en los logs cuando se llama a start
    await update.message.reply_text('Envíame el nombre de la película o serie (ejemplo: Inception)')
    context.user_data.clear()  # Limpiamos cualquier dato previo del usuario
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # FILTRO 1: Verificar si es spam
    if is_spam_message(update.message.text):
        logger.info(f"Mensaje de spam ignorado de usuario {update.message.from_user.id}: {update.message.text[:50]}...")
        return  # Ignorar silenciosamente
    
    # FILTRO 2: Verificar si el usuario es miembro del grupo
    if not await is_user_in_group(context, update.message.from_user.id):
        logger.info(f"Usuario no autorizado {update.message.from_user.id} intentó usar el bot")
        return  # Ignorar silenciosamente
    
    text = update.message.text.strip()
    
    # Log de uso legítimo
    logger.info(f"Procesando búsqueda legítima de usuario {update.message.from_user.id}: {text}")
    
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
            await update.message.reply_text('No se encontró el material. Intenta con otro nombre o año.')
            return
        if poster_url:
            await context.bot.send_photo(chat_id=CHAT_ID, photo=poster_url, caption=caption, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
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
        return SELECTING

    # Si solo hay una coincidencia, publicar directamente
    item = combined[0]
    is_movie = item['__type'] == 'movie'
    year = item.get('release_date', '')[:4] if is_movie else item.get('first_air_date', '')[:4]
    await publish_tmdb_item(update, context, item, is_movie, year)

async def select_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # FILTRO: Verificar si el usuario es miembro del grupo
    if not await is_user_in_group(context, update.message.from_user.id):
        logger.info(f"Usuario no autorizado {update.message.from_user.id} intentó seleccionar opción")
        return ConversationHandler.END
    
    try:
        idx = int(update.message.text.strip()) - 1
        options = context.user_data.get('options', [])
        if idx < 0 or idx >= len(options):
            await update.message.reply_text('Opción inválida. Intenta de nuevo.')
            return SELECTING
        item = options[idx]
        is_movie = item.get('__type') == 'movie'
        year = item.get('release_date', '')[:4] if is_movie else item.get('first_air_date', '')[:4]
        await publish_tmdb_item(update, context, item, is_movie, year)
        context.user_data.clear()
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text('Por favor, responde con el número de la opción.')
        return SELECTING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la operación actual."""
    await update.message.reply_text('Operación cancelada. Puedes empezar de nuevo cuando quieras.')
    context.user_data.clear()
    return ConversationHandler.END

def main() -> None:
    """Inicia el bot."""
    if not all([BOT_TOKEN, TMDB_API_KEY]):
        logger.critical("Faltan variables de entorno críticas (BOT_TOKEN, TMDB_API_KEY). El bot no puede iniciar.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            SELECTING: [MessageHandler(filters.Regex(r'^\d+$'), select_option)]
        },
        fallbacks=[
            CommandHandler('start', start),
            CommandHandler('cancel', cancel)
        ]
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    
    logger.info("Bot iniciado...")
    app.run_polling()

if __name__ == '__main__':
    main()
