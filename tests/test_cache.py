"""Caducidad, capacidad y aislamiento de resultados almacenados."""
from unittest.mock import AsyncMock
import pytest
from visualbot.cache import TTLCache


async def test_cache_expires_and_removes_old_entries():
    now = [0]
    cache = TTLCache(ttl_seconds=5, maxsize=2, clock=lambda: now[0])
    source = AsyncMock(return_value={'value': 1})
    source.__name__ = 'source'
    lookup = cache(source)
    await lookup('a')
    now[0] = 4
    await lookup('a')
    assert source.await_count == 1
    now[0] = 5
    await lookup('b')
    assert len(cache.cache) == 1
    await lookup('a')
    assert source.await_count == 3


async def test_cache_lru_capacity_and_copy():
    cache = TTLCache(maxsize=2)
    calls = []
    @cache
    async def lookup(key):
        calls.append(key)
        return [{'key': key}]
    result = await lookup('a')
    result[0]['key'] = 'changed'
    await lookup('b')
    assert (await lookup('a'))[0]['key'] == 'a'
    await lookup('c')  # b is the least recently used
    assert len(cache.cache) == 2
    await lookup('b')
    assert calls == ['a', 'b', 'c', 'b']
    lookup.cache_clear()
    assert not cache.cache


async def test_cache_never_stores_exceptions_or_rejected_results():
    cache = TTLCache(cache_if=bool)
    attempts = 0
    @cache
    async def lookup():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError('unavailable')
        return [] if attempts == 2 else ['ok']
    with pytest.raises(RuntimeError):
        await lookup()
    assert await lookup() == []
    assert await lookup() == ['ok']
    assert await lookup() == ['ok']
    assert attempts == 3


@pytest.mark.parametrize('kwargs', [{'ttl_seconds': 0}, {'maxsize': 0}])
def test_invalid_cache_configuration(kwargs):
    with pytest.raises(ValueError):
        TTLCache(**kwargs)
