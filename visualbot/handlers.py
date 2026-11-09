"""Comandos, autorización y conversaciones de Telegram."""
import logging
import re
import httpx
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from .config import CHAT_ID, SELECCIONANDO, SELECCIONANDO_TEMPORADA
from .spam import is_spam_message
from .result_labels import send_options, one_line
from .formatting import utf16_length
from .web_catalogs import search_official_web, publish_web_item
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

    context.user_data.clear()
    text = update.message.text.strip()

    # Log de uso legítimo
    logger.info(
        f"Procesando búsqueda de usuario {update.message.from_user.id}"
    )

    # Intentar separar nombre y año
    try:
        name, year = text.rsplit(' ', 1)
        year = year.strip()
        if not re.fullmatch(r'(?:19|20)\d{2}', year):
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
        if not caption:
            web_options = await search_official_web(name, year)
            if len(web_options) == 1:
                await publish_web_item(context, web_options[0])
                return ConversationHandler.END
            if web_options:
                context.user_data['options'] = web_options
                await send_options(update.message, web_options,
                                   'Encontré estas fichas oficiales. Responde con el número de la opción:')
                return SELECCIONANDO
        if not caption and failures:
            raise ProviderError("No se pudo completar la búsqueda en los proveedores") from failures[-1]
        if not caption:
            await update.message.reply_text(
                'No se encontró el material en ninguna de nuestras fuentes. Intenta con otro nombre o año.')
            return
        if year:
            await update.message.reply_text('No se pudo verificar que esta ficha corresponda al año solicitado.')
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
        context.user_data['requested_year'] = year
        await send_options(update.message, combined,
                           'Se encontraron varias coincidencias. Responde con el número de la opción que deseas publicar:')
        logger.info(f"Cambiando a estado SELECCIONANDO para usuario {update.message.from_user.id}")
        return SELECCIONANDO

    # Si solo hay una coincidencia, publicar directamente
    item = combined[0]
    return await publish_selection(update, context, item, year)


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
    if item.get('__type') == 'web':
        await publish_web_item(context, item)
        context.user_data.clear()
        return ConversationHandler.END
    requested_year = context.user_data.get('requested_year')
    return await publish_selection(update, context, item, requested_year)


async def publish_selection(update, context, item, requested_year=None):
    is_movie = item.get('__type') == 'movie'
    if is_movie:
        await publish_tmdb_item(update, context, item, True,
                                (item.get('release_date') or '')[:4])
        context.user_data.clear()
        return ConversationHandler.END

    result = await publish_tmdb_item(update, context, item, False,
                                     requested_year=requested_year)
    seasons = result['seasons']
    selected = result['selected']
    official = []
    if selected is None:
        year_note = f' de {requested_year}' if requested_year else ''
        await update.message.reply_text(
            f'No hay una temporada estrenada{year_note} disponible en TMDb. '
            'Se mostró la ficha general, no una ficha de temporada.')
        # Las fuentes disponibles aportan fichas generales, no necesariamente
        # temporadas; nunca afirmar que una ficha general es una temporada.
        title = item.get('name') or item.get('title') or ''
        official = await search_official_web(title, requested_year)
    if selected is not None and not requested_year:
        await update.message.reply_text('Se mostró la temporada estrenada más reciente disponible en TMDb.')
    if (seasons and (len(seasons) > 1 or selected is None)) or official:
        context.user_data.clear()
        context.user_data['season_item'] = item
        context.user_data['seasons'] = seasons
        context.user_data['season_official'] = official
        await send_season_options(update.message, seasons, selected, official)
        return SELECCIONANDO_TEMPORADA
    context.user_data.clear()
    return ConversationHandler.END


async def send_season_options(message, seasons, selected, official=()):
    text = 'Elige una opción o responde 0 para terminar:\n\n'
    for index, season in enumerate(seasons, 1):
        name = one_line(season.get('name'), 100)
        number = season['season_number']
        line = f"{index}. Temporada {number} ({season['air_date'][:4]})"
        if name:
            line += f' · {name}'
        if number == selected:
            line += ' · mostrada'
        line += '\n'
        if utf16_length(text + line) > 4096:
            await message.reply_text(text.rstrip())
            text = ''
        text += line
    for index, entry in enumerate(official, len(seasons) + 1):
        line = f"{index}. Ficha oficial general: {one_line(entry.get('title'), 150)} · {one_line(entry.get('source'), 60)}\n"
        if utf16_length(text + line) > 4096:
            await message.reply_text(text.rstrip())
            text = ''
        text += line
    if text.strip():
        await message.reply_text(text.rstrip())


async def select_season(update, context):
    if not await is_user_in_group(context, update.message.from_user.id):
        context.user_data.clear()
        return ConversationHandler.END
    try:
        index = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text('Responde con el número de una opción o 0 para terminar.')
        return SELECCIONANDO_TEMPORADA
    if index == 0:
        context.user_data.clear()
        await update.message.reply_text('Selección de temporadas terminada.')
        return ConversationHandler.END
    seasons = context.user_data.get('seasons', [])
    item = context.user_data.get('season_item')
    official = context.user_data.get('season_official', [])
    if not item or index < 1 or index > len(seasons) + len(official):
        await update.message.reply_text('Opción inválida. Intenta de nuevo o responde 0 para terminar.')
        return SELECCIONANDO_TEMPORADA
    if index > len(seasons):
        await publish_web_item(context, official[index - len(seasons) - 1])
        await update.message.reply_text('Puedes elegir otra opción de la lista o responder 0 para terminar.')
        return SELECCIONANDO_TEMPORADA
    number = seasons[index - 1]['season_number']
    result = await publish_tmdb_item(update, context, item, False, season_number=number)
    if result['selected'] != number:
        await update.message.reply_text('La temporada ya no está disponible en TMDb; se mostró la ficha general.')
    await update.message.reply_text('Puedes elegir otra opción de la lista o responder 0 para terminar.')
    return SELECCIONANDO_TEMPORADA


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la operación actual."""
    await update.message.reply_text(
        'Operación cancelada. Puedes empezar de nuevo cuando quieras.')
    context.user_data.clear()
    return ConversationHandler.END
