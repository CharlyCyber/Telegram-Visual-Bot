from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import requests

BOT_TOKEN = '7726628351:AAGtS54WxgnTPDw1xvwREn-gFsl1WC9Eg9Q'  
CHAT_ID = -1002700094661
TMDB_API_KEY = '6be7b144ecef91b9d6eaf39946b5273f'

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Envíame el nombre y año de la película o serie (ejemplo: Inception 2010)')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    # Separar nombre y año
    try:
        name, year = text.rsplit(' ', 1)
    except ValueError:
        await update.message.reply_text('Por favor, envía el nombre y el año. Ejemplo: Inception 2010')
        return
    # Buscar en TMDb (películas)
    url = f'https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={name}&year={year}&language=es-ES'
    r = requests.get(url)
    data = r.json()
    if not data['results']:
        # Buscar en TMDb (series)
        url = f'https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={name}&first_air_date_year={year}&language=es-ES'
        r = requests.get(url)
        data = r.json()
        if not data['results']:
            await update.message.reply_text('No se encontró el material. Intenta con otro nombre o año.')
            return
        item = data['results'][0]
        title = item.get('name', 'Sin título')
        overview = item.get('overview', 'Sin sinopsis.')
        poster_path = item.get('poster_path')
        poster_url = f'https://image.tmdb.org/t/p/original{poster_path}' if poster_path else None
        genres = []
        # Obtener géneros de series
        tv_id = item['id']
        details_url = f'https://api.themoviedb.org/3/tv/{tv_id}?api_key={TMDB_API_KEY}&language=es-ES'
        details = requests.get(details_url).json()
        if 'genres' in details:
            genres = [g['name'] for g in details['genres']]
        genres_str = ', '.join(genres) if genres else 'Sin género'
        caption = f"🎬 {title} ({year}) 🎬\n\n📝 Sinopsis:\n{overview}\n\n🎞️ Géneros: {genres_str}"
    else:
        item = data['results'][0]
        title = item.get('title', 'Sin título')
        overview = item.get('overview', 'Sin sinopsis.')
        poster_path = item.get('poster_path')
        poster_url = f'https://image.tmdb.org/t/p/original{poster_path}' if poster_path else None
        genres = []
        # Obtener géneros de películas
        movie_id = item['id']
        details_url = f'https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}&language=es-ES'
        details = requests.get(details_url).json()
        if 'genres' in details:
            genres = [g['name'] for g in details['genres']]
        genres_str = ', '.join(genres) if genres else 'Sin género'
        caption = f"🎬 {title} ({year}) 🎬\n\n📝 Sinopsis:\n{overview}\n\n🎞️ Géneros: {genres_str}"
    if poster_url:
        await context.bot.send_photo(chat_id=CHAT_ID, photo=poster_url, caption=caption)
    else:
        await context.bot.send_message(chat_id=CHAT_ID, text=caption)

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
