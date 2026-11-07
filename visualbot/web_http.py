"""Acceso prudente a HTML: robots, dominio cerrado, caché y presupuestos."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import math
import re
from time import monotonic
from urllib.parse import urlsplit, unquote

import httpx
from .cache import TTLCache
from .network import shared_client

logger = logging.getLogger(__name__)
USER_AGENT = 'TelegramVisualBot/1.0'
MAX_BYTES = 2 * 1024 * 1024
sleep = asyncio.sleep


class WebUnavailable(Exception):
    """Fuente opcional bloqueada, temporalmente caída o con respuesta inválida."""


@dataclass
class RobotsPolicy:
    rules: list = field(default_factory=list)
    delay: float = 1.0
    blocked: bool = False

    def allows(self, url):
        if self.blocked:
            return False
        parsed = urlsplit(url)
        path = unquote(parsed.path) + ('?' + parsed.query if parsed.query else '')
        matches = []
        for allow, rule in self.rules:
            end = rule.endswith('$')
            pattern = rule[:-1] if end else rule
            pattern = '^' + '.*'.join(re.escape(part) for part in pattern.split('*'))
            if re.search(pattern + ('$' if end else ''), path):
                matches.append((len(rule.replace('*', '').rstrip('$')), allow))
        return max(matches)[1] if matches else True


def parse_robots(text):
    groups, agents, directives = [], [], []
    for line in text.splitlines():
        key, sep, value = line.split('#', 1)[0].partition(':')
        if not sep:
            continue
        key, value = key.strip().lower(), value.strip()
        if key == 'user-agent':
            if directives:
                groups.append((agents, directives))
                agents, directives = [], []
            agents.append(value.lower())
        elif agents and key in ('allow', 'disallow', 'crawl-delay'):
            directives.append((key, value))
    groups.append((agents, directives))
    selected, longest = [], -1
    for agents, directives in groups:
        specificity = max((0 if agent == '*' else len(agent) for agent in agents
                           if agent == '*' or agent in USER_AGENT.lower()), default=-1)
        if specificity > longest:
            selected, longest = [], specificity
        if specificity == longest and specificity >= 0:
            selected.extend(directives)
    rules, delay = [], 1.0
    for key, value in selected:
        if key in ('allow', 'disallow') and value:
            rules.append((key == 'allow', value))
        elif key == 'crawl-delay':
            try:
                number = float(value)
                if math.isfinite(number) and number >= 0:
                    delay = max(delay, number)
            except ValueError:
                pass
    return RobotsPolicy(rules, delay)


# Como máximo seis estados de dominio; no se crean a partir de URLs del usuario.
_locks = {}
_last_request = {}
_backoff = {}
_host_delay = {}


async def _read(source, url, *, robots=False, delay=1.0, redirects=0):
    if redirects > 3 or source.url(url) != url:
        raise WebUnavailable('URL fuera del catálogo permitido')
    host = source.host
    delay = max(delay, _host_delay.get(host, 1.0))
    lock = _locks.setdefault(host, asyncio.Lock())
    async with lock:
        if _backoff.get(host, 0) > monotonic():
            raise WebUnavailable('Fuente en pausa temporal')
        wait = delay - (monotonic() - _last_request.get(host, float('-inf')))
        if wait > 0:
            await sleep(wait)
        _last_request[host] = monotonic()
        try:
            async with shared_client() as client:
                async with client.stream('GET', url, timeout=5, follow_redirects=False,
                                         headers={'User-Agent': USER_AGENT,
                                                  'Accept': 'text/plain' if robots else 'text/html'}) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        target = source.url(response.headers.get('location', ''), url)
                        if not target or not response.headers.get('location'):
                            raise WebUnavailable('Redirección no permitida')
                    else:
                        target = None
                        if robots and response.status_code == 404:
                            return ''
                        if response.status_code in (403, 429, 503):
                            # No insistir ni eludir bloqueos. No afecta a otros proveedores.
                            pause = 60.0
                            retry = response.headers.get('retry-after', '')
                            try:
                                advertised = float(retry)
                                if math.isfinite(advertised):
                                    pause = max(pause, advertised)
                            except ValueError:
                                try:
                                    advertised = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                                    pause = max(pause, advertised)
                                except (TypeError, ValueError, OverflowError):
                                    pass
                            _backoff[host] = monotonic() + pause
                        response.raise_for_status()
                        content_type = response.headers.get('content-type', '').lower()
                        if not robots and not any(t in content_type for t in ('text/html', 'application/xhtml+xml')):
                            raise WebUnavailable('El servidor no entregó HTML')
                        chunks, size = [], 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > (128 * 1024 if robots else MAX_BYTES):
                                raise WebUnavailable('Página demasiado grande')
                            chunks.append(chunk)
                        text = b''.join(chunks).decode(response.encoding or 'utf-8', errors='replace')
                        if robots and '<html' in text.lower():
                            raise WebUnavailable('robots.txt inválido')
                        return text
        except httpx.HTTPError as exc:
            raise WebUnavailable(f'{source.name}: acceso no disponible') from exc
    # Cada destino de redirección se vuelve a comprobar ANTES de solicitarlo.
    if not robots:
        policy = await robots_policy(source)
        if not policy.allows(target):
            raise WebUnavailable('Redirección restringida por robots.txt')
    return await _read(source, target, robots=robots, delay=delay, redirects=redirects + 1)


@TTLCache(ttl_seconds=300, maxsize=16)
async def robots_policy(source):
    try:
        policy = parse_robots(await _read(source, f'https://{source.host}/robots.txt', robots=True))
        _host_delay[source.host] = policy.delay
        return policy
    except WebUnavailable:
        # Si no se puede verificar la política, no rastrear el sitio.
        return RobotsPolicy(blocked=True)


@TTLCache(ttl_seconds=900, maxsize=64)
async def fetch_html(source, url):
    policy = await robots_policy(source)
    if not policy.allows(url):
        raise WebUnavailable('Acceso restringido por robots.txt')
    return await _read(source, url, delay=policy.delay)


def clear_web_state():
    """Limpieza al apagar y aislamiento entre pruebas/event loops."""
    robots_policy.cache_clear()
    fetch_html.cache_clear()
    _locks.clear()
    _last_request.clear()
    _backoff.clear()
    _host_delay.clear()
