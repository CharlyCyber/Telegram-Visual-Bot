"""Pruebas de disponibilidad sin credenciales ni servicios externos."""
import http.client
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from supervisor.datatypes import RestartUnconditionally
from supervisor.options import ServerOptions

import bot
from visualbot import health


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
        conn.request('GET', '/health?check=1')
        response = conn.getresponse()
        assert response.status == status
        assert response.read() == (b'OK' if status == 200 else b'Bot not ready')

        conn.request('HEAD', '/health')
        head_resp = conn.getresponse()
        assert head_resp.status == status
        assert head_resp.read() == b''
    finally:
        conn.close()


def test_root_returns_json_status(health_server):
    server, app = health_server
    app.running = True
    app.updater.running = True
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
    try:
        conn.request('GET', '/')
        response = conn.getresponse()
        assert response.status == 200
        payload = json.loads(response.read().decode('utf-8'))
        assert payload['status'] == 'ok'
        assert payload['service'] == 'telegram-visual-bot'
        assert payload['bot_polling_active'] is True

        conn.request('HEAD', '/')
        head_resp = conn.getresponse()
        assert head_resp.status == 200
        assert head_resp.read() == b''
    finally:
        conn.close()


def test_health_unknown_path(health_server):
    server, _ = health_server
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=2)
    try:
        conn.request('GET', '/unknown')
        response = conn.getresponse()
        assert response.status == 404
        response.read()
    finally:
        conn.close()


def test_resolve_http_port_defaults(monkeypatch):
    monkeypatch.delenv('PORT', raising=False)
    monkeypatch.delenv('SPACE_ID', raising=False)
    assert health.resolve_http_port() == 10000

    monkeypatch.setenv('SPACE_ID', 'user/telegram-visual-bot')
    assert health.resolve_http_port() == 7860

    monkeypatch.setenv('PORT', '9090')
    assert health.resolve_http_port() == 9090

    monkeypatch.setenv('PORT', 'invalid')
    assert health.resolve_http_port() == 7860


def test_self_ping_once_uses_public_url_or_localhost(monkeypatch):
    calls = []

    def fake_get(url, timeout=12.0, follow_redirects=True):
        calls.append((url, timeout, follow_redirects))
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(health.httpx, 'get', fake_get)
    assert health.self_ping_once(10000, public_url='https://bot.example.com/') is True
    assert health.self_ping_once(7860, public_url='') is True
    assert calls[0][0] == 'https://bot.example.com/health'
    assert calls[1][0] == 'http://127.0.0.1:7860/health'


def test_self_ping_once_handles_failures(monkeypatch):
    monkeypatch.setattr(health.httpx, 'get', lambda *a, **kw: SimpleNamespace(status_code=503))
    assert health.self_ping_once(10000, public_url='') is False

    def boom(*args, **kwargs):
        raise httpx.ConnectError('network down')

    monkeypatch.setattr(health.httpx, 'get', boom)
    assert health.self_ping_once(10000, public_url='') is False


def test_start_self_ping_disabled_and_stoppable():
    assert health._start_self_ping(10000, interval=0) == (None, None)
    stop_event, thread = health._start_self_ping(10000, interval=300)
    assert stop_event is not None and thread is not None and thread.is_alive()
    stop_event.set()
    thread.join(timeout=2)
    assert not thread.is_alive()


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
    monkeypatch.setattr(bot, 'CHAT_ID', -1001234567890)
    app = Mock()
    builder = Mock()
    builder.token.return_value.post_init.return_value.post_shutdown.return_value.build.return_value = app
    monkeypatch.setattr(bot, 'ApplicationBuilder', lambda: builder)
    server, thread = Mock(server_port=10000), Mock()
    monkeypatch.setattr(bot, '_start_health_server', lambda _: (server, thread))
    ping_stop, ping_thread = Mock(), Mock()
    monkeypatch.setattr(bot, '_start_self_ping', lambda port: (ping_stop, ping_thread))
    if polling_error:
        app.run_polling.side_effect = RuntimeError('polling failed')
        with pytest.raises(RuntimeError, match='polling failed'):
            bot.main()
    else:
        bot.main()
    app.add_error_handler.assert_called_once_with(bot.handle_error)
    builder.token.return_value.post_init.assert_called_once_with(bot.initialize_http)
    builder.token.return_value.post_init.return_value.post_shutdown.assert_called_once_with(bot.shutdown_http)
    app.run_polling.assert_called_once_with(bootstrap_retries=-1)
    ping_stop.set.assert_called_once_with()
    ping_thread.join.assert_called_once_with(timeout=2)
    server.shutdown.assert_called_once_with()
    server.server_close.assert_called_once_with()
    thread.join.assert_called_once_with(timeout=5)


def test_port_binding_failure_is_not_silent(monkeypatch):
    monkeypatch.setenv('PORT', '0')
    def fail(*args):
        raise OSError('port unavailable')
    monkeypatch.setattr(health.http.server, 'ThreadingHTTPServer', fail)
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
