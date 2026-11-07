"""HTML sintético representativo: estas fixtures NO prueban disponibilidad en vivo."""
import asyncio
from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from xml.etree import ElementTree

from bs4 import BeautifulSoup
import httpx
import pytest
from telegram.error import NetworkError

from visualbot import handlers, web_catalogs as web, web_http
from visualbot.config import FIRME, SELECCIONANDO
from visualbot.formatting import utf16_length
from visualbot.web_sources import SOURCES, enabled_sources

TELEMUNDO, ESTRELLAS, CARACOL, RTVE, GLOBO, ATRES = SOURCES


@pytest.fixture(autouse=True)
def no_crawler_wait(monkeypatch):
    # No desactivar la temporización de asyncio; solo las pausas de cortesía del crawler.
    pause = AsyncMock()
    monkeypatch.setattr(web_http, 'sleep', pause)
    monkeypatch.delenv('WEB_SOURCES', raising=False)
    return pause


def series_page(title='Pasión de Gavilanes', year='2003', extra=None):
    record = {'@type': 'TVSeries', 'name': title, 'description': 'Una historia de amor & justicia.',
              'startDate': year + '-01-01', 'image': 'https://media-cldnry.s-nbcnews.com/poster.jpg'}
    record.update(extra or {})
    return '<script type="application/ld+json">' + json.dumps({'@graph': [record]}) + '</script>'


def test_registry_is_configurable_without_keys(monkeypatch):
    assert len(enabled_sources()) == 6
    monkeypatch.setenv('WEB_SOURCES', 'rtve, caracol')
    assert enabled_sources() == (CARACOL, RTVE)
    monkeypatch.setenv('WEB_SOURCES', 'none')
    assert not enabled_sources()


@pytest.mark.parametrize('url', [
    'https://evil.example/shows/test', '//127.0.0.1/test', 'javascript:alert(1)',
    'https://www.telemundo.com@evil.example/shows/test',
    'https://www.telemundo.com:9999/shows/test',
    'https://www.telemundo.com:bad/shows/test',
    'https://www.telemundo.com/shows/%2e%2e/test', 'https://[bad',
])
def test_rejects_unsafe_urls(url):
    assert TELEMUNDO.url(url) is None


@pytest.mark.parametrize('source,path', [
    (TELEMUNDO, '/shows/pasion-de-gavilanes'),
    (ESTRELLAS, '/telenovelas/rubi'), (CARACOL, '/rosalinda'),
    (RTVE, '/play/videos/la-promesa/'), (GLOBO, '/o-clone/t/12345/'),
    (ATRES, '/antena3/series/el-secreto-de-puente-viejo/'),
    (ATRES, '/antena3/programas/el-hormiguero/'),
])
def test_official_catalog_link_patterns(source, path):
    assert source.is_title(source.url(path))


@pytest.mark.parametrize('source,path', [
    (TELEMUNDO, '/shows/pasion-de-gavilanes/capitulo-1'),
    (ESTRELLAS, '/telenovelas/rubi/noticia'), (CARACOL, '/rosalinda/capitulo-1'),
    (RTVE, '/play/videos/la-promesa/capitulo-1/123/'),
    (GLOBO, '/v/123/'), (ATRES, '/antena3/series/bandolera/temporada-1/'),
])
def test_news_and_episodes_not_discovered(source, path):
    assert not source.is_title(source.url(path))


def test_discovery_handles_accents_cards_slugs_and_duplicate_links():
    html = '''<a href="/shows/pasion-de-gavilanes"><h3>Pasión de Gavilanes</h3></a>
    <a href="/shows/pasion-de-gavilanes">series y novelas</a>
    <a href="https://evil.test/shows/pasion-de-gavilanes">Pasión de Gavilanes</a>
    <a href="/shows/pasion-de-gavilanes/capitulo-2">Pasión de Gavilanes</a>'''
    matches = web.discover(TELEMUNDO, html, 'https://www.telemundo.com/shows', 'Pasion de gavilanes')
    assert len(matches) == 1
    assert matches[0]['title'] == 'Pasión de Gavilanes'


def test_rtve_card_with_description_uses_title_attribute():
    html = '''<a href="/play/videos/la-promesa/" title="Ver todos los contenidos de 'La Promesa'">
    Series La Promesa Una mujer, una venganza y una historia de amor</a>'''
    assert web.discover(RTVE, html, RTVE.url(RTVE.catalogs[0]), 'La Promesa')[0]['title'] == 'La Promesa'


def test_jsonld_discovery_nested_item_list():
    html = '<script type="application/ld+json">' + json.dumps({'@type': 'ItemList', 'itemListElement': [
        {'@type': 'ListItem', 'item': {'name': 'Rubi', 'url': '/telenovelas/rubi'}}]}) + '</script>'
    assert len(web.discover(ESTRELLAS, html, ESTRELLAS.url('/telenovelas'), 'Rubí')) == 1


