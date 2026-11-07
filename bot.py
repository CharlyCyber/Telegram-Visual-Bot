"""Punto de entrada. La lógica está organizada en el paquete visualbot."""
import logging

from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          filters, ConversationHandler)
from visualbot.config import BOT_TOKEN, TMDB_API_KEY, SELECCIONANDO
from visualbot.logging_setup import configure_logging
from visualbot.network import initialize_http, shutdown_http
from visualbot.errors import handle_error
from visualbot.handlers import start, cancel, handle_message, select_option
from visualbot.health import _start_health_server
# Compatibilidad con los imports públicos anteriores.
from visualbot.spam import is_spam_message
from visualbot.formatting import (esc, get_genre_emojis, get_keyword_emojis,
                                  get_synopsis_with_emojis, get_dynamic_closing)
from visualbot.providers import (search_tmdb_and_show_options, search_tvmaze,
                                 search_omdb, publish_tmdb_item)

configure_logging()
logger = logging.getLogger(__name__)


def main() -> None:
    """Inicia el bot."""
    if not all([BOT_TOKEN, TMDB_API_KEY]):
        logger.critical(
            "Faltan variables de entorno críticas (BOT_TOKEN, TMDB_API_KEY). El bot no puede iniciar."
        )
        raise SystemExit(1)

    app = (ApplicationBuilder().token(BOT_TOKEN)
           .post_init(initialize_http).post_shutdown(shutdown_http).build())
    app.add_error_handler(handle_error)

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        ],
        states={
            SELECCIONANDO:
            [MessageHandler(filters.Regex(r'^\d+$'), select_option)]
        },
        fallbacks=[
            CommandHandler('start', start),
            CommandHandler('cancel', cancel)
        ])

    app.add_handler(conv_handler)

    server, health_thread = _start_health_server(app)
    try:
        logger.info("Iniciando bot con reconexión automática...")
        # Reintentar también durante el arranque si Telegram no está disponible.
        app.run_polling(bootstrap_retries=-1)
    finally:
        server.shutdown()
        server.server_close()
        health_thread.join(timeout=5)


if __name__ == '__main__':
    main()
