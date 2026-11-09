"""Búsquedas y publicaciones de temporadas, sin llamadas externas."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup
import pytest

from visualbot import handlers, providers
from visualbot.formatting import utf16_length


@pytest.fixture
def conversation():
    message = SimpleNamespace(text='La isla 2025', from_user=SimpleNamespace(id=1),
                              reply_text=AsyncMock(), reply_photo=AsyncMock())
    context = SimpleNamespace(user_data={}, bot=SimpleNamespace(
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status='member')),
        send_photo=AsyncMock(), send_message=AsyncMock()))
    return SimpleNamespace(message=message), context


def fake_tmdb(request):
    path = request.url.path
    if path.endswith('/search/movie'):
        return httpx.Response(200, json={'results': []})
    if path.endswith('/search/tv'):
        assert 'first_air_date_year' not in request.url.params
        return httpx.Response(200, json={'results': [{'id': 7, 'name': 'La isla',
                                                     'first_air_date': '2020-01-01'}]})
    if '/season/' in path:
        number = int(path.split('/')[-1])
        return httpx.Response(200, json={'name': f'Edición {number} & más',
                                        'overview': f'Sinopsis de temporada {number}.',
                                        'credits': {'cast': [{'name': 'Persona & persona'}]}})
    return httpx.Response(200, json={
        'overview': 'Sinopsis general de la serie.', 'poster_path': '/serie.jpg',
        'first_air_date': '2020-01-01', 'number_of_seasons': 4, 'number_of_episodes': 90,
        'genres': [{'id': 10764, 'name': 'Reality'}],
        'credits': {'cast': [{'name': 'Reparto general'}]},
        'seasons': [
            {'season_number': 0, 'air_date': '2025-01-01'},
            {'season_number': 1, 'air_date': '2023-01-02', 'episode_count': 10},
            {'season_number': 2, 'air_date': '2024-02-03', 'episode_count': 12},
            {'season_number': 3, 'air_date': '2025-03-04', 'poster_path': '/temporada.jpg', 'episode_count': 14},
            {'season_number': 4, 'air_date': '2999-01-01'},
        ]})


async def test_year_search_publishes_matching_season_and_selects_previous(api, conversation):
    requests = api(fake_tmdb)
    update, context = conversation
    assert await handlers.handle_message(update, context) == handlers.SELECCIONANDO_TEMPORADA
    caption = update.message.reply_photo.call_args.kwargs['caption']
    text = BeautifulSoup(caption, 'html.parser').get_text()
    assert update.message.reply_photo.call_args.kwargs['photo'].endswith('/temporada.jpg')
    assert 'Temporada: 3' in text and 'Sinopsis de temporada 3' in text
    assert 'Estreno de temporada: 2025-03-04' in text
    assert 'Episodios de temporada: 14' in text
    assert 'Reparto: Persona & persona' in text and 'Reparto general' not in text
    assert 'Fuente: TMDb' in text and 'Sinopsis general' not in text
    assert utf16_length(text) <= 1024
    ElementTree.fromstring('<root>' + caption + '</root>')
    prompt = update.message.reply_text.call_args.args[0]
    assert '1. Temporada 3 (2025)' in prompt and '2. Temporada 2 (2024)' in prompt
    assert 'Temporada 0' not in prompt and 'Temporada 4' not in prompt
    update.message.text = '2'
    assert await handlers.select_season(update, context) == handlers.SELECCIONANDO_TEMPORADA
    text = BeautifulSoup(update.message.reply_photo.call_args.kwargs['caption'], 'html.parser').get_text()
    assert 'Temporada: 2' in text and 'Sinopsis de temporada 2' in text
    assert any('/season/2' in r.url.path for r in requests)
    update.message.text = '0'
    assert await handlers.select_season(update, context) == -1
    assert not context.user_data


async def test_latest_automatic_when_no_year(api, conversation):
    api(fake_tmdb)
    update, context = conversation
    update.message.text = 'La isla'
    await handlers.handle_message(update, context)
    assert 'Temporada:</b> 3' in update.message.reply_photo.call_args.kwargs['caption']


async def test_requested_older_year_is_used(api, conversation):
    api(fake_tmdb)
    update, context = conversation
    update.message.text = 'La isla 2024'
    await handlers.handle_message(update, context)
    assert 'Temporada:</b> 2' in update.message.reply_photo.call_args.kwargs['caption']


async def test_year_survives_program_selection(api, conversation):
    def respond(request):
        if request.url.path.endswith('/search/movie'):
            return httpx.Response(200, json={'results': [{'id': 8, 'title': 'La isla'}]})
        return fake_tmdb(request)
    api(respond)
    update, context = conversation
    assert await handlers.handle_message(update, context) == handlers.SELECCIONANDO
    update.message.text = '2'
    assert await handlers.select_option(update, context) == handlers.SELECCIONANDO_TEMPORADA
    assert 'Temporada:</b> 3' in update.message.reply_photo.call_args.kwargs['caption']


async def test_missing_year_offers_older_seasons_and_official_general(api, conversation, monkeypatch):
    api(fake_tmdb)
    official = {'__type': 'web', 'title': 'La isla', 'year': '2022', 'source': 'RTVE',
                'url': 'https://www.rtve.es/play/videos/la-isla/', 'description': 'Ficha general', 'image': None}
    search = AsyncMock(return_value=[official])
    monkeypatch.setattr(handlers, 'search_official_web', search)
    publish = AsyncMock()
    monkeypatch.setattr(handlers, 'publish_web_item', publish)
    update, context = conversation
    update.message.text = 'La isla 2022'
    assert await handlers.handle_message(update, context) == handlers.SELECCIONANDO_TEMPORADA
    search.assert_awaited_once_with('La isla', '2022')
    caption = update.message.reply_photo.call_args.kwargs['caption']
    assert 'Sinopsis general' in caption and 'Temporada:</b>' not in caption
    assert 'ficha general' in update.message.reply_text.call_args_list[0].args[0]
    assert '4. Ficha oficial general' in update.message.reply_text.call_args.args[0]
    update.message.text = '4'
    await handlers.select_season(update, context)
    publish.assert_awaited_once_with(context, official)


async def test_season_details_failure_uses_only_summary(api, conversation):
    def respond(request):
        if '/season/' in request.url.path:
            return httpx.Response(503)
        return fake_tmdb(request)
    api(respond)
    update, context = conversation
    await handlers.handle_message(update, context)
    caption = update.message.reply_photo.call_args.kwargs['caption']
    assert 'Temporada:</b> 3' in caption
    assert 'Sin descripción disponible' in caption
    assert 'Sinopsis general' not in caption and 'Reparto general' not in caption


def test_aired_seasons_filters_dates_and_specials():
    seasons = providers.aired_seasons([
        {'season_number': 0, 'air_date': '2023-01-01'},
        {'season_number': 1, 'air_date': '2023-01-01'},
        {'season_number': 2, 'air_date': '2024-01-01'},
        {'season_number': 3, 'air_date': None},
        {'season_number': 4, 'air_date': 'n/a'},
        {'season_number': True, 'air_date': '2023-01-01'},
        None,
    ], today=date(2023, 12, 31))
    assert [s['season_number'] for s in seasons] == [1]


async def test_invalid_selection_and_cancel(api, conversation):
    api(fake_tmdb)
    update, context = conversation
    await handlers.handle_message(update, context)
    update.message.text = '999'
    assert await handlers.select_season(update, context) == handlers.SELECCIONANDO_TEMPORADA
    assert 'inválida' in update.message.reply_text.call_args.args[0]
    assert await handlers.cancel(update, context) == -1
    assert not context.user_data


async def test_no_available_seasons_and_no_official_match(api, conversation, monkeypatch):
    def respond(request):
        response = fake_tmdb(request)
        if request.url.path.endswith('/tv/7'):
            return httpx.Response(200, json={'overview': 'Ficha general', 'seasons': [],
                                             'poster_path': '/serie.jpg'})
        return response
    api(respond)
    official = AsyncMock(return_value=[])
    monkeypatch.setattr(handlers, 'search_official_web', official)
    update, context = conversation
    assert await handlers.handle_message(update, context) == -1
    official.assert_awaited_once_with('La isla', '2025')
    assert 'ficha general' in update.message.reply_text.call_args.args[0]
    assert not context.user_data


async def test_season_selection_rechecks_membership(api, conversation):
    api(fake_tmdb)
    update, context = conversation
    await handlers.handle_message(update, context)
    context.bot.get_chat_member.return_value.status = 'left'
    update.message.text = '2'
    assert await handlers.select_season(update, context) == -1
    assert update.message.reply_photo.await_count == 1
    assert not context.user_data


async def test_season_options_are_split_with_stable_indices(conversation):
    update, _ = conversation
    seasons = [{'season_number': n, 'air_date': '2025-01-01', 'name': '😀' * 100}
               for n in range(1, 100)]
    await handlers.send_season_options(update.message, seasons, 1)
    messages = [call.args[0] for call in update.message.reply_text.call_args_list]
    assert len(messages) > 1
    assert all(utf16_length(text) <= 4096 for text in messages)
    assert '1. Temporada 1' in messages[0] and '99. Temporada 99' in messages[-1]
