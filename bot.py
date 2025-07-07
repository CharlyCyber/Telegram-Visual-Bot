import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = '7726628351:AAGtS54WxgnTPDw1xvwREn-gFsl1WC9Eg9Q'
CHAT_ID = -1002700094661
TMDB_API_KEY = '6be7b144ecef91b9d6eaf39946b5273f'

# Diccionario de emojis temáticos por género
genre_emojis_dict = {
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

# Diccionario de emojis por palabras clave en el título
title_keyword_emojis = {
    'luna': '🌙',
    'lunar': '🌙',
    'espacio': '🚀',
    'estrella': '⭐',
    'galaxia': '🌌',
    'mar': '🌊',
    'océano': '🌊',
    'amor': '❤️',
    'nav': '🚀',
    'avión': '✈️',
    'ballet': '🩰',
    'fuego': '🔥',
    'guerra': '⚔️',
    'robot': '🤖',
    'fantasma': '👻',
    'música': '🎵',
    'superhéroe': '🦸',
    'caballo': '🐎',
    'vaquero': '🤠',
    'familia': '👨‍👩‍👧‍👦',
    'misterio': '🕵️',
    'terror': '👻',
    'comedia': '😂',
    'drama': '🎭',
    'historia': '📜',
    'fantasía': '🧚',
    'deporte': '🏅',
}

# Diccionario de emojis contextuales para la sinopsis
synopsis_keyword_emojis = {
    'asesino': '🔪',
    'asesina': '🔪',
    'misterio': '🕵️',
    'amor': '❤️',
    'guerra': '⚔️',
    'espacio': '🚀',
    'luna': '🌙',
    'planeta': '🪐',
    'robot': '🤖',
    'futuro': '🔮',
    'ballet': '🩰',
    'baile': '💃',
    'familia': '👨‍👩‍👧‍👦',
    'amigos': '🤝',
    'venganza': '😠',
    'policía': '👮',
    'crimen': '🕵️',
    'viaje': '✈️',
    'mar': '🌊',
    'océano': '🌊',
    'monstruo': '👹',
    'fantasma': '👻',
    'música': '🎵',
    'superhéroe': '🦸',
    'poder': '💪',
    'magia': '✨',
    'rey': '🤴',
    'reina': '👸',
    'princesa': '👸',
    'príncipe': '🤴',
    'batalla': '⚔️',
    'fuga': '🏃',
    'carrera': '🏁',
    'investigación': '🔍',
    'secreto': '🤫',
    'sueño': '💤',
    'pesadilla': '😱',
    'dinero': '💰',
    'poder': '💪',
    'heroe': '🦸',
    'villano': '🦹',
    'extraterrestre': '👽',
    'alien': '👽',
    'fuga': '🏃',
    'rescate': '🆘',
    'explosión': '💥',
    'coche': '🚗',
    'auto': '🚗',
    'avión': '✈️',
    'nave': '🚀',
    'fuego': '🔥',
    'héroe': '🦸',
    'enemigo': '😈',
    'amigo': '🤝',
    'enemigos': '😈',
    'peligro': '⚠️',
    'secuestro': '🕵️',
    'investigador': '🕵️',
    'detective': '🕵️',
    'profesor': '👨‍🏫',
    'escuela': '🏫',
    'niño': '🧒',
    'niña': '👧',
    'joven': '🧑',
    'anciano': '🧓',
    'abuelo': '🧓',
    'abuela': '👵',
    'madre': '👩',
    'padre': '👨',
    'hermano': '👦',
    'hermana': '👧',
    'hijo': '🧒',
    'hija': '👧',
}

def get_genre_emojis(genres):
    emojis = [genre_emojis_dict.get(g, '🎬') for g in genres]
    return ' '.join(sorted(set(emojis)))

def get_keyword_emojis(title):
    title_lower = title.lower()
    emojis = [emoji for word, emoji in title_keyword_emojis.items() if word in title_lower]
    return ' '.join(sorted(set(emojis)))

def get_synopsis_with_emojis(synopsis):
    if not synopsis:
        return ''
    synopsis_lower = synopsis.lower()
    used_emojis = set()
    words = synopsis_lower.split()
    # Solo añadimos hasta 3 emojis contextuales para no sobrecargar
    for word in words:
        for key, emoji in synopsis_keyword_emojis.items():
            if key in word and emoji not in used_emojis:
                used_emojis.add(emoji)
                if len(used_emojis) >= 3:
                    break
        if len(used_emojis) >= 3:
            break
    # Insertamos los emojis al final de la sinopsis
    return f"{synopsis} {' '.join(used_emojis)}" if used_emojis else synopsis

def get_main_credits(credits, tipo='actor', max_count=3):
    if tipo == 'actor':
        cast = credits.get('cast', [])
        return ', '.join([c['name'] for c in cast[:max_count]]) if cast else ''
    else:
        crew = credits.get('crew', [])
        for c in crew:
            if c['job'] in ['Director', 'Directora']:
                return c['name']
        return ''

def get_awards_text():
    # TMDb no da premios, así que puedes poner "" para omitir si no hay info
    return ''

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

    # Construir mensaje solo con los campos disponibles
    lines = []
    # Título con emojis temáticos
    title_emojis = f"{keyword_emojis} {genre_emojis}".strip()
    lines.append(f"{title_emojis}🎬 <b>{title} ({year})</b> 🎬{title_emojis}")
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
    lines.append("\n¡No te pierdas esta emocionante historia! 🚀")
    # Firma personalizada
    lines.append("\n💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ")
    caption = '\n'.join(lines)

    if poster_url:
        await context.bot.send_photo(chat_id=CHAT_ID, photo=poster_url, caption=caption, parse_mode='HTML')
    else:
        await context.bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
