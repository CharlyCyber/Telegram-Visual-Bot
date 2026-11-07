import httpx
import pytest
from visualbot import network


async def test_shared_pool_lifecycle():
    await network.shutdown_http(None)
    await network.initialize_http(None)
    original = network.get_client()
    async with network.shared_client() as first:
        assert first is original
    assert not original.is_closed
    async with network.shared_client() as second:
        assert second is first
    await network.shutdown_http(None)
    assert original.is_closed
    assert network._client is None
    # Cerrar dos veces no debe fallar.
    await network.shutdown_http(None)


async def test_request_errors_propagate(api):
    def timeout(request):
        raise httpx.ReadTimeout('timeout', request=request)
    api(timeout)
    with pytest.raises(httpx.ReadTimeout):
        await network.get_client().get('https://example.test')


async def test_http_error_not_treated_as_valid_json(api):
    api(lambda _: httpx.Response(500, json={'results': []}))
    with pytest.raises(httpx.HTTPStatusError):
        await network.get_client().get('https://example.test')
