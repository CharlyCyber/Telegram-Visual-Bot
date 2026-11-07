"""Catálogos HTML oficiales. No son APIs ni una garantía de catálogo completo."""
from dataclasses import dataclass
import os
import re
from urllib.parse import urljoin, urlsplit, urlunsplit, unquote


@dataclass(frozen=True)
class WebSource:
    key: str
    name: str
    host: str
    catalogs: tuple[str, ...]
    title_path: str
    image_hosts: tuple[str, ...]

    def url(self, value, base=None):
        if not isinstance(value, str) or not value or len(value) > 2048:
            return None
        try:
            parsed = urlsplit(urljoin(base or f'https://{self.host}/', value))
            port = parsed.port
        except ValueError:
            return None
        if (parsed.scheme not in ('http', 'https') or parsed.hostname != self.host
                or parsed.username or parsed.password or port not in (None, 80, 443)
                or any(p in ('.', '..') for p in unquote(parsed.path).split('/'))):
            return None
        # Enlaces antiguos HTTP se actualizan a HTTPS; nunca se permite salir del dominio.
        return urlunsplit(('https', self.host, parsed.path or '/', '', ''))

    def is_title(self, url):
        safe = self.url(url)
        return bool(safe and re.fullmatch(self.title_path, urlsplit(safe).path))

    def image(self, value, base):
        if isinstance(value, list):
            value = value[0] if value else None
        if isinstance(value, dict):
            value = value.get('url') or value.get('contentUrl')
        if not isinstance(value, str) or not value:
            return None
        try:
            parsed = urlsplit(urljoin(base, value))
            port = parsed.port
        except ValueError:
            return None
        if (parsed.scheme not in ('http', 'https') or parsed.username or parsed.password
                or port not in (None, 80, 443) or not parsed.hostname):
            return None
        if not any(parsed.hostname == host or parsed.hostname.endswith('.' + host)
                   for host in (self.host, *self.image_hosts)):
            return None
        return urlunsplit(('https', parsed.netloc, parsed.path, parsed.query, ''))


SOURCES = (
    WebSource('telemundo', 'Telemundo', 'www.telemundo.com',
              ('/shows',), r'/shows/[^/]+/?', ('s-nbcnews.com', 'nbcuni.com')),
    WebSource('las_estrellas', 'Las Estrellas', 'www.lasestrellas.tv',
              ('/telenovelas',), r'/telenovelas/[^/]+/?', ('uvnimg.com',)),
    WebSource('caracol', 'Caracol TV', 'www.caracoltv.com',
              ('/programas',), r'/(?!programas/?$|busqueda/?$|noticias/?$)[^/]+/?',
              ('caracoltv.brightspotcdn.com', 'caracol-brightspot.s3.us-west-2.amazonaws.com')),
    WebSource('rtve', 'RTVE Play', 'www.rtve.es',
              ('/play/colecciones/telenovelas/229/', '/play/colecciones/play-archivo-novelas/275/',
               '/play/series/', '/play/documentales/', '/play/'),
              r'/play/videos/[^/]+/?', ('img.rtve.es',)),
    WebSource('globoplay', 'Globoplay', 'globoplay.globo.com',
              ('/categorias/novelas/', '/categorias/novelas-anos-2000/', '/categorias/novelas-anos-2020/',
               '/categorias/series/', '/categorias/filmes/'),
              r'/[^/]+/(?:t|vc)/[A-Za-z0-9]+/?', ('glbimg.com',)),
    WebSource('atresplayer', 'Atresplayer', 'www.atresplayer.com',
              ('/series/', '/programas/', '/'),
              r'/(?:(?:antena3|nova|lasexta|neox|flooxer)/)?(?:series|novelas|programas|peliculas|vertical)/[^/]+/?',
              ('imagenes.atresplayer.com', 'atresmedia.com')),
)


def enabled_sources():
    configured = os.getenv('WEB_SOURCES')
    if configured is None:
        return SOURCES
    keys = {key.strip().lower() for key in configured.split(',')}
    return tuple(source for source in SOURCES if source.key in keys)