def test_common_word_does_not_match_every_show():
    assert web.relevance('Amor', 'Amor eterno') == 0
    assert web.relevance('Rubí', 'Rubi') == 1
    assert web.relevance('Betty', 'Betty en NY') == 0
    assert web.relevance('La Promesa', 'La Promesa') == 1


def test_schema_metadata_and_year_filter():
    url = TELEMUNDO.url('/shows/pasion-de-gavilanes')
    result = web.metadata(TELEMUNDO, series_page(), url, 'Pasion de Gavilanes', '2003')
    assert result['year'] == '2003'
    assert result['source'] == 'Telemundo'
    assert result['image'].startswith('https://media-cldnry.s-nbcnews.com/')
    assert web.metadata(TELEMUNDO, series_page(), url, 'Pasion de Gavilanes', '2022') is None


def test_open_graph_requires_relevant_title_and_description():
    html = '''<meta property="og:title" content="Rubí | Las Estrellas">
    <meta property="og:description" content="Una mujer ambiciosa">
    <meta property="og:image" content="http://st1.uvnimg.com/poster.jpg">'''
    result = web.metadata(ESTRELLAS, html, ESTRELLAS.url('/telenovelas/rubi'), 'Rubi')
    assert result['title'] == 'Rubí'
    assert result['year'] == ''
    assert result['image'].startswith('https://')
    assert web.metadata(ESTRELLAS, html, ESTRELLAS.url('/telenovelas/rubi'), 'Rubi', '2020') is None
    assert web.metadata(ESTRELLAS, html, ESTRELLAS.url('/telenovelas/rubi'), 'Teresa') is None


@pytest.mark.parametrize('kind', ['NewsArticle', 'Article', 'TVEpisode', 'VideoObject'])
def test_editorial_pages_not_published_as_series(kind):
    html = '<meta property="og:title" content="Rubí"><meta name="description" content="Noticia">'
    html += '<script type="application/ld+json">' + json.dumps({'@type': kind, 'name': 'Rubí'}) + '</script>'
    assert web.metadata(ESTRELLAS, html, ESTRELLAS.url('/telenovelas/rubi'), 'Rubi') is None


def test_soft_404_and_untrusted_images():
    assert web.metadata(TELEMUNDO, '<h1>Página no encontrada</h1>' + series_page(),
                        TELEMUNDO.url('/shows/test'), 'Pasion de Gavilanes') is None
    assert TELEMUNDO.image('https://127.0.0.1/private', TELEMUNDO.url('/')) is None
    assert TELEMUNDO.image('https://media-cldnry.s-nbcnews.com.evil.test/x', TELEMUNDO.url('/')) is None
    assert TELEMUNDO.image('https://www.telemundo.com:bad/x', TELEMUNDO.url('/')) is None


def test_deduplication_preserves_remakes():
    items = [{'title': 'Rubí', 'year': '2004'}, {'title': 'Rubi', 'year': '2004'},
             {'title': 'Rubí', 'year': '2020'}]
    assert len(web.deduplicate(items)) == 2


def test_robots_specific_agents_wildcards_and_allow_precedence():
    policy = web_http.parse_robots('''User-agent: *
    Disallow: /shows/*/episode
    Disallow: /search
    Allow: /shows/test/episode$
    Crawl-delay: 10
    User-agent: OtherBot
    Disallow: /
    ''')
    assert policy.delay == 10
    assert not policy.allows(TELEMUNDO.url('/shows/rubi/episode'))
    assert policy.allows(TELEMUNDO.url('/shows/test/episode'))
    assert not policy.allows(TELEMUNDO.url('/search'))
    assert policy.allows(TELEMUNDO.url('/shows/rubi'))
    specific = web_http.parse_robots('User-agent: *\nDisallow: /\nUser-agent: TelegramVisualBot\nAllow: /shows')
    assert specific.allows(TELEMUNDO.url('/shows/rubi'))


async def test_blocked_robots_prevents_catalog_request(api):
    requests = api(lambda _: httpx.Response(200, text='User-agent: *\nDisallow: /'))
    with pytest.raises(web_http.WebUnavailable):
        await web_http.fetch_html(TELEMUNDO, TELEMUNDO.url('/shows'))
    assert len(requests) == 1


@pytest.mark.parametrize('status', [403, 429, 500])
async def test_unavailable_robots_fails_closed(api, status):
    requests = api(lambda _: httpx.Response(status))
    with pytest.raises(web_http.WebUnavailable):
        await web_http.fetch_html(TELEMUNDO, TELEMUNDO.url('/shows'))
    assert len(requests) == 1


