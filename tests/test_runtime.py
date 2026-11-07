"""Pruebas de disponibilidad sin credenciales ni servicios externos."""
import http.client
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from supervisor.datatypes import RestartUnconditionally
from supervisor.options import ServerOptions

import bot


@pytest.fixture
def health_server(monkeypatch):
    monkeypatch.setenv('PORT', '0')
    app = SimpleNamespace(running=False, updater=SimpleNamespace(running=False))
    server, thread = bot._start_health_server(app)
    yield server, app
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    assert not thread.is_alive()


@pytest.mark.parametrize('running,polling,status', [
    (False, False, 503), (True, False, 503), (False, True, 503),
    (True, True, 200),
])
def test_health_reflects_bot_state(health_server, running, polling, status):
    server, app = health_server
    app.running = running
    app.updater.running = polling
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
    try:
        conn.request('GET', '/health')
        response = conn.getresponse()
        assert response.status == status
        assert response.read() == (b'OK' if status == 200 else b'Bot not ready')
    finally:
        conn.close()


def test_health_unknown_path(health_server):
    server, _ = health_server
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
    try:
        conn.request('GET', '/')
        response = conn.getresponse()
        assert response.status == 404
        response.read()
    finally:
        conn.close()


def test_missing_credentials_exit_with_error(monkeypatch):
    monkeypatch.setattr(bot, 'BOT_TOKEN', None)
    monkeypatch.setattr(bot, 'TMDB_API_KEY', None)
    with pytest.raises(SystemExit) as exc:
        bot.main()
    assert exc.value.code == 1


@pytest.mark.parametrize('polling_error', [False, True])
def test_polling_retries_and_cleans_up(monkeypatch, polling_error):
    monkeypatch.setattr(bot, 'BOT_TOKEN', 'test-token')
    monkeypatch.setattr(bot, 'TMDB_API_KEY', 'test-key')
    app = Mock()
    builder = Mock()
    builder.token.return_value.build.return_value = app
    monkeypatch.setattr(bot, 'ApplicationBuilder', lambda: builder)
    server, thread = Mock(), Mock()
    monkeypatch.setattr(bot, '_start_health_server', lambda _: (server, thread))
    if polling_error:
        app.run_polling.side_effect = RuntimeError('polling failed')
        with pytest.raises(RuntimeError, match='polling failed'):
            bot.main()
    else:
        bot.main()
    app.run_polling.assert_called_once_with(bootstrap_retries=-1)
    server.shutdown.assert_called_once_with()
    server.server_close.assert_called_once_with()
    thread.join.assert_called_once_with(timeout=5)


def test_port_binding_failure_is_not_silent(monkeypatch):
    monkeypatch.setenv('PORT', '0')
    def fail(*args):
        raise OSError('port unavailable')
    monkeypatch.setattr(bot.http.server, 'ThreadingHTTPServer', fail)
    with pytest.raises(OSError, match='port unavailable'):
        bot._start_health_server(Mock())


def test_supervisor_config_is_valid_and_always_restarts(tmp_path):
    root = Path(__file__).resolve().parents[1]
    # Usar rutas temporales para que el parser pueda validar los directorios.
    config = (root / 'supervisord.conf').read_text().replace('%(here)s', str(tmp_path))
    (tmp_path / 'logs').mkdir()
    (tmp_path / 'run').mkdir()
    path = tmp_path / 'supervisord.conf'
    path.write_text(config)
    options = ServerOptions()
    options.realize(['-c', str(path)])
    process = options.process_group_configs[0].process_configs[0]
    assert process.autostart is True
    assert process.autorestart is RestartUnconditionally
    assert process.startsecs == 0
    assert process.stopasgroup is True
    assert process.killasgroup is True
    # Verificar también la factoría RPC: antes tenía un nombre truncado.
    factory = options.rpcinterface_factories[0][1]
    assert callable(factory)
