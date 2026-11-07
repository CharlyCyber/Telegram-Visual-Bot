"""Endpoint de disponibilidad del proceso de Telegram."""
import http.server
import logging
import os
import threading

logger = logging.getLogger(__name__)

class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            app = self.server.application
            ready = app.running and app.updater is not None and app.updater.running
            self.send_response(200 if ready else 503)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'OK' if ready else b'Bot not ready')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logger.debug(f"Health server: {format % args}")


def _start_health_server(app):
    # Vincular el puerto en el hilo principal: un fallo debe detener el proceso
    # para que el supervisor lo reinicie, no dejar un bot sin monitoreo.
    port = int(os.environ.get('PORT', 10000))
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    server.daemon_threads = True
    server.application = app
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health server escuchando en el puerto %s", server.server_port)
    return server, thread
