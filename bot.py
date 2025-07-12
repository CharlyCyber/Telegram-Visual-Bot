import os
import requests
from requests.auth import HTTPBasicAuth
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
import random

BOT_TOKEN = '7726628351:AAGtS54WxgnTPDw1xvwREn-gFsl1WC9Eg9Q'
CHAT_ID = -1002700094661
TMDB_API_KEY = '6be7b144ecef91b9d6eaf39946b5273f'
TVMAZE_API_KEY = 'WT5t6vEvBf5sjNlLCqwn7NcLktyo2awz'
TVMAZE_USERNAME = ''  # Si tienes usuario de TVmaze, ponlo aquí. Si no, déjalo vacío.

# ... (toda la lógica de emojis y funciones auxiliares igual que antes)
# ... (omito aquí para no repetir, pero debes mantener las funciones de emojis, sinopsis, cierre, etc.)

# Añade esta función para buscar en TVmaze

def search_tvmaze(query):
    url = f'https://api.tvmaze.com/search/shows?q={query}'
    # TVmaze no requiere API Key para búsquedas públicas, pero si necesitas endpoints privados, usa HTTPBasicAuth
    r = requests.get(url)
    data = r.json()
    if not data:
        return None
    show = data[0]['show']
    # Extraer detalles relevantes
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
    main_cast = ''  # TVmaze requiere otra llamada para el cast
    director = ''   # No disponible en TVmaze
    awards = ''     # No disponible en TVmaze
    tipo_material = '📺 Tipo: Serie'  # TVmaze es principalmente para series
    # Obtener reparto principal
    cast_url = f'https://api.tvmaze.com/shows/{show["id"]}/cast'
    cast_r = requests.get(cast_url)
    cast_data = cast_r.json()
    if cast_data:
        main_cast = ', '.join([c['person']['name'] for c in cast_data[:4]])
    # Construir mensaje (usa las funciones auxiliares de emojis y cierre)
    genre_emojis = get_genre_emojis(genres)
    keyword_emojis = get_keyword_emojis(title)
    overview_with_emojis = get_synopsis_with_emojis(overview)
    closing = get_dynamic_closing(overview)
    lines = []
    title_emojis = f"{keyword_emojis} {genre_emojis}".strip()
    lines.append(f"{title_emojis}🎬 <b>{title} ({year})</b> 🎬{title_emojis}")
    lines.append(f"\n{tipo_material}")
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

# Modifica la función handle_message para buscar en TVmaze si TMDb falla

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        name, year = text.rsplit(' ', 1)
    except ValueError:
        await update.message.reply_text('Por favor, envía el nombre y el año. Ejemplo: Inception 2010')
        return

    # Buscar en TMDb (igual que antes...)
    # ...
    # Si no se encuentra en TMDb:
    if not data['results']:
        poster_url, caption = search_tvmaze(name)
        if not caption:
            await update.message.reply_text('No se encontró el material. Intenta con otro nombre o año.')
            return
        if poster_url:
            await context.bot.send_photo(chat_id=CHAT_ID, photo=poster_url, caption=caption, parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')
        return
    # ...
    # (El resto de la función igual que antes)
