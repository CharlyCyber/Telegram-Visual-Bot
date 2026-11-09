"""Descubrimiento HTML oficial, relevancia, fichas y publicación segura."""
import asyncio
from difflib import SequenceMatcher
import json
import logging
import re
import unicodedata
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from telegram.error import TelegramError

from .cache import TTLCache
from .result_labels import identity_fields
from .config import FIRME, SEP_STAR
from .formatting import esc, fit_html, get_dynamic_closing, utf16_length
from .web_http import fetch_html, WebUnavailable
from .web_sources import enabled_sources

logger = logging.getLogger(__name__)
SEARCH_SECONDS = 28
MAX_RESULTS = 8
MEDIA_TYPES = {'TVSeries', 'Movie', 'TVShow', 'CreativeWorkSeries'}


def normalize(text):
    text = unicodedata.normalize('NFKD', str(text)).casefold()
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ' '.join(re.findall(r'\w+', text))


def clean_title(value):
    text = BeautifulSoup(str(value), 'html.parser').get_text(' ', strip=True)
    text = re.sub(r"^Ver todos los contenidos de ['\"](.+?)['\"]$", r'\1', text)
    text = re.sub(r'^(?:Saiba mais,|Assistir|Ver show:)\s*', '', text, flags=re.I)
    text = re.split(r'\s+[|–]\s+', text)[0]
    text = re.sub(r'\s*:\s*(?:capítulos completos|capitulos completos|ver capítulos|videos y fotos|elenco|tráiler).*$', '', text, flags=re.I)
    text = re.sub(r'\s+online(?:\s+no\s+Globoplay)?$', '', text, flags=re.I)
    text = re.sub(r'\s+-\s+(?:Telemundo|RTVE(?: Play)?|Ver gratis|Atresplayer|Globoplay|Las Estrellas|Serie española).*$','', text, flags=re.I)
    text = re.sub(r'\s*\((?:19|20)\d{2}\)\s*$', '', text)
    return text.strip()[:200]


def relevance(query, title):
    left, right = normalize(query), normalize(clean_title(title))
    if not left or not right:
        return 0
    if left == right:
        return 1.0
    # Un título de una sola palabra no debe recuperar cualquier novela de amor.
    if len(left.split()) == 1 or len(right.split()) == 1:
        return 0
    ratio = SequenceMatcher(None, left, right).ratio()
    return ratio if ratio >= 0.90 else 0


def json_nodes(soup):
    """JSON-LD insertado en HTML: no se consulta ningún endpoint JSON/API."""
    def walk(value, depth=0):
        if depth > 10:
            return
        if isinstance(value, dict):
            yield value
            for key in ('@graph', 'itemListElement', 'item', 'mainEntity'):
                yield from walk(value.get(key), depth + 1)
        elif isinstance(value, list):
            for item in value[:1000]:
                yield from walk(item, depth + 1)
    for script in soup.select('script[type="application/ld+json"]')[:30]:
        try:
            yield from walk(json.loads(script.string or script.get_text()))
        except (ValueError, RecursionError):
            continue


def discover(source, html, catalog_url, query):
    soup = BeautifulSoup(html, 'html.parser')
    found = {}
    def add(url, titles):
        url = source.url(url, catalog_url)
        if not url or not source.is_title(url):
            return
        for title in titles:
            title = clean_title(title)
            score = relevance(query, title)
            if score and (url not in found or score > found[url][0]):
                found[url] = (score, title)
    for node in json_nodes(soup):
        aliases = node.get('alternateName', [])
        aliases = [aliases] if isinstance(aliases, str) else aliases
        add(node.get('url') or node.get('@id'), [node.get('name', ''), *(aliases if isinstance(aliases, list) else [])])
    for anchor in soup.select('a[href]'):
        heading = anchor.find(re.compile(r'^h[1-6]$'))
        image = anchor.find('img')
        titles = [anchor.get('title', ''), anchor.get('aria-label', ''),
                  heading.get_text(' ', strip=True) if heading else '',
                  image.get('alt', '') if image else '', anchor.get_text(' ', strip=True)]
        # Algunas tarjetas solo dicen "+ info": el slug aporta el nombre, nunca una URL adivinada.
        url = source.url(anchor.get('href'), catalog_url)
        if url and source.is_title(url):
            parts = unquote(urlsplit(url).path).strip('/').split('/')
            slug = parts[-3] if source.key == 'globoplay' else parts[-1]
            titles.append(slug.replace('-', ' '))
        add(anchor.get('href'), titles)
    return [dict(url=url, title=title) for url, (_, title) in
            sorted(found.items(), key=lambda pair: (-pair[1][0], pair[0]))][:3]


