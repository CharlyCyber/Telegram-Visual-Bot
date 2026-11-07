"""Comandos, autorización y conversaciones de Telegram."""
import logging
import httpx
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from .config import CHAT_ID, SELECCIONANDO
from .spam import is_spam_message
from .providers import (search_catalog, search_tvmaze, search_omdb, search_danfra,
                        search_lamparaturca, publish_tmdb_item, ProviderError)

logger = logging.getLogger(__name__)


async def is_user_in_group(context: ContextTypes.DEFAULT_TYPE,
                           user_id: int) -> bool:
    """Verifica si un usuario es miembro del grupo especificado"""
    try:
        chat_member = await context.bot.get_chat_member(CHAT_ID, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        # Nunca permitir acceso si no se pudo verificar la membresía.
        raise RuntimeError("No se pudo verificar la membresía") from e


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Comando /start recibido de usuario {update.message.from_user.id}")
    await update.message.reply_text(
        'Envíame el nombre de la película o serie (ejemplo: Inception)')
    context.user_data.clear()
    return ConversationHandler.END


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Nueva búsqueda de usuario %s", update.message.from_user.id)
    # FILTRO 1: Verificar si es spam
    if is_spam_message(update.message.text):
        logger.info(
            f"Mensaje de spam ignorado de usuario {update.message.from_user.id}"
        )
        return  # Ignorar silenciosamente

    # FILTRO 2: Verificar si el usuario es miembro del grupo
    if not await is_user_in_group(context, update.message.from_user.id):
        logger.info(
            f"Usuario no autorizado {update.message.from_user.id} intentó usar el bot"
        )
        return  # Ignorar silenciosamente

    text = update.message.text.strip()

    # Log de uso legítimo
    logger.info(
        f"Procesando búsqueda de usuario {update.message.from_user.id}"
    )

    # Intentar separar nombre y año
    try:
        name, year = text.rsplit(' ', 1)
        year = year.strip()
        if not year.isdigit():
            name = text
            year = None
    except ValueError:
        name = text
        year = None

    primary_error = None
    try:
        combined = await search_catalog(name, year)
    except (httpx.HTTPError, ValueError, ProviderError) as exc:
        primary_error = exc
        combined = []

    if not combined:
        failures = [primary_error] if primary_error else []
        poster_url, caption = None, None
        for search in (search_tvmaze, search_omdb, search_danfra, search_lamparaturca):
            try:
                poster_url, caption = await search(name)
            except ProviderError as exc:
                failures.append(exc)
                continue
            if caption:
                break
        if not caption and failures:
            raise ProviderError("No se pudo completar la búsqueda en los proveedores") from failures[-1]
        if not caption:
            await update.message.reply_text(
                'No se encontró el material en ninguna de nuestras fuentes. Intenta con otro nombre o año.')
            return
        if poster_url:
            await context.bot.send_photo(chat_id=CHAT_ID,
                                         photo=poster_url,
                                         caption=caption,
                                         parse_mode='HTML')
        else:
            await context.bot.send_message(chat_id=CHAT_ID,
                                           text=caption,
                                           parse_mode='HTML')
        return

    # Si hay más de una coincidencia, mostrar opciones
    if len(combined) > 1:
        context.user_data['options'] = combined
        msg = 'Se encontraron varias coincidencias. Responde con el número de la opción que deseas publicar:\n\n'
        for idx, item in enumerate(combined, 1):
            if item['__type'] == 'movie':
                title = item.get('title', 'Sin título')
                date = item.get('release_date', '')
                tipo = '🎬 Película'
            else:
                title = item.get('name', 'Sin título')
                date = item.get('first_air_date', '')
                tipo = '📺 Serie'
            msg += f"{idx}. {title} ({date[:4]}) {tipo}\n"
        await update.message.reply_text(msg)
        logger.info(f"Cambiando a estado SELECCIONANDO para usuario {update.message.from_user.id}")
        return SELECCIONANDO

    # Si solo hay una coincidencia, publicar directamente
    item = combined[0]
    is_movie = item.get('__type') == 'movie'
    year = (item.get('release_date') or item.get('first_air_date') or '')[:4]
    await publish_tmdb_item(update, context, item, is_movie, year)


async def select_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Selección recibida de usuario %s", update.message.from_user.id)
    # FILTRO: Verificar si el usuario es miembro del grupo
    if not await is_user_in_group(context, update.message.from_user.id):
        logger.info(
            f"Usuario no autorizado {update.message.from_user.id} intentó seleccionar opción"
        )
        return ConversationHandler.END

    try:
        idx = int(update.message.text.strip()) - 1
    except ValueError:
        await update.message.reply_text('Por favor, responde con el número de la opción.')
        return SELECCIONANDO
    options = context.user_data.get('options', [])
    if idx < 0 or idx >= len(options):
        await update.message.reply_text('Opción inválida. Intenta de nuevo.')
        return SELECCIONANDO
    item = options[idx]
    is_movie = item.get('__type') == 'movie'
    year = (item.get('release_date') or item.get('first_air_date') or '')[:4]
    await publish_tmdb_item(update, context, item, is_movie, year)
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la operación actual."""
    await update.message.reply_text(
        'Operación cancelada. Puedes empezar de nuevo cuando quieras.')
    context.user_data.clear()
    return ConversationHandler.END
