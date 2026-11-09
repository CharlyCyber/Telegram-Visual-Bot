"""Estructuras HTML sintéticas; no sustituyen una prueba del sitio real."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from xml.etree import ElementTree

import httpx
import pytest
from bs4 import BeautifulSoup

from visualbot import handlers, mediaset, web_http, web_catalogs
from visualbot.formatting import utf16_length

CATALOG = '''<a href="/programas-tv/la-isla-de-las-tentaciones/">
    <img alt="La isla de las tentaciones"><b>La isla de las tentaciones</b></a>'''
PAGE = '''<html><head><title>La isla de las tentaciones T11 | Mediaset Infinity</title>
<script type="application/ld+json">%s</script></head><body>
<img alt="La isla de las tentaciones T11" src="https://img-prod-api2.mediasetplay.mediaset.it/p.jpg">
<a href="/programas-tv/la-isla-de-las-tentaciones/temporada-11">Logo</a>
<div>Temporada 11</div><div>Último episodio Mi lista VALORAR</div><div>2026 | Reality</div>
</body></html>''' % json.dumps({'@type': 'TVSeries', 'name': 'La isla de las tentaciones T11 | Mediaset Infinity',
                               'description': 'Cinco parejas & una prueba.'})
URL = mediaset.SOURCE.url('/programas-tv/la-isla-de-las-tentaciones/')


@pytest.fixture(autouse=True)
def no_delay(monkeypatch):
    monkeypatch.setattr(web_http, 'sleep', AsyncMock())
    monkeypatch.delenv('WEB_SOURCES', raising=False)


def site(request):
    if request.url.path == '/robots.txt':
        return httpx.Response(200, text='User-agent: *\nDisallow: /*?search')
    if request.url.path == '/programas-tv':
        return httpx.Response(200, text=CATALOG, headers={'content-type': 'text/html'})
    if request.url.path == '/programas-tv/la-isla-de-las-tentaciones/':
        return httpx.Response(200, text=PAGE, headers={'content-type': 'text/html'})
    return httpx.Response(404)


async def test_discovery_and_verified_season(api):
    requests = api(site)
    results = await mediaset.search_mediaset('La Isla de las Tentaciones', '2026')
    assert len(results) == 1
    item = results[0]
    assert item['season_number'] == 11 and item['year'] == '2026'
    assert item['url'].endswith('/temporada-11')
    assert item['description'] == 'Cinco parejas & una prueba.'
    assert item['image'].startswith('https://img-prod-api2.mediasetplay.mediaset.it/')
    assert [r.url.path for r in requests] == ['/robots.txt', '/programas-tv',
                                                '/programas-tv/la-isla-de-las-tentaciones/']
    assert await mediaset.search_mediaset('La isla de las tentaciones', '2025') == []


def test_no_season_if_title_or_link_does_not_match():
    assert mediaset.season_metadata(PAGE, URL, 'Otro programa') is None
    assert mediaset.season_metadata(PAGE.replace('/temporada-11', '/temporada-10'), URL,
                                    'La isla de las tentaciones') is None
    assert mediaset.season_metadata(PAGE.replace('/temporada-11', 'https://evil.test/temporada-11'), URL,
                                    'La isla de las tentaciones') is None
    assert mediaset.season_metadata(PAGE, 'https://evil.test/', 'La isla de las tentaciones') is None


def test_no_year_or_description_inferred_from_recommendations():
    page = PAGE.replace('2026 | Reality', '').replace('Cinco parejas & una prueba.', '')
    item = mediaset.season_metadata(page, URL, 'La isla de las tentaciones')
    assert item['year'] == '' and item['description'] == ''


async def test_no_year_does_not_match_year_query(api):
    def respond(request):
        response = site(request)
        if request.url.path.endswith('la-isla-de-las-tentaciones/'):
            return httpx.Response(200, text=PAGE.replace('2026 | Reality', ''),
                                  headers={'content-type': 'text/html'})
        return response
    api(respond)
    assert not await mediaset.search_mediaset('La isla de las tentaciones', '2026')


async def test_robots_and_configuration_block_requests(api, monkeypatch):
    requests = api(lambda _: httpx.Response(200, text='User-agent: *\nDisallow: /'))
    assert not await mediaset.search_mediaset('La isla de las tentaciones')
    assert [r.url.path for r in requests] == ['/robots.txt']
    monkeypatch.setenv('WEB_SOURCES', 'rtve')
    assert not await mediaset.search_mediaset('La isla de las tentaciones')
    assert len(requests) == 1


async def test_official_option_available_even_when_tmdb_found(monkeypatch):
    message = SimpleNamespace(text='1', from_user=SimpleNamespace(id=1), reply_text=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(user_data={}, bot=SimpleNamespace(
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status='member'))))
    item = mediaset.season_metadata(PAGE, URL, 'La isla de las tentaciones')
    monkeypatch.setattr(handlers, 'publish_tmdb_item', AsyncMock(return_value={
        'seasons': [{'season_number': 9, 'air_date': '2025-01-01'}], 'selected': 9}))
    monkeypatch.setattr(handlers, 'search_mediaset', AsyncMock(return_value=[item]))
    publish = AsyncMock()
    monkeypatch.setattr(handlers, 'publish_web_item', publish)
    assert await handlers.publish_selection(update, context,
                    {'__type': 'tv', 'name': 'La isla de las tentaciones'}) == handlers.SELECCIONANDO_TEMPORADA
    assert 'Temporada 11 (2026)' in message.reply_text.call_args.args[0]
    message.text = '2'
    assert await handlers.select_season(update, context) == handlers.SELECCIONANDO_TEMPORADA
    publish.assert_awaited_once_with(context, item)


async def test_official_only_when_tmdb_no_results(monkeypatch):
    update = SimpleNamespace(message=SimpleNamespace(text='La isla de las tentaciones 2026',
        from_user=SimpleNamespace(id=1), reply_text=AsyncMock()))
    context = SimpleNamespace(user_data={}, bot=SimpleNamespace(
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status='member'))))
    item = mediaset.season_metadata(PAGE, URL, 'La isla de las tentaciones')
    monkeypatch.setattr(handlers, 'search_catalog', AsyncMock(return_value=[]))
    monkeypatch.setattr(handlers, 'search_mediaset', AsyncMock(return_value=[item]))
    publish = AsyncMock()
    monkeypatch.setattr(handlers, 'publish_web_item', publish)
    assert await handlers.handle_message(update, context) == -1
    publish.assert_awaited_once_with(context, item)


async def test_official_caption_safe_and_attributed():
    item = mediaset.season_metadata(PAGE, URL, 'La isla de las tentaciones')
    context = SimpleNamespace(bot=SimpleNamespace(send_photo=AsyncMock(), send_message=AsyncMock()))
    await web_catalogs.publish_web_item(context, item)
    caption = context.bot.send_photo.call_args.kwargs['caption']
    text = BeautifulSoup(caption, 'html.parser').get_text()
    assert 'Temporada: 11' in text and 'Mediaset Infinity' in text
    assert 'Cinco parejas & una prueba.' in text
    assert utf16_length(text) <= 1024
    ElementTree.fromstring('<root>' + caption + '</root>')


async def test_timeout_does_not_block_other_sources(monkeypatch):
    import asyncio
    monkeypatch.setattr(mediaset, 'SEARCH_SECONDS', 0.01)
    async def slow(*args):
        await asyncio.sleep(1)
    monkeypatch.setattr(mediaset, '_search', slow)
    assert await mediaset.search_mediaset('La isla') == []


def test_episode_metadata_not_used_as_season_synopsis():
    episode = PAGE.replace('"@type": "TVSeries"', '"@type": "TVEpisode"')
    item = mediaset.season_metadata(episode, URL, 'La isla de las tentaciones')
    assert item['description'] == ''
