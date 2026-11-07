"""Pool HTTP compartido y cierre vinculado al ciclo de vida del bot."""
from contextlib import asynccontextmanager
import httpx


class APIClient(httpx.AsyncClient):
    async def request(self, *args, **kwargs):
        response = await super().request(*args, **kwargs)
        response.raise_for_status()
        return response


_client = None


def get_client():
    global _client
    if _client is None or _client.is_closed:
        _client = APIClient(
            timeout=httpx.Timeout(10.0),
            transport=httpx.AsyncHTTPTransport(retries=2),
            follow_redirects=True,
        )
    return _client


@asynccontextmanager
async def shared_client():
    # Salir del bloque NO cierra el pool: se reutiliza en la próxima consulta.
    yield get_client()


async def initialize_http(application):
    get_client()


async def shutdown_http(application):
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