def metadata(source, html, url, query, year=None):
    soup = BeautifulSoup(html, 'html.parser')
    # No convertir páginas 404 con recomendaciones, login o CAPTCHA en fichas.
    heading = soup.find('h1')
    heading_image = heading.find('img') if heading else None
    heading_title = (heading.get_text(' ', strip=True) if heading else '') or (
        heading_image.get('alt', '') if heading_image else '')
    marker = normalize((soup.title.get_text() if soup.title else '') + ' ' +
                       heading_title)
    if any(text in marker for text in ('pagina no encontrada', 'page not found', 'access denied',
                                       'just a moment', 'seccion no encontrada', 'captcha', 'error 404')):
        return None
    def meta(*names):
        for name in names:
            tag = soup.find('meta', property=name) or soup.find('meta', attrs={'name': name})
            if tag and tag.get('content'):
                return tag['content']
        return ''
    records = []
    for node in json_nodes(soup):
        types = node.get('@type', [])
        types = [types] if isinstance(types, str) else types
        if not isinstance(types, list):
            continue
        if any(t.rsplit('/', 1)[-1] in MEDIA_TYPES for t in types if isinstance(t, str)):
            records.append(node)
    # Los avances/episodios incrustados no convierten una portada de serie
    # en un episodio. Exigir H1 pertinente si solo existe schema VideoObject.
    if not records:
        for node in json_nodes(soup):
            kind = node.get('@type')
            kind = kind.rsplit('/', 1)[-1] if isinstance(kind, str) else ''
            linked = node.get('url') or node.get('@id')
            primary = not linked or source.url(linked, url) == url
            if primary and kind in ('NewsArticle', 'Article', 'TVEpisode'):
                return None
            if primary and kind == 'VideoObject' and not relevance(query, heading_title):
                return None
    for name in (meta('og:title'), heading_title):
        records.append({'name': name, 'description': meta('og:description', 'description'),
                        'image': meta('og:image')})
    for record in records:
        title = clean_title(record.get('name', ''))
        aliases = record.get('alternateName', [])
        aliases = [aliases] if isinstance(aliases, str) else aliases
        names = [title, *(aliases if isinstance(aliases, list) else [])]
        if not any(relevance(query, name) for name in names):
            continue
        description = BeautifulSoup(str(record.get('description') or ''), 'html.parser').get_text(' ', strip=True)
        # Una ficha sin datos no añade cobertura útil; no inventar sinopsis ni años.
        if not description:
            continue
        release = record.get('startDate') or record.get('datePublished') or ''
        match = re.match(r'((?:19|20)\d{2})(?:\D|$)', str(release))
        released = match.group(1) if match else ''
        # No usar la fecha de actualización de una página como estreno.
        if year and str(year) != released:
            continue
        return {'__type': 'web', 'title': title, 'year': released,
                'description': description[:2000], 'url': url, 'source': source.name,
                'image': source.image(record.get('image'), url),
                'origin_countries': record.get('countryOfOrigin'),
                'content_type': _content_type(record),
                'alternate_names': aliases if isinstance(aliases, list) else []}
    return None



def _content_type(record):
    types = record.get('@type', [])
    types = [types] if isinstance(types, str) else types
    if not isinstance(types, list):
        return None
    types = {value.rsplit('/', 1)[-1] for value in types if isinstance(value, str)}
    return 'movie' if 'Movie' in types else 'tv' if 'TVSeries' in types else 'show' if 'TVShow' in types else None


def deduplicate(items):
    result = []
    for item in items:
        duplicate = next((old for old in result if normalize(old['title']) == normalize(item['title'])
                          and (not old['year'] or not item['year'] or old['year'] == item['year'])), None)
        if duplicate is None:
            result.append(item)
        elif (not duplicate['year'] and item['year']):
            result[result.index(duplicate)] = item
    return result[:MAX_RESULTS]


@TTLCache(ttl_seconds=300, maxsize=128, cache_if=bool)
async def _search(query, year, sources):
    collected = []
    async def search_source(source):
        checked = set()
        for path in source.catalogs:
            catalog_url = source.url(path)
            try:
                html = await fetch_html(source, catalog_url)
                candidates = discover(source, html, catalog_url, query)
                for candidate in candidates:
                    url = candidate['url']
                    if url in checked:
                        continue
                    checked.add(url)
                    try:
                        page = await fetch_html(source, url)
                        item = metadata(source, page, url, query, year)
                        if item:
                            collected.append(item)
                    except WebUnavailable:
                        continue
            except WebUnavailable:
                logger.info('Catálogo web opcional no disponible: %s', source.name)
                continue
    tasks = [asyncio.create_task(search_source(source)) for source in sources]
    if not tasks:
        return []
    try:
        done, _ = await asyncio.wait(tasks, timeout=SEARCH_SECONDS)
        for task in done:
            task.result()  # Los errores de programación no se esconden como "sin resultados".
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    order = {source.name: i for i, source in enumerate(sources)}
    collected.sort(key=lambda item: (order[item['source']], -relevance(query, item['title']), item['url']))
    return deduplicate(collected)


async def search_official_web(query, year=None):
    return await _search(query.strip(), year, enabled_sources())


async def publish_web_item(context, item):
    from .config import CHAT_ID
    signature = (f"\n🌐 <a href='{esc(item['url'])}'>Ficha oficial · {esc(item['source'])}</a>\n"
                 f'{SEP_STAR}\n{get_dynamic_closing()}{FIRME}')
    title = esc(item['title']) + (f" ({esc(item['year'])})" if item['year'] else '')
    identity = '\n'.join(f'<b>{esc(label)}:</b> {esc(value)}' for label, value in identity_fields(item))
    season = (f"\n📚 <b>Temporada:</b> {esc(item['season_number'])}"
              if item.get('season_number') else '')
    description = esc(item['description']) if item.get('description') else '<i>Sin descripción disponible.</i>'
    body = (f'📺 <b>{title}</b>\n{identity}{season}\n\n'
            f"📝 {description}\n")
    limit = 1024 if item.get('image') else 4096
    caption = fit_html(body, limit - utf16_length(BeautifulSoup(signature, 'html.parser').get_text())) + signature
    if item.get('image'):
        try:
            await context.bot.send_photo(chat_id=CHAT_ID, photo=item['image'], caption=caption, parse_mode='HTML')
            return
        except TelegramError:
            logger.warning('No se pudo enviar la imagen oficial; se enviará texto')
    await context.bot.send_message(chat_id=CHAT_ID, text=caption, parse_mode='HTML')


def clear_search_cache():
    _search.cache_clear()
