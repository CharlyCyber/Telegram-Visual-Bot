"""Formato HTML y vocabulario visual."""
import html
from bs4 import BeautifulSoup
from .config import FIRME, SEP, SEP_SOFT, SEP_STAR
import re

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


def render_tmdb_caption(title, details, is_movie, overview):
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

    # Reservar la firma y recortar texto, nunca cortar etiquetas o entidades HTML.
    limit = 1024 if poster_url else 4096
    signature = f"\n{SEP_STAR}\n{get_dynamic_closing()}{FIRME}"
    body = caption[:-len(signature)]
    budget = limit - utf16_length(BeautifulSoup(signature, 'html.parser').get_text())
    caption = fit_html(body, budget) + signature

    return poster_url, caption


def utf16_length(text):
    """Telegram cuenta caracteres usando unidades UTF-16, incluidos los emojis."""
    return len(text.encode('utf-16-le')) // 2


def fit_html(value, limit):
    """Acorta texto renderizado sin romper etiquetas, entidades ni emojis."""
    if limit < 1:
        return ''
    soup = BeautifulSoup(value, 'html.parser')
    if utf16_length(soup.get_text()) <= limit:
        return value
    remaining = limit - 1  # reservar el carácter de elipsis
    finished = False
    for node in list(soup.find_all(string=True)):
        if finished:
            node.extract()
            continue
        text = str(node)
        size = utf16_length(text)
        if size <= remaining:
            remaining -= size
            continue
        prefix = []
        for char in text:
            width = utf16_length(char)
            if width > remaining:
                break
            prefix.append(char)
            remaining -= width
        node.replace_with(''.join(prefix) + '…')
        finished = True
    return str(soup)
