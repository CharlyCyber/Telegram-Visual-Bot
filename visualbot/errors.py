"""Errores centralizados y avisos opcionales al administrador."""
from collections import deque
import logging
from time import monotonic
from telegram.error import TelegramError

from .config import ADMIN_CHAT_ID

logger = logging.getLogger(__name__)
ERROR_MESSAGE = (
    'No pude completar la operación por un problema temporal. '
    'Intenta de nuevo; si estabas eligiendo una opción, puedes usar /cancel y volver a buscar.'
)


class ErrorMonitor:
    """Agrupa fallos, sin almacenar mensajes ni datos personales de usuarios."""
    def __init__(self, threshold=3, window=300, cooldown=300, clock=monotonic):
        self.threshold, self.window, self.cooldown = threshold, window, cooldown
        self.clock = clock
        self.events = deque(maxlen=threshold)
        self.last_alert = float('-inf')

    def should_alert(self):
        now = self.clock()
        while self.events and now - self.events[0] >= self.window:
            self.events.popleft()
        self.events.append(now)
        if len(self.events) >= self.threshold and now - self.last_alert >= self.cooldown:
            self.last_alert = now
            self.events.clear()
            return True
        return False


async def handle_error(update, context):
    error = context.error
    logger.error('Error no controlado (%s)', type(error).__name__,
                 exc_info=(type(error), error, error.__traceback__))
    monitor = context.application.bot_data.setdefault('_error_monitor', ErrorMonitor())
    alert = monitor.should_alert()
    if ADMIN_CHAT_ID is not None and alert:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text='⚠️ El bot registró varios fallos en los últimos 5 minutos. Revisa los logs del servicio.',
            )
        except TelegramError:
            # No invocar de nuevo el manejador: evitar bucles de notificaciones.
            logger.warning('No se pudo enviar la alerta al administrador')
    message = getattr(update, 'effective_message', None)
    if message is not None:
        try:
            await message.reply_text(ERROR_MESSAGE)
        except TelegramError:
            logger.warning('No se pudo informar al usuario del fallo')