async def test_missing_robots_allows_html_and_caches(api, no_crawler_wait):
    def respond(request):
        if request.url.path == '/robots.txt':
            return httpx.Response(404)
        return httpx.Response(200, text='<h1>Shows</h1>', headers={'content-type': 'text/html'})
    requests = api(respond)
    url = TELEMUNDO.url('/shows')
    assert 'Shows' in await web_http.fetch_html(TELEMUNDO, url)
    assert 'Shows' in await web_http.fetch_html(TELEMUNDO, url)
    assert len(requests) == 2
    assert requests[1].headers['user-agent'] == web_http.USER_AGENT


async def test_crawl_delay_is_respected(api, no_crawler_wait):
    def respond(request):
        return (httpx.Response(200, text='User-agent: *\nCrawl-delay: 10')
                if request.url.path == '/robots.txt' else
                httpx.Response(200, text='<h1>Shows</h1>', headers={'content-type': 'text/html'}))
    api(respond)
    await web_http.fetch_html(TELEMUNDO, TELEMUNDO.url('/shows'))
    assert no_crawler_wait.call_args.args[0] > 9


@pytest.mark.parametrize('destination', ['https://127.0.0.1/private', 'https://evil.example/x', '/search'])
async def test_redirect_checked_before_following(api, destination):
    def respond(request):
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nDisallow: /search')
        return httpx.Response(302, headers={'location': destination})
    requests = api(respond)
    with pytest.raises(web_http.WebUnavailable):
        await web_http.fetch_html(TELEMUNDO, TELEMUNDO.url('/shows'))
    assert len(requests) == 2


async def test_backoff_after_429_does_not_keep_hitting_site(api):
    def respond(request):
        return httpx.Response(200, text='User-agent: *\nAllow: /') if request.url.path == '/robots.txt' else httpx.Response(429)
    requests = api(respond)
    for path in ('/shows', '/shows/rubi'):
        with pytest.raises(web_http.WebUnavailable):
            await web_http.fetch_html(TELEMUNDO, TELEMUNDO.url(path))
    assert len(requests) == 2


async def test_oversized_html_is_rejected(api, monkeypatch):
    monkeypatch.setattr(web_http, 'MAX_BYTES', 20)
    def respond(request):
        return httpx.Response(404) if request.url.path == '/robots.txt' else httpx.Response(
            200, text='x' * 21, headers={'content-type': 'text/html'})
    api(respond)
    with pytest.raises(web_http.WebUnavailable, match='grande'):
        await web_http.fetch_html(TELEMUNDO, TELEMUNDO.url('/shows'))


async def test_end_to_end_official_search_without_api(api, monkeypatch):
    monkeypatch.setenv('WEB_SOURCES', 'telemundo')
    def respond(request):
        assert '/api/' not in request.url.path
        if request.url.path == '/robots.txt':
            return httpx.Response(200, text='User-agent: *\nAllow: /')
        text = ('<a href="/shows/pasion-de-gavilanes"><h3>Pasión de Gavilanes</h3></a>'
                if request.url.path == '/shows' else series_page())
        return httpx.Response(200, text=text, headers={'content-type': 'text/html'})
    requests = api(respond)
    results = await web.search_official_web('Pasion de gavilanes', '2003')
    assert len(results) == 1
    assert results[0]['source'] == 'Telemundo'
    assert len(requests) == 3
    results[0]['title'] = 'changed'
    assert (await web.search_official_web('Pasion de gavilanes', '2003'))[0]['title'] != 'changed'
    assert len(requests) == 3


async def test_failed_optional_site_does_not_hide_working_site(monkeypatch):
    monkeypatch.setattr(web, 'enabled_sources', lambda: (TELEMUNDO, ESTRELLAS))
    async def fetch(source, url):
        if source == TELEMUNDO:
            raise web_http.WebUnavailable('blocked')
        if url.endswith('/telenovelas'):
            return '<a href="/telenovelas/rubi">Rubí</a>'
        return series_page('Rubí', '2004', {'image': None})
    monkeypatch.setattr(web, 'fetch_html', fetch)
    assert (await web.search_official_web('Rubi'))[0]['source'] == 'Las Estrellas'


async def test_search_deadline_keeps_results_and_cleans_pending_tasks(monkeypatch):
    monkeypatch.setattr(web, 'SEARCH_SECONDS', .02)
    monkeypatch.setattr(web, 'enabled_sources', lambda: (TELEMUNDO, ESTRELLAS))
    cancelled = asyncio.Event()
    async def fetch(source, url):
        if source == TELEMUNDO:
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        return ('<a href="/telenovelas/rubi">Rubí</a>' if url.endswith('/telenovelas') else series_page('Rubí'))
    monkeypatch.setattr(web, 'fetch_html', fetch)
    assert (await web.search_official_web('Rubi'))[0]['source'] == 'Las Estrellas'
    assert cancelled.is_set()


