import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = '7726628351:AAGtS54WxgnTPDw1xvwREn-gFsl1WC9Eg9Q'
CHAT_ID = -1002700094661
TMDB_API_KEY = '6be7b144ecef91b9d6eaf39946b5273f'

# Diccionario de emojis temáticos por género
GENRE_EMOJIS = {
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

def get_genre_emojis(genres):
    emojis = [GENRE_EMOJIS.get(g, '🎬') for g in genres]
    return ' '.join(emojis)

def get_main_credits(credits, tipo='actor', max_count=3):
    if tipo == 'actor':
        cast = credits.get('cast', [])
        return ', '.join([c['name'] for c in cast[:max_count]]) if cast else 'No disponible'
    else:
        crew = credits.get('crew', [])
        for c in crew:
            if c['job'] in ['Director', 'Directora']:
                return c['name']
        return 'No disponible'

def get_awards_text():
    # TMDb no da premios, así que puedes poner "No disponible" o buscar en IMDb si quieres ampliar
    return 'No disponible'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Envíame el nombre y año de la película o serie (ejemplo: Inception 2010)')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        name, year = text.rsplit(' ', 1)
    except ValueError:
        await update.message.reply_text('Por favor, envía el nombre y el año. Ejemplo: Inception 2010')
        return

    # Buscar en TMDb (películas)
    url = f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={name}&year={year}&language=es-ES'
    r = requests.get(url)
    data = r.json()
    is_movie = True

    if not data['results']:
        # Buscar en TMDb (series)
        url = f'https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={name}&first_air_date_year={year}&language=es-ES'
        r = requests.get(url)
        data = r.json()
        is_movie = False
        if not data['results']:
            await update.message.reply_text('No se encontró el material. Intenta con otro nombre o año.')
            return

    item = data['results'][0]
    if is_movie:
        title = item.get('title', 'Sin título')
        id_ = item['id']
        details_url = f'https://api.themoviedb.org/3/movie/{id_}?api_key={TMDB_API_KEY}&language=es-ES'
        credits_url = f'https://api.themoviedb.org/3/movie/{id_}/credits?api_key={TMDB_API_KEY}&language=es-ES'
    else:
        title = item.get('name', 'Sin título')
        id_ = item['id']
        details_url = f'https://api.themoviedb.org/3/tv/{id_}?api_key={TMDB_API_KEY}&language=es-ES'
        credits_url = f'https://api.themoviedb.org/3/tv/{id_}/credits?api_key={TMDB_API_KEY}&language=es-ES'

    details = requests.get(details_url).json()
    credits = requests.get(credits_url).json()

    # Detalles
    overview = details.get('overview', 'Sin sinopsis.')
    genres = [g['name'] for g in details.get('genres', [])]
    genres_str = ', '.join(genres) if genres else 'Sin género'
    genre_emojis = get_genre_emojis(genres)
    poster_path = details.get('poster_path')
    poster_url = f'https://image.tmdb.org/t/p/original{poster_path}' if poster_path else None
    release_date = details.get('release_date') or details.get('first_air_date', 'No disponible')
    runtime = details.get('runtime') or details.get('episode_run_time', ['No disponible'])
    if isinstance(runtime, list):
        runtime = runtime[0] if runtime else 'No disponible'
    if runtime != 'No disponible':
        runtime = f"{runtime} min"
    vote_average = details.get('vote_average', 'No disponible')
    main_cast = get_main_credits(credits, 'actor', 4)
    director = get_main_credits(credits, 'director')
    awards = get_awards_text()

    # Plantilla motivadora y detallada
    caption = f"""
{genre_emojis}🎬 <b>{title} ({year})</b> 🎬{genre_emojis}

📝 <b>Sinopsis:</b>
{overview}

🎭 <b>Reparto principal:</b> {main_cast}
🎬 <b>Dirección:</b> {director}
🕒 <b>Duración:</b> {runtime}
📅 <b>Estreno:</b> {release_date}
⭐️ <b>Calificación IMDb:</b> {vote_average}/10
🏆 <b>Premios:</b> {awards}
🎞️ <b>Géneros:</b> {genres_str} {genre_emojis}

¡No te pierdas esta emocionante historia! 🚀
"""

    if poster_url:
        await context.bot.send_photo(chat_id=CHAT_ID, photo=poster_url, caption=caption, parse_mode='HTML')
    else:
        await context.bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
