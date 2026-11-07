"""Identidad de resultados a partir de datos explícitos, nunca del idioma o del sitio."""
import unicodedata

# Nombres frecuentes en catálogos audiovisuales. Otros nombres se conservan tal cual.
COUNTRIES = {
    'TR': 'Turquía', 'ES': 'España', 'MX': 'México', 'CO': 'Colombia',
    'BR': 'Brasil', 'US': 'Estados Unidos', 'GB': 'Reino Unido', 'AR': 'Argentina',
    'CU': 'Cuba', 'CL': 'Chile', 'VE': 'Venezuela', 'PE': 'Perú', 'EC': 'Ecuador',
    'DO': 'República Dominicana', 'PR': 'Puerto Rico', 'CA': 'Canadá',
    'FR': 'Francia', 'DE': 'Alemania', 'IT': 'Italia', 'PT': 'Portugal',
    'KR': 'Corea del Sur', 'JP': 'Japón', 'CN': 'China', 'IN': 'India',
    'TH': 'Tailandia', 'PH': 'Filipinas', 'TW': 'Taiwán', 'AU': 'Australia',
    'RU': 'Rusia', 'UA': 'Ucrania', 'PL': 'Polonia', 'SE': 'Suecia',
}
COUNTRY_ALIASES = {'turkey': 'TR', 'turkiye': 'TR', 'türkiye': 'TR',
                   'spain': 'ES', 'mexico': 'MX', 'brazil': 'BR',
                   'united states': 'US', 'united states of america': 'US',
                   'united kingdom': 'GB', 'south korea': 'KR'}


def one_line(value, limit=180):
    return ' '.join(str(value or '').split())[:limit]


def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', one_line(value)).casefold()
                   if not unicodedata.combining(c))


def country_text(value):
    if not isinstance(value, (list, tuple)):
        value = [value]
    result = []
    for country in value:
        if isinstance(country, dict):
            country = country.get('iso_3166_1') or country.get('identifier') or country.get('name')
        if not isinstance(country, str):
            continue
        country = one_line(country, 60)
        if not country or country.casefold() in ('n/a', 'n/d', 'unknown'):
            continue
        code = country.upper()
        code = COUNTRY_ALIASES.get(country.casefold(), code)
        if code not in COUNTRIES:
            code = next((key for key, name in COUNTRIES.items() if normalized(name) == normalized(country)), None)
        if code:
            flag = ''.join(chr(127397 + ord(char)) for char in code)
            text = f'{flag} {COUNTRIES[code]}'
        else:
            text = country
        if text not in result:
            result.append(text)
    return ', '.join(result[:4])


def media_label(item):
    kind = item.get('__type')
    if kind == 'web':
        kind = item.get('content_type')
    if kind is None:
        kind = 'movie' if item.get('is_movie') is True else 'tv' if item.get('is_movie') is False else None
    genre_ids = item.get('genre_ids') or []
    ids = {value for value in genre_ids if isinstance(value, int)} if isinstance(genre_ids, (list, tuple)) else set()
    genres = item.get('genres') or []
    if isinstance(genres, list):
        ids.update(g['id'] for g in genres if isinstance(g, dict) and isinstance(g.get('id'), int))
    if kind == 'movie':
        return '🎬 Película documental' if 99 in ids else '🎬 Película'
    if kind == 'tv':
        if 10766 in ids or item.get('type') == 'Soap':
            return '📺 Telenovela'
        if 10764 in ids or item.get('type') == 'Reality':
            return '📺 Reality'
        if 10767 in ids or item.get('type') == 'Talk Show':
            return '🎙️ Programa de entrevistas'
        if 99 in ids or item.get('type') == 'Documentary':
            return '📽️ Serie documental'
        if 16 in ids or item.get('type') == 'Animation':
            return '🎨 Serie de animación'
        return '📺 Serie'
    if kind == 'show':
        return '📺 Programa de televisión'
    return '📺 Audiovisual'


def identity_fields(item, title=None):
    title = title or item.get('title') or item.get('name') or ''
    fields = [('Tipo', media_label(item))]
    country = country_text(item.get('origin_country') or item.get('origin_countries'))
    if country:
        fields.append(('País de origen', country))
    original = one_line(item.get('original_name') or item.get('original_title'))
    if original and normalized(original) != normalized(title):
        fields.append(('Título original', original))
    aliases = item.get('alternate_names') or []
    if isinstance(aliases, str):
        aliases = [aliases]
    if not isinstance(aliases, (list, tuple)):
        aliases = []
    names = []
    for alias in aliases:
        if not isinstance(alias, str):
            continue
        name = one_line(alias, 100)
        if name and normalized(name) not in {normalized(n) for n in (title, original, *names)}:
            names.append(name)
    if names:
        fields.append(('Otros títulos', ' / '.join(names[:2])))
    return fields


def format_option(index, item):
    title = one_line(item.get('title') or item.get('name') or 'Sin título', 150)
    date = one_line(item.get('release_date') or item.get('first_air_date') or item.get('year'))[:4]
    fields = identity_fields(item, title)
    first = f"{index}. {title} ({date or 'N/D'}) · " + ' · '.join(
        value for label, value in fields if label in ('Tipo', 'País de origen'))
    if item.get('source'):
        first += ' · ' + one_line(item['source'], 60)
    extra = [f'   {label}: {value}' for label, value in fields if label not in ('Tipo', 'País de origen')]
    return '\n'.join([first, *extra])


async def send_options(message, items, introduction):
    # Más datos por ficha no deben exceder los 4096 caracteres de Telegram.
    chunk = introduction.rstrip() + '\n\n'
    for index, item in enumerate(items, 1):
        line = format_option(index, item) + '\n'
        if len((chunk + line).encode('utf-16-le')) // 2 > 4096:
            await message.reply_text(chunk.rstrip())
            chunk = ''
        chunk += line
    if chunk.strip():
        await message.reply_text(chunk.rstrip())
