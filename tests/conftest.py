"""Todas las pruebas son offline: una petición externa accidental falla."""
import httpx
import pytest
from visualbot import network, providers


@pytest.fixture(autouse=True)
async def offline_http(monkeypatch):
    def unexpected(request):
        raise AssertionError(f'Petición no simulada: {request.url.host}{request.url.path}')
    client = network.APIClient(transport=httpx.MockTransport(unexpected))
    monkeypatch.setattr(network, '_client', client)
    for search in (providers.search_tvmaze, providers.search_omdb, providers.search_catalog):
        search.cache_clear()
    yield
    await network.shutdown_http(None)
    await client.aclose()


@pytest.fixture
async def api(monkeypatch):
    """Instala respuestas simuladas por petición y devuelve el registro de URLs."""
    clients = []
    def install(handler):
        requests = []
        def dispatch(request):
            requests.append(request)
            return handler(request)
        client = network.APIClient(transport=httpx.MockTransport(dispatch))
        clients.append(client)
        monkeypatch.setattr(network, '_client', client)
        return requests
    yield install
    for client in clients:
        await client.aclose()
