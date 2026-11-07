"""Caché TTL/LRU acotada; no restringe búsquedas ni usuarios."""
from collections import OrderedDict
from copy import deepcopy
from functools import wraps
from time import monotonic


class TTLCache:
    def __init__(self, ttl_seconds=300, maxsize=256, *, cache_if=None, clock=monotonic):
        if ttl_seconds <= 0 or maxsize <= 0:
            raise ValueError("TTL y tamaño de caché deben ser positivos")
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self.cache_if = cache_if or (lambda result: True)
        self.clock = clock
        self.cache = OrderedDict()

    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            now = self.clock()
            for expired in [key for key, (expiry, _) in self.cache.items() if expiry <= now]:
                del self.cache[expired]
            key = (func.__name__, args, tuple(sorted(kwargs.items())))
            if key in self.cache:
                self.cache.move_to_end(key)
                return deepcopy(self.cache[key][1])
            result = await func(*args, **kwargs)
            if self.cache_if(result):
                self.cache[key] = (self.clock() + self.ttl, deepcopy(result))
                self.cache.move_to_end(key)
                while len(self.cache) > self.maxsize:
                    self.cache.popitem(last=False)
            return result
        wrapper.cache_clear = self.cache.clear
        return wrapper
