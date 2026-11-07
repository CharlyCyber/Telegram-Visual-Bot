"""Pruebas deterministas de búsquedas; no usan credenciales ni APIs reales."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from visualbot import handlers, providers


@pytest.fixture
def conversation():
    message = SimpleNamespace(text='Matrix', from_user=SimpleNamespace(id=123),
                              reply_text=AsyncMock(), reply_photo=AsyncMock())
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(user_data={}, bot=SimpleNamespace(
        get_chat_member=AsyncMock(return_value=SimpleNamespace(status='member')),
        send_photo=AsyncMock(), send_message=AsyncMock()))
    return update, context


async def test_spanish_matrix_search(api, conversation):
    def respond(request):
        assert request.url.params['language'] == 'es-ES'
        assert request.url.params['query'] == 'Matrix'
        results = [{'id': 1, 'title': 'Matrix', 'release_date': '1999-03-31'},
                   {'id': 2, 'title': 'Matrix Reloaded', 'release_date': '2003-05-15'}]
        return httpx.Response(200, json={'results': results if request.url.path.endswith('movie') else []})
    requests = api(respond)
    update, context = conversation
    assert await providers.search_tmdb_and_show_options(update, context, 'Matrix') is True
    assert len(requests) == 2
    assert len(context.user_data['matches']) == 2
    assert 'Matrix (1999)' in update.message.reply_text.call_args.args[0]


async def test_catalog_year_cache_and_mutation_isolation(api):
    def respond(request):
        params = request.url.params
        is_movie = request.url.path.endswith('movie')
        assert params['year' if is_movie else 'first_air_date_year'] == '1999'
        return httpx.Response(200, json={'results': [{'id': 1}] if is_movie else []})
    requests = api(respond)
    result = await providers.search_catalog('Matrix', '1999')
    assert result[0]['__type'] == 'movie'
    result[0]['id'] = 999
    assert (await providers.search_catalog('Matrix', '1999'))[0]['id'] == 1
    assert len(requests) == 2


async def test_single_match_publishes_without_options(api, conversation):
    def respond(request):
        if '/search/' in request.url.path:
            return httpx.Response(200, json={'results': [{'id': 1, 'title': 'Matrix'}]
                if request.url.path.endswith('movie') else []})
        return httpx.Response(200, json={'overview': 'Un programador descubre una simulación',
                                        'release_date': '1999-03-31'})
    api(respond)
    update, context = conversation
    await handlers.handle_message(update, context)
    assert 'options' not in context.user_data
    assert 'Matrix' in update.message.reply_text.call_args.kwargs['text']


@pytest.mark.parametrize('status', [401, 429, 500])
async def test_tmdb_http_errors_are_not_empty_results(api, conversation, status):
    api(lambda _: httpx.Response(status, json={'status_message': 'unavailable'}))
    with pytest.raises(providers.ProviderError):
        await providers.search_tmdb_and_show_options(*conversation, 'Matrix')


async def test_tvmaze_html_and_cache(api):
    requests = api(lambda _: httpx.Response(200, json=[{'show': {
        'name': 'Tom & Jerry', 'summary': '<p>Amor & aventura</p>',
        'premiered': '2020-01-01', 'genres': ['Animación']}}]))
    _, caption = await providers.search_tvmaze('Tom')
    assert 'Tom &amp; Jerry' in caption
    assert 'Amor' in caption
    assert await providers.search_tvmaze('Tom') == (None, caption)
    assert len(requests) == 1


async def test_failed_provider_is_not_cached(api):
    attempt = 0
    def respond(_):
        nonlocal attempt
        attempt += 1
        return httpx.Response(503) if attempt == 1 else httpx.Response(200, json=[{'show': {'name': 'Matrix'}}])
    api(respond)
    with pytest.raises(providers.ProviderError):
        await providers.search_tvmaze('Matrix')
    assert (await providers.search_tvmaze('Matrix'))[1]
    assert attempt == 2


async def test_primary_failure_uses_backup(api, conversation):
    def respond(request):
        if request.url.host == 'api.tvmaze.com':
            return httpx.Response(200, json=[{'show': {'name': 'Matrix'}}])
        return httpx.Response(503)
    api(respond)
    update, context = conversation
    await handlers.handle_message(update, context)
    context.bot.send_message.assert_awaited_once()


async def test_all_providers_down_propagates_error(api, conversation):
    api(lambda _: httpx.Response(503))
    with pytest.raises(providers.ProviderError):
        await handlers.handle_message(*conversation)


async def test_unauthorized_user_does_not_search(conversation, monkeypatch):
    update, context = conversation
    context.bot.get_chat_member.return_value.status = 'left'
    search = AsyncMock()
    monkeypatch.setattr(handlers, 'search_catalog', search)
    await handlers.handle_message(update, context)
    search.assert_not_awaited()


@pytest.mark.parametrize('failure', [RuntimeError('failed'), ValueError('failed')])
async def test_selection_does_not_mask_publication_failure(conversation, monkeypatch, failure):
    update, context = conversation
    update.message.text = '1'
    context.user_data['options'] = [{'id': 1, '__type': 'movie'}]
    monkeypatch.setattr(handlers, 'publish_tmdb_item', AsyncMock(side_effect=failure))
    with pytest.raises(type(failure), match='failed'):
        await handlers.select_option(update, context)


async def test_multiple_searches_have_no_user_quota(conversation, monkeypatch):
    search = AsyncMock(return_value=[])
    monkeypatch.setattr(handlers, 'search_catalog', search)
    for name in ('search_tvmaze', 'search_omdb', 'search_danfra', 'search_lamparaturca'):
        monkeypatch.setattr(handlers, name, AsyncMock(return_value=(None, None)))
    for _ in range(20):
        await handlers.handle_message(*conversation)
    assert search.await_count == 20
