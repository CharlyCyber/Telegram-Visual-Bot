"""Endpoint de disponibilidad y auto-ping 24/7 del proceso de Telegram."""
from datetime import datetime, timezone
import http.server
import json
import logging
import os
import threading

import httpx

from . import config

logger = logging.getLogger(__name__)


def resolve_http_port() -> int:
    """Resuelve el puerto HTTP: 7860 en Hugging Face Spaces (SPACE_ID), 10000 por defecto."""
    default_port = "7860" if os.getenv("SPACE_ID") else "10000"
    raw = (os.environ.get("PORT") or "").strip()
    try:
        return int(raw) if raw else int(default_port)
    except ValueError:
        return int(default_port)


class HealthHandler(http.server.BaseHTTPRequestHandler):
    def _is_ready(self) -> bool:
        app = self.server.application
        return bool(app.running and app.updater is not None and app.updater.running)

    def _send(self, status: int, content_type: str, body: bytes, send_body: bool) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if send_body and body:
            self.wfile.write(body)

    def _handle_request(self, send_body: bool) -> None:
        path = self.path.split('?', 1)[0]
        if path == '/health':
            ready = self._is_ready()
            self._send(
                200 if ready else 503,
                'text/plain; charset=utf-8',
                b'OK' if ready else b'Bot not ready',
                send_body,
            )
        elif path == '/':
            payload = json.dumps({
                'status': 'ok',
                'service': 'telegram-visual-bot',
                'bot_polling_active': self._is_ready(),
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }).encode('utf-8')
            self._send(200, 'application/json; charset=utf-8', payload, send_body)
        else:
            self._send(404, 'text/plain; charset=utf-8', b'', False)

    def do_GET(self):
        self._handle_request(send_body=True)

    def do_HEAD(self):
        self._handle_request(send_body=False)

    def log_message(self, format, *args):
        logger.debug(f"Health server: {format % args}")


def _start_health_server(app):
    # Vincular el puerto en el hilo principal: un fallo debe detener el proceso
    # para que el supervisor lo reinicie, no dejar un bot sin monitoreo.
    port = resolve_http_port()
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    server.daemon_threads = True
    server.application = app
    thread = threading.Thread(target=server.serve_forever, name="HealthServer", daemon=True)
    thread.start()
    logger.info("Health server escuchando en 0.0.0.0:%s", server.server_port)
    return server, thread


def self_ping_once(port: int, public_url: str | None = None) -> bool:
    """Realiza un ping HTTP a /health (usa PUBLIC_URL/RENDER_EXTERNAL_URL/SPACE_HOST si existe)."""
    raw_url = (config.PUBLIC_URL if public_url is None else public_url).strip()
    base = raw_url if raw_url.startswith(("http://", "https://")) else f"http://127.0.0.1:{port}"
    url = f"{base.rstrip('/')}/health"
    try:
        resp = httpx.get(url, timeout=12.0, follow_redirects=True)
        if resp.status_code == 200:
            logger.debug("Health ping OK (%s)", url)
            return True
        logger.warning("Health ping respondió con status %s (%s)", resp.status_code, url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Health ping falló (%s): %s", url, exc)
    return False


def _start_self_ping(port: int, interval: int | None = None):
    """Inicia el hilo periódico de auto-ping para mantener vivo el servicio."""
    effective_interval = config.SELF_PING_INTERVAL if interval is None else interval
    if effective_interval <= 0:
        return None, None

    stop_event = threading.Event()
    initial_delay = min(30, effective_interval)

    def _loop() -> None:
        if stop_event.wait(initial_delay):
            return
        while not stop_event.is_set():
            self_ping_once(port)
            if stop_event.wait(effective_interval):
                break

    thread = threading.Thread(target=_loop, name="SelfPing", daemon=True)
    thread.start()
    logger.info("Auto-ping 24/7 activo cada %ds", effective_interval)
    return stop_event, thread
