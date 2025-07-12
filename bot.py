import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import random

BOT_TOKEN = '7726628351:AAGtS54WxgnTPDw1xvwREn-gFsl1WC9Eg9Q'
CHAT_ID = -1002700094661
TMDB_API_KEY = '6be7b144ecef91b9d6eaf39946b5273f'

# --- EMOJIS Y FUNCIONES AUXILIARES (igual que antes, omito para brevedad) ---
# ... (Pega aquí los diccionarios y funciones auxiliares de emojis, sinopsis, cierre, etc.)

# --- TVMAZE SEARCH (igual que antes) ---
def search_tvmaze(query):
    url = f'https://api.tvmaze.com/search/shows?q={query}'
    r = requests.get(url)
    data = r.json()
    if not data:
        return None, None
    show = data[0]['show']
    title = show.get('name', 'Sin título')
    year = show.get('premiered', '')[:4] if show.get('premiered') else ''
    overview = show.get('summary', '').replace('<p>','').replace('</p>','').replace('<b>','').replace('</b>','')
    genres = show.get('genres', [])
    genres_str = ', '.join(genres)
    poster_url = show['image']['original'] if show.get('image') and show['image'].get('original') else None
    release_date = show.get('premiered', '')
    runtime = show.get('runtime')
    if runtime:
        runtime = f"{runtime} min"
    vote_average = show.get('rating', {}).get('average')
    main_cast = ''
    cast_url = f'https://api.tvmaze.com/shows/{show["id"]}/cast'
    cast_r = requests.get(cast_url)
    cast_data = cast_r.json()
    if cast_data:
        main_cast = ', '.join([c['person']['name'] for c in cast_data[:4]])
    genre_emojis = get_genre_emojis(genres)
    keyword_emojis = get_keyword_emojis(title)
    overview_with_emojis = get_synopsis_with_emojis(overview)
    closing = get_dynamic_closing(overview)
    lines = []
    title_emojis = f"{keyword_emojis} {genre_emojis}".strip()
    lines.append(f"{title_emojis}🎬 <b>{title} ({year})</b> 🎬{title_emojis}")
    lines.append(f"\n📺 Tipo: Serie")
    if overview:
        lines.append(f"\n📝 <b>Sinopsis:</b>\n{overview_with_emojis}")
    if main_cast:
        lines.append(f"\n🎭 <b>Reparto principal:</b> {main_cast}")
    if runtime:
        lines.append(f"\n🕒 <b>Duración:</b> {runtime}")
    if release_date:
        lines.append(f"\n📅 <b>Estreno:</b> {release_date}")
    if vote_average:
        lines.append(f"\n⭐️ <b>Calificación:</b> {vote_average}/10")
    if genres_str:
        lines.append(f"\n🎞️ <b>Géneros:</b> {genres_str} {genre_emojis}")
    lines.append(f"\n{closing}")
    lines.append("\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ")
    caption = '\n'.join(lines)
    return poster_url, caption

# --- FLUJO INTERACTIVO ---
SELECTING, = range(1)

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
            # Buscar en TVmaze
            poster_url, caption = search_tvmaze(name)
            if not caption:
                await update.message.reply_text('No se encontró el material. Intenta con otro nombre o año.')
                return
            if poster_url:
                await context.bot.send_photo(chat_id=CHAT_ID, photo=poster_url, caption=caption, parse_mode='HTML')
            else:
                await context.bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
            return

    # Si hay más de una coincidencia, mostrar opciones
    if len(data['results']) > 1:
        context.user_data['options'] = data['results']
        context.user_data['is_movie'] = is_movie
        msg = 'Se encontraron varias coincidencias. Responde con el número de la opción que deseas publicar:\n\n'
        for idx, item in enumerate(data['results'], 1):
            if is_movie:
                title = item.get('title', 'Sin título')
                date = item.get('release_date', '')
            else:
                title = item.get('name', 'Sin título')
                date = item.get('first_air_date', '')
            msg += f"{idx}. {title} ({date[:4]})\n"
        await update.message.reply_text(msg)
        return SELECTING

    # Si solo hay una coincidencia, publicar directamente
    await publish_tmdb_item(update, context, data['results'][0], is_movie, year)

async def select_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(update.message.text.strip()) - 1
        options = context.user_data.get('options', [])
        is_movie = context.user_data.get('is_movie', True)
        if idx < 0 or idx >= len(options):
            await update.message.reply_text('Opción inválida. Intenta de nuevo.')
            return SELECTING
        item = options[idx]
        year = item.get('release_date', '')[:4] if is_movie else item.get('first_air_date', '')[:4]
        await publish_tmdb_item(update, context, item, is_movie, year)
        context.user_data.clear()
        return ConversationHandler.END
    except Exception:
        await update.message.reply_text('Por favor, responde con el número de la opción.')
        return SELECTING

async def publish_tmdb_item(update, context, item, is_movie, year):
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
    overview = details.get('overview', '')
    genres = [g['name'] for g in details.get('genres', [])]
    genres_str = ', '.join(genres)
    genre_emojis = get_genre_emojis(genres)
    keyword_emojis = get_keyword_emojis(title)
    poster_path = details.get('poster_path')
    poster_url = f'https://image.tmdb.org/t/p/original{poster_path}' if poster_path else None
    release_date = details.get('release_date') or details.get('first_air_date', '')
    runtime = details.get('runtime') or details.get('episode_run_time', [''])
    if isinstance(runtime, list):
        runtime = runtime[0] if runtime else ''
    if runtime:
        runtime = f"{runtime} min"
    vote_average = details.get('vote_average')
    main_cast = get_main_credits(credits, 'actor', 4)
    director = get_main_credits(credits, 'director')
    awards = get_awards_text()
    lines = []
    title_emojis = f"{keyword_emojis} {genre_emojis}".strip()
    lines.append(f"{title_emojis}🎬 <b>{title} ({year})</b> 🎬{title_emojis}")
    tipo_material = '🎬 Tipo: Película' if is_movie else '📺 Tipo: Serie'
    lines.append(f"\n{tipo_material}")
    if overview:
        overview_with_emojis = get_synopsis_with_emojis(overview)
        lines.append(f"\n📝 <b>Sinopsis:</b>\n{overview_with_emojis}")
    if main_cast:
        lines.append(f"\n🎭 <b>Reparto principal:</b> {main_cast}")
    if director:
        lines.append(f"\n🎬 <b>Dirección:</b> {director}")
    if runtime:
        lines.append(f"\n🕒 <b>Duración:</b> {runtime}")
    if release_date:
        lines.append(f"\n📅 <b>Estreno:</b> {release_date}")
    if vote_average:
        lines.append(f"\n⭐️ <b>Calificación IMDb:</b> {vote_average}/10")
    if awards:
        lines.append(f"\n🏆 <b>Premios:</b> {awards}")
    if genres_str:
        lines.append(f"\n🎞️ <b>Géneros:</b> {genres_str} {genre_emojis}")
    lines.append(f"\n{get_dynamic_closing(overview)}")
    lines.append("\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ")
    caption = '\n'.join(lines)
    if poster_url:
        await context.bot.send_photo(chat_id=CHAT_ID, photo=poster_url, caption=caption, parse_mode='HTML')
    else:
        await context.bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Envíame el nombre y año de la película o serie (ejemplo: Inception 2010)')

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)],
        states={
            SELECTING: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_option)]
        },
        fallbacks=[]
    )
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    app.run_polling()
