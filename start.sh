#!/bin/bash

# Script de inicio para Render
echo "🚀 Iniciando Bot de Telegram Anti-Spam..."

# Instalar dependencias
pip install -r requirements.txt

# Crear directorio para logs
mkdir -p /var/log/supervisor

echo "✅ Dependencias instaladas"

# Iniciar supervisor con el bot
echo "🤖 Iniciando bot con supervisor..."
supervisord -c supervisord.conf

echo "🎯 Bot iniciado correctamente"

# Mantener el proceso vivo
tail -f /var/log/supervisor/telegram_bot.log