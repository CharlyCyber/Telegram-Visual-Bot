"""Identificación sin inferir origen a partir del idioma, nombre o plataforma."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from xml.etree import ElementTree
import json

from bs4 import BeautifulSoup
import httpx
import pytest

from visualbot import handlers, providers, web_catalogs
from visualbot.formatting import render_tmdb_caption, utf16_length
from visualbot.result_labels import country_text, format_option, identity_fields, media_label, send_options
from visualbot.web_sources import SOURCES


def turkish_result():
    # Datos ficticios: no afirma equivalencia entre títulos concretos reales.
    return {'__type': 'tv', 'name': 'El secreto', 'original_name': 'Örnek Dizi',
            'first_air_date': '2025-10-01', 'origin_country': ['TR'], 'genre_ids': [10766]}


def test_turkish_soap_and_original_title_in_choices():
    text = format_option(1, turkish_result())
    assert '1. El secreto (2025)' in text
    assert 'Telenovela' in text
    assert '🇹🇷 Turquía' in text
    assert 'Título original: Örnek Dizi' in text


@pytest.mark.parametrize('item,label', [
    ({'__type': 'tv'}, 'Serie'),
    ({'__type': 'movie'}, 'Película'),
    ({'__type': 'tv', 'genre_ids': [10764]}, 'Reality'),
    ({'__type': 'tv', 'genre_ids': [10767]}, 'Programa de entrevistas'),
    ({'__type': 'tv', 'genre_ids': [99]}, 'Serie documental'),
    ({'__type': 'tv', 'genre_ids': [16]}, 'Serie de animación'),
    ({'__type': 'web', 'content_type': 'movie'}, 'Película'),
    ({'__type': 'web', 'content_type': 'show'}, 'Programa de televisión'),
    ({'__type': 'web'}, 'Audiovisual'),
])
def test_types_from_explicit_metadata(item, label):
    assert label in media_label(item)


def test_language_or_platform_country_is_not_origin():
    item = {'__type': 'tv', 'name': 'El secreto', 'original_language': 'tr',
            'source': 'Telemundo', 'network': {'country': {'code': 'US'}}}
    text = format_option(1, item)
    assert 'Turquía' not in text
    assert 'Estados Unidos' not in text
    assert 'Telenovela' not in text
    assert 'Serie' in text


@pytest.mark.parametrize('country', ['TR', 'Turkey', 'Türkiye', 'Turquía', {'@type': 'Country', 'name': 'Turkey'}])
def test_countries_accept_codes_or_explicit_names(country):
    assert country_text(country) == '🇹🇷 Turquía'


def test_coproduction_and_duplicate_countries():
    assert country_text(['TR', 'ES', 'TR']) == '🇹🇷 Turquía, 🇪🇸 España'
    assert country_text(None) == ''
    assert country_text('N/A') == ''


def test_no_duplicate_original_title_and_explicit_aliases_only():
    item = {'title': 'Rubí', 'original_title': 'Rubi', 'alternate_names': ['Rubi', 'Otro nombre', 'Otro nombre']}
    fields = dict(identity_fields(item))
    assert 'Título original' not in fields
    assert fields['Otros títulos'] == 'Otro nombre'
    assert 'Otros títulos' not in dict(identity_fields({'title': 'El secreto'}))


async def test_many_choices_are_split_with_continuous_numbers():
    message = SimpleNamespace(reply_text=AsyncMock())
    items = [dict(turkish_result(), name='Un nombre ' * 30, original_name='Título original ' * 30)] * 30
    await send_options(message, items, 'Elige una opción:')
    chunks = [call.args[0] for call in message.reply_text.await_args_list]
    assert len(chunks) > 1
    assert all(utf16_length(chunk) <= 4096 for chunk in chunks)
    assert chunks[0].startswith('Elige una opción:')
    assert '30. ' in chunks[-1]


def test_caption_shows_origin_before_synopsis_and_escapes_original():
    _, caption = render_tmdb_caption('El secreto', dict(turkish_result(),
        original_name='Örnek <Dizi> & amor', genres=[{'id': 10766, 'name': 'Soap'}]),
        False, 'Una historia de amor')
    assert 'Telenovela' in caption
    assert '🇹🇷 Turquía' in caption
    assert 'Örnek &lt;Dizi&gt; &amp; amor' in caption
    assert caption.index('Turquía') < caption.index('Sinopsis')
    ElementTree.fromstring('<root>' + caption + '</root>')


async def test_tmdb_choices_use_search_metadata_without_extra_requests(api):
    def respond(request):
        results = [dict(turkish_result(), id=1), {'id': 2, 'name': 'El secreto', 'origin_country': ['ES']}]
        return httpx.Response(200, json={'results': results if request.url.path.endswith('/tv') else []})
    requests = api(respond)
    update = SimpleNamespace(message=SimpleNamespace(reply_text=AsyncMock()))
    context = SimpleNamespace(user_data={})
    assert await providers.search_tmdb_and_show_options(update, context, 'El secreto')
    text = update.message.reply_text.call_args.args[0]
    assert 'Turquía' in text and 'España' in text
    assert len(requests) == 2


async def test_real_message_handler_includes_origin_in_options(monkeypatch):
    monkeypatch.setattr(handlers, 'search_catalog', AsyncMock(return_value=[turkish_result(),
        {'__type': 'movie', 'title': 'El secreto', 'release_date': '2006-01-01'}]))
    update = SimpleNamespace(message=SimpleNamespace(text='El secreto',
        from_user=SimpleNamespace(id=1), reply_text=AsyncMock()))
    context = SimpleNamespace(user_data={}, bot=SimpleNamespace(get_chat_member=AsyncMock(
        return_value=SimpleNamespace(status='member'))))
    await handlers.handle_message(update, context)
    text = update.message.reply_text.call_args.args[0]
    assert '🇹🇷 Turquía' in text
    assert 'Telenovela' in text and 'Película' in text
    assert len(context.user_data['options']) == 2


async def test_web_schema_country_and_aliases_reach_selection_and_publication():
    source = SOURCES[0]
    record = {'@type': 'TVSeries', 'name': 'El secreto', 'description': 'Una historia',
              'countryOfOrigin': {'@type': 'Country', 'name': 'Turkey'},
              'alternateName': ['Nombre alternativo']}
    html = '<script type="application/ld+json">' + json.dumps(record) + '</script>'
    item = web_catalogs.metadata(source, html, source.url('/shows/el-secreto'), 'El secreto')
    assert 'Turquía' in format_option(1, item)
    assert 'Nombre alternativo' in format_option(1, item)
    context = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
    await web_catalogs.publish_web_item(context, item)
    caption = context.bot.send_message.call_args.kwargs['text']
    assert 'Turquía' in caption
    assert 'Nombre alternativo' in caption
    assert 'Telenovela' not in caption  # TVSeries por sí solo no demuestra que sea novela.
    assert utf16_length(BeautifulSoup(caption, 'html.parser').get_text()) <= 4096