async def test_web_publication_safe_html_and_photo_fallback():
    context = SimpleNamespace(bot=SimpleNamespace(send_photo=AsyncMock(side_effect=NetworkError('bad image')),
                                                 send_message=AsyncMock()))
    item = {'title': 'Rubí & amor', 'year': '2004', 'description': '<amor> 😀 ' * 500,
            'source': 'Las Estrellas', 'url': ESTRELLAS.url('/telenovelas/rubi'), 'image': 'https://st1.uvnimg.com/poster'}
    await web.publish_web_item(context, item)
    context.bot.send_message.assert_awaited_once()
    caption = context.bot.send_message.call_args.kwargs['text']
    assert 'Rubí &amp; amor' in caption
    assert FIRME in caption
    assert 'Ficha oficial · Las Estrellas' in caption
    assert item['url'] in caption
    assert utf16_length(BeautifulSoup(caption, 'html.parser').get_text()) <= 1024
    ElementTree.fromstring('<root>' + caption + '</root>')


async def test_disabled_sources_make_no_requests(api, monkeypatch):
    monkeypatch.setenv('WEB_SOURCES', 'none')
    requests = api(lambda _: pytest.fail('No requests expected'))
    assert await web.search_official_web('Rubi') == []
    assert requests == []


def test_film_show_and_documentary_schema_supported():
    for kind in ('Movie', 'TVShow', 'CreativeWorkSeries'):
        html = series_page('Mi programa', extra={'@type': kind})
        assert web.metadata(TELEMUNDO, html, TELEMUNDO.url('/shows/mi-programa'), 'Mi programa')


def test_embedded_alternate_name_is_used_without_inventing_translation():
    html = series_page('O Clone', extra={'alternateName': 'El clon'})
    assert web.metadata(GLOBO, html, GLOBO.url('/o-clone/t/123/'), 'El clon')['title'] == 'O Clone'


async def test_all_optional_sites_blocked_return_empty_not_provider_error(monkeypatch):
    async def blocked(*args):
        raise web_http.WebUnavailable('blocked')
    monkeypatch.setattr(web, 'fetch_html', blocked)
    assert await web.search_official_web('Rubí') == []


async def test_outer_cancellation_cleans_up_children(monkeypatch):
    monkeypatch.setattr(web, 'enabled_sources', lambda: (TELEMUNDO,))
    started, stopped = asyncio.Event(), asyncio.Event()
    async def pending(*args):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()
    monkeypatch.setattr(web, 'fetch_html', pending)
    task = asyncio.create_task(web.search_official_web('Rubí'))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stopped.is_set()


def test_telemundo_promotional_title_suffix_is_not_part_of_name():
    value = 'Pasión de Gavilanes: Capítulos Completos, Elenco, Tráiler | Telemundo'
    assert web.clean_title(value) == 'Pasión de Gavilanes'
    html = f'<meta property="og:title" content="{value}"><meta name="description" content="Historia de tres hermanos">'
    assert web.metadata(TELEMUNDO, html, TELEMUNDO.url('/shows/pasion-de-gavilanes'), 'Pasion de Gavilanes')


def test_image_heading_and_embedded_trailer_on_series_landing_page():
    html = '''<h1><img alt="El Secreto de Puente Viejo"></h1>
    <meta name="description" content="La familia Mella llega a Puente Viejo.">
    <script type="application/ld+json">{"@type":"VideoObject","name":"Capítulo 1"}</script>'''
    result = web.metadata(ATRES, html, ATRES.url('/antena3/series/el-secreto-de-puente-viejo/'), 'El secreto de Puente Viejo')
    assert result['title'] == 'El Secreto de Puente Viejo'


def test_globoplay_promo_and_schema_url_types():
    assert web.clean_title('Assistir O Clone online no Globoplay') == 'O Clone'
    html = series_page('Mi película', extra={'@type': 'https://schema.org/Movie'})
    assert web.metadata(GLOBO, html, GLOBO.url('/mi-pelicula/t/123/'), 'Mi pelicula')


async def test_retry_after_is_honored(api):
    def respond(request):
        return httpx.Response(404) if request.url.path == '/robots.txt' else httpx.Response(
            429, headers={'retry-after': '600'})
    api(respond)
    before = web_http.monotonic()
    with pytest.raises(web_http.WebUnavailable):
        await web_http.fetch_html(TELEMUNDO, TELEMUNDO.url('/shows'))
    assert web_http._backoff[TELEMUNDO.host] >= before + 600
