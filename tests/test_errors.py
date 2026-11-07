import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from telegram.error import NetworkError
from visualbot import errors
from visualbot.logging_setup import RedactingFormatter


@pytest.fixture
def error_context(monkeypatch):
    monkeypatch.setattr(errors, 'ADMIN_CHAT_ID', 42)
    context = SimpleNamespace(error=RuntimeError('failure'),
                              application=SimpleNamespace(bot_data={}),
                              bot=SimpleNamespace(send_message=AsyncMock()))
    update = SimpleNamespace(effective_message=SimpleNamespace(reply_text=AsyncMock()))
    return update, context


async def test_user_receives_helpful_message_and_admin_gets_repeated_failure_alert(error_context):
    update, context = error_context
    for _ in range(3):
        await errors.handle_error(update, context)
    assert update.effective_message.reply_text.await_count == 3
    assert update.effective_message.reply_text.call_args.args == (errors.ERROR_MESSAGE,)
    context.bot.send_message.assert_awaited_once()
    assert context.bot.send_message.call_args.kwargs['chat_id'] == 42
    for _ in range(10):
        await errors.handle_error(update, context)
    assert context.bot.send_message.await_count == 1


async def test_admin_alerts_optional(error_context, monkeypatch):
    monkeypatch.setattr(errors, 'ADMIN_CHAT_ID', None)
    update, context = error_context
    for _ in range(3):
        await errors.handle_error(update, context)
    context.bot.send_message.assert_not_awaited()


async def test_notification_failures_do_not_recurse(error_context):
    update, context = error_context
    context.bot.send_message.side_effect = NetworkError('offline')
    update.effective_message.reply_text.side_effect = NetworkError('offline')
    for _ in range(3):
        await errors.handle_error(update, context)
    assert context.bot.send_message.await_count == 1


async def test_polling_errors_without_update_are_supported(error_context):
    _, context = error_context
    await errors.handle_error(None, context)


def test_monitor_window_and_cooldown():
    now = [0]
    monitor = errors.ErrorMonitor(clock=lambda: now[0])
    assert not monitor.should_alert()
    now[0] = 301
    assert not monitor.should_alert()  # el evento antiguo caducó
    assert not monitor.should_alert()
    assert monitor.should_alert()
    assert not monitor.should_alert()
    now[0] = 602
    assert not monitor.should_alert()
    assert not monitor.should_alert()
    assert monitor.should_alert()
    assert len(monitor.events) == 0


def test_formatter_redacts_messages_and_tracebacks(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', '123:private-token')
    monkeypatch.setenv('TMDB_API_KEY', 'private-tmdb')
    monkeypatch.setenv('OMDB_API_KEY', 'private-omdb')
    try:
        raise RuntimeError('https://api.test/?apikey=private-omdb&api_key=another-secret')
    except RuntimeError as exc:
        record = logging.LogRecord('test', logging.ERROR, '', 1,
            'https://api.telegram.org/bot123:private-token/getUpdates private-tmdb', (),
            (type(exc), exc, exc.__traceback__))
    text = RedactingFormatter('%(message)s').format(record)
    for secret in ('123:private-token', 'private-tmdb', 'private-omdb', 'another-secret'):
        assert secret not in text
    assert '[REDACTED]' in text
    assert 'RuntimeError' in text
