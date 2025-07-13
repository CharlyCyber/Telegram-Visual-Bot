import os
import random
import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)

# ─────────── CONFIGURACIÓN ───────────
BOT_TOKEN   = os.getenv("BOT_TOKEN",   "7726628351:AAGtS54WxgnTPDw1xvwREn-gFsl1WC9Eg9Q")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "6be7b144ecef91b9d6eaf39946b5273f")
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "d06982f2")

# ─────────── DICCIONARIOS DE EMOJIS ───────────
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

# ─────────── FUNCIONES AUXILIARES ───────────
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

# ─────────── BÚSQUEDAS ───────────
def search_tvmaze(query):
    url = f'https://api.tvmaze.com/search/shows?q={query}'
    r = requests.get(url)
    data = r.json()
    if not data:
        return None, None
    show = data[0]['show']
    title  = show.get('name', 'Sin título')
    year   = show.get('premiered', '')[:4]
    overview = show.get('summary', '').replace('<p>', '').replace('</p>', '').replace('<b>', '').replace('</b>', '')
    genres   = show.get('genres', [])
    poster   = show['image']['original'] if show.get('image') else None
    runtime  = f"{show['runtime']} min" if show.get('runtime') else None
    rating   = show.get('rating', {}).get('average')
    cast_r   = requests.get(f'https://api.tvmaze.com/shows/{show["id"]}/cast').json()
    cast     = ', '.join([c['person']['name'] for c in cast_r[:4]]) if cast_r else ''

    genre_emojis  = get_genre_emojis(genres)
    keyword_emojis= get_keyword_emojis(title)
    overview_emo  = get_synopsis_with_emojis(overview)
    closing       = get_dynamic_closing(overview)

    lines = [
        f"{keyword_emojis} {genre_emojis} 🎬 <b>{title} ({year})</b> 🎬 {keyword_emojis} {genre_emojis}",
        "📺 Tipo: Serie",
    ]
    if overview:   lines.append(f"\n📝 <b>Sinopsis:</b>\n{overview_emo}")
    if cast:       lines.append(f"\n🎭 <b>Reparto:</b> {cast}")
    if runtime:    lines.append(f"\n🕒 <b>Duración:</b> {runtime}")
    if rating:     lines.append(f"\n⭐️ <b>Calificación:</b> {rating}/10")
    if genres:     lines.append(f"\n🎞️ <b>Géneros:</b> {', '.join(genres)} {genre_emojis}")
    lines.append(f"\n{closing}")
    lines.append("\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ")
    return poster, '\n'.join(lines)

def search_omdb(title, year=''):
    url = f'http://www.omdbapi.com/?t={title}&y={year}&apikey={OMDB_API_KEY}&plot=full'
    r = requests.get(url)
    data = r.json()
    if data.get('Response') != 'True':
        return None, None
    tit   = data.get('Title')
    ano   = data.get('Year')
    plot  = data.get('Plot')
    genres= data.get('Genre', '').split(', ')
    poster= data.get('Poster') if data.get('Poster') != 'N/A' else None
    runtime= data.get('Runtime')
    rating = data.get('imdbRating')
    cast   = data.get('Actors')
    director = data.get('Director')
    awards   = data.get('Awards')

    genre_emojis  = get_genre_emojis(genres)
    keyword_emojis= get_keyword_emojis(tit)
    plot_emo      = get_synopsis_with_emojis(plot)
    closing       = get_dynamic_closing(plot)

    lines = [
        f"{keyword_emojis} {genre_emojis} 🎬 <b>{tit} ({ano})</b> 🎬 {keyword_emojis} {genre_emojis}",
        f"🎬 Tipo: Película" if data.get('Type') == 'movie' else "📺 Tipo: Serie"
    ]
    if plot:        lines.append(f"\n📝 <b>Sinopsis:</b>\n{plot_emo}")
    if cast:        lines.append(f"\n🎭 <b>Reparto:</b> {cast}")
    if director:    lines.append(f"\n🎬 <b>Dirección:</b> {director}")
    if runtime:     lines.append(f"\n🕒 <b>Duración:</b> {runtime}")
    if rating:      lines.append(f"\n⭐️ <b>Calificación IMDb:</b> {rating}/10")
    if awards:      lines.append(f"\n🏆 <b>Premios:</b> {awards}")
    if genres:      lines.append(f"\n🎞️ <b>Géneros:</b> {', '.join(genres)} {genre_emojis}")
    lines.append(f"\n{closing}")
    lines.append("\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ")
    return poster, '\n'.join(lines)

# ─────────── HANDLERS ───────────
SELECTING = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Envíame el nombre de la película o serie (ejemplo: Inception)')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    poster, caption = search_tvmaze(text)
    if not poster:
        poster, caption = search_omdb(text)
    if poster:
        await update.message.reply_photo(photo=poster, caption=caption, parse_mode='HTML')
    else:
        await update.message.reply_text("No encontré nada con ese nombre 😢")

async def select_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Simplificado: si usas ConversationHandler tendrás que adaptar la lógica.
    await handle_message(update, context)
    return ConversationHandler.END

# ─────────── MAIN ───────────
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