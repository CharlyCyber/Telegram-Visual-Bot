"""Descubrimiento conservador de fichas públicas de Mediaset Infinity.

No se adivinan URLs ni se consultan APIs privadas. La página general puede
presentar una edición concreta; solo la identificamos si el título y un enlace
oficial concuerdan explícitamente con el mismo número de temporada.
"""
import asyncio
import logging
import os
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .web_catalogs import discover, json_nodes, normalize
from .web_http import fetch_html, WebUnavailable
from .web_sources import WebSource

logger = logging.getLogger(__name__)
SEARCH_SECONDS = 15
SOURCE = WebSource('mediaset', 'Mediaset Infinity', 'www.mediasetinfinity.es',
                   ('/programas-tv',), r'/programas-tv/[^/]+/?',
                   ('mediasetplay.mediaset.it',))


def enabled():
    value = os.getenv('WEB_SOURCES')
    return value is None or 'mediaset' in {v.strip().lower() for v in value.split(',')}


def season_metadata(html, url, query):
    """Lee exclusivamente la temporada explícita de la cabecera de una ficha."""
    if not SOURCE.is_title(url):
        return None
    soup = BeautifulSoup(html, 'html.parser')
    if any(word in normalize(soup.title.get_text(' ', strip=True) if soup.title else '')
           for word in ('pagina no encontrada', 'access denied', 'captcha', 'error 404')):
        return None
    names = []
    if soup.title:
        names.append(soup.title.get_text(' ', strip=True))
    og = soup.find('meta', property='og:title')
    if og:
        names.append(og.get('content', ''))
    records = list(json_nodes(soup))
    for node in records:
        kind = node.get('@type', '')
        types = [kind] if isinstance(kind, str) else kind if isinstance(kind, list) else []
        if any(isinstance(t, str) and t.rsplit('/', 1)[-1] in ('TVSeries', 'TVSeason') for t in types):
            names.append(node.get('name', ''))

    for name in names:
        if not isinstance(name, str):
            continue
        name = name.split('|', 1)[0].strip()
        match = re.fullmatch(r'(.+?)\s+T(\d{1,3})', name, re.I)
        if not match or normalize(match.group(1)) != normalize(query):
            continue
        title, number = match.group(1), int(match.group(2))
        if number < 1:
            continue
        # Exigir un enlace real en la ficha al mismo programa y temporada.
        base = urlsplit(url).path.rstrip('/')
        expected = f'{base}/temporada-{number}'
        season_url = None
        for anchor in soup.select('a[href]'):
            link = SOURCE.url(anchor.get('href'), url)
            if link and urlsplit(link).path.rstrip('/') == expected:
                season_url = link
                break
        if not season_url:
            continue

        # El año visible debe estar junto a la cabecera de la misma temporada,
        # no en noticias, episodios recomendados o fecha de actualización.
        visible = soup.get_text(' ', strip=True)
        heading = re.search(r'\bTemporada\s+' + str(number) + r'\b', visible, re.I)
        year = ''
        if heading:
            excerpt = visible[heading.end():heading.end() + 250]
            match_year = re.search(r'\b((?:19|20)\d{2})\s*\|\s*[^|\d]', excerpt)
            if match_year:
                year = match_year.group(1)

        # Solo una descripción estructurada referida a esa misma edición.
        description = ''
        for node in records:
            node_name = str(node.get('name') or '').split('|', 1)[0].strip()
            kind = node.get('@type', '')
            types = [kind] if isinstance(kind, str) else kind if isinstance(kind, list) else []
            if (any(isinstance(t, str) and t.rsplit('/', 1)[-1] in ('TVSeries', 'TVSeason') for t in types)
                    and normalize(node_name) == normalize(name) and isinstance(node.get('description'), str)):
                description = BeautifulSoup(node['description'], 'html.parser').get_text(' ', strip=True)[:2000]
                break
        image = None
        for img in soup.select('img[alt]'):
            if normalize(img.get('alt', '')) == normalize(name):
                image = SOURCE.image(img.get('src'), url)
                if image:
                    break
        return {'__type': 'web', 'title': title, 'year': year, 'season_number': number,
                'description': description, 'url': season_url, 'source': SOURCE.name,
                'image': image, 'content_type': 'show'}
    return None


async def search_mediaset(query, year=None):
    if not enabled():
        return []
    try:
        return await asyncio.wait_for(_search(query, year), timeout=SEARCH_SECONDS)
    except (WebUnavailable, asyncio.TimeoutError):
        logger.info('Catálogo opcional de Mediaset no disponible')
        return []


async def _search(query, year):
    try:
        catalog_url = SOURCE.url(SOURCE.catalogs[0])
        catalog = await fetch_html(SOURCE, catalog_url)
        candidates = discover(SOURCE, catalog, catalog_url, query)
        # Solo coincidencia exacta; no unir programas distintos por parecido.
        candidates = [c for c in candidates if normalize(c['title']) == normalize(query)]
        for candidate in candidates[:3]:
            try:
                html = await fetch_html(SOURCE, candidate['url'])
                item = season_metadata(html, candidate['url'], query)
                if item and (not year or item['year'] == str(year)):
                    return [item]
            except WebUnavailable:
                continue
    except WebUnavailable:
        logger.info('Catálogo opcional de Mediaset no disponible')
    return []
