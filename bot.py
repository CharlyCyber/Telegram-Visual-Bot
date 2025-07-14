import os
import asyncio
import httpx
import random
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler

# Cargar variables de entorno
load_dotenv()

# --- Configuración y Constantes ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OMDB_API_KEY = os.getenv("OMDB_API_KEY") # Movido aquí para consistencia
CHAT_ID = -1002700094661

SIGNATURE = "\n\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ"

# Estados de la conversación
SELECTING = 1

# --- Diccionarios de Emojis ---

genre_emojis_dict = {
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
    if any(x in s for x in ['misterio', 'secreto']):        return "¡Atrévete a descubrir el misterio! 🕵️‍♂️"
    if any(x in s for x in ['aventura', 'viaje']):          return "¡Sumérgete en esta aventura única! 🗺️"
    if any(x in s for x in ['acción', 'batalla']):          return "¡Prepárate para la acción! 🔥"
    if any(x in s for x in ['amor', 'romance']):            return "¡Déjate llevar por esta historia de amor! ❤️"
    if any(x in s for x in ['familia', 'hermano', 'padre']):return "¡Una historia que celebra la familia! 👨‍👩‍👧‍👦"
    if any(x in s for x in ['espacio', 'planeta']):         return "¡Viaja más allá de las estrellas! 🌌"
    if any(x in s for x in ['terror', 'miedo']):            return "¡Atrévete a sentir el terror! 👻"
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
            print('TMDb movie:', data_movie)
            data_tv = r_tv.json()
            print('TMDb tv:', data_tv)
        
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

async def publish_tmdb_item(update: Update, item: dict):
    is_movie = item.get('is_movie', False)
    try:
        if is_movie:
            title = item.get('title', 'Sin título')
            id_ = item['id']
            details_url = f'https://api.themoviedb.org/3/movie/{id_}?api_key={TMDB_API_KEY}&language=es-ES&append_to_response=credits'
        else:
            title = item.get('name', 'Sin título')
            id_ = item['id']
            details_url = f'https://api.themoviedb.org/3/tv/{id_}?api_key={TMDB_API_KEY}&language=es-ES&append_to_response=credits'
        
        async with httpx.AsyncClient() as client:
            response = await client.get(details_url, timeout=10)
            details = response.json()
        
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
        
        await _send_formatted_reply(update, poster_url, caption)
            
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
    print("handle_message llamado")
    try:
        text = update.message.text.strip()
        found = await search_tmdb_and_show_options(update, context, text)
        
        if found:
            # Si hay una sola coincidencia, ya se publicó. Si hay varias, esperamos la selección.
            if context.user_data.get('matches'):
                return SELECTING
            return ConversationHandler.END

        # Si no hay resultados en TMDb, buscar en APIs de fallback
        poster, caption = await search_tvmaze(text)
        if caption:
            await _send_formatted_reply(update, poster, caption)
            return ConversationHandler.END

        poster, caption = await search_omdb(text)
        if caption:
            await _send_formatted_reply(update, poster, caption)
            return ConversationHandler.END

        await update.message.reply_text("No encontré nada con ese nombre 😢\nIntenta con otro título o verifica la ortografía.")
        return ConversationHandler.END

    except Exception as e:
        print(f"Error en handle_message: {e}")
        print(e)
        await update.message.reply_text("Hubo un error al procesar tu búsqueda. Intenta de nuevo.")
        return ConversationHandler.END

async def select_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("select_option llamado")
    options = context.user_data.get('matches')
    if not options:
        await update.message.reply_text('No hay opciones guardadas. Vuelve a empezar con /start.')
        return ConversationHandler.END
    try:
        idx = int(update.message.text.strip()) - 1
        if not (0 <= idx < len(options)):
            await update.message.reply_text('Opción inválida. Elige un número de la lista.')
            return SELECTING
        item = options[idx]
        await publish_tmdb_item(update, item)
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text('Por favor, responde con el número de la opción.')
        return SELECTING
    except Exception as e:
        logger.error(f"Error en select_option: {e}")
        await update.message.reply_text('Hubo un error. Intenta de nuevo.')
        context.user_data.clear()
        return ConversationHandler.END

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