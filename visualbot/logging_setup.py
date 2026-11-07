"""Evita que URLs y excepciones expongan credenciales en los logs."""
import logging
import os
import re


class RedactingFormatter(logging.Formatter):
    def format(self, record):
        text = super().format(record)
        for name in ('BOT_TOKEN', 'TMDB_API_KEY', 'OMDB_API_KEY'):
            secret = os.getenv(name)
            if secret:
                text = text.replace(secret, '[REDACTED]')
        text = re.sub(r'(?i)(/bot)[^/\s?]+', r'\1[REDACTED]', text)
        return re.sub(
            r'''(?i)((?:api_key|apikey|bot_token|token)=)[^&\s'"<>]+''',
            r'\1[REDACTED]', text,
        )


def configure_logging():
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    root.setLevel(logging.INFO)
    for handler in root.handlers:
        handler.setFormatter(RedactingFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    # httpx registra URLs de peticiones a Telegram que contienen el token.
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
