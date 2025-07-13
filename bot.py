import os
import requests
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler

BOT_TOKEN = os.getenv("BOT_TOKEN", "7726628351:AAGtS54WxgnTPDw1xvwREn-gFsl1WC9Eg9Q")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "6be7b144ecef91b9d6eaf39946b5273f")
CHAT_ID = -1002700094661

# Diccionarios de emojis (igual que antes)
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
def get_genre_emojis(genres):
    return ' '.join(sorted({genre_emojis_dict.get(g, '🎬') for g in genres}))

def get_keyword_emojis(title):
    t = title.lower()
    return ' '.join({e for k, e in title_keyword_emojis.items() if k in t})

def get_synopsis_with_emojis(synopsis):
    if not synopsis:
        return ''
    used = set()
    for w in synopsis.lower().split():
        for k, e in synopsis_keyword_emojis.items():
            if k in w and e not in used:
                used.add(e)
                if len(used) == 3:
                    break
        if len(used) == 3:
            break
    return f"{synopsis} {' '.join(used)}" if used else synopsis

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

# --- Búsqueda en TMDb y lógica de coincidencias ---
user_matches = {}

async def search_tmdb_and_show_options(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    url_movie = f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={query}&language=es-ES'
    url_tv = f'https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&language=es-ES'
    r_movie = requests.get(url_movie)
    r_tv = requests.get(url_tv)
    data_movie = r_movie.json()
    data_tv = r_tv.json()
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
        await publish_tmdb_item(update, context, results[0], results[0]['is_movie'])
        return True
    # Mostrar opciones
    user_matches[update.effective_user.id] = results
    msg = 'Se encontraron varias coincidencias. Responde con el número de la opción que deseas publicar:\n\n'
    for idx, item in enumerate(results, 1):
        title = item.get('title') or item.get('name', 'Sin título')
        date = item.get('release_date') or item.get('first_air_date', '')
        tipo = 'Película' if item['is_movie'] else 'Serie'
        msg += f"{idx}. {title} ({date[:4] if date else 'N/D'}) [{tipo}]\n"
    await update.message.reply_text(msg)
    return True

async def publish_tmdb_item(update, context, item, is_movie):
    if is_movie:
        title = item.get('title', 'Sin título')
        id_ = item['id']
        details_url = f'https://api.themoviedb.org/3/movie/{id_}?api_key={TMDB_API_KEY}&language=es-ES&append_to_response=credits'
    else:
        title = item.get('name', 'Sin título')
        id_ = item['id']
        details_url = f'https://api.themoviedb.org/3/tv/{id_}?api_key={TMDB_API_KEY}&language=es-ES&append_to_response=credits'
    details = requests.get(details_url).json()
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
    lines.append(f"\n{get_dynamic_closing(overview)}")
    lines.append("\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ")
    caption = '\n'.join(lines)
    if poster_url:
        await update.message.reply_photo(photo=poster_url, caption=caption, parse_mode='HTML')
    else:
        await update.message.reply_text(caption, parse_mode='HTML')
SELECTING = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Envíame el nombre de la película o serie (ejemplo: Inception)')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    found = await search_tmdb_and_show_options(update, context, text)
    if not found:
        # Si no hay resultados en TMDb, buscar en TVmaze y OMDb
        poster, caption = search_tvmaze(text)
        if not poster:
            poster, caption = search_omdb(text)
        if poster:
            await update.message.reply_photo(photo=poster, caption=caption, parse_mode='HTML')
        else:
            await update.message.reply_text("No encontré nada con ese nombre 😢")

async def select_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    options = user_matches.get(user_id)
    if not options:
        await update.message.reply_text('No hay opciones guardadas. Escribe el nombre de la película o serie.')
        return ConversationHandler.END
    try:
        idx = int(update.message.text.strip()) - 1
        if idx < 0 or idx >= len(options):
            await update.message.reply_text('Opción inválida. Intenta de nuevo.')
            return SELECTING
        item = options[idx]
        await publish_tmdb_item(update, context, item, item['is_movie'])
        del user_matches[user_id]
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text('Por favor, responde con el número de la opción.')
        return SELECTING

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start),
                      MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            SELECTING: [MessageHandler(filters.Regex(r'^\d+$'), select_option)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    app.add_handler(conv_handler)
    app.run_polling()
