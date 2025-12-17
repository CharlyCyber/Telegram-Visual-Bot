#!/bin/bash

# Script de inicio para Render
echo "🚀 Iniciando Bot de Telegram Anti-Spam..."

# Instalar dependencias
pip install -r requirements.txt

# Crear directorios para logs (dentro del proyecto)
mkdir -p ./logs
mkdir -p ./run

echo "✅ Dependencias instaladas"

# Iniciar supervisor con el bot
echo "🤖 Iniciando bot con supervisor..."
supervisord -c supervisord.conf

echo "🎯 Bot iniciado correctamente"

# Mantener el proceso vivo mostrando logs
tail -f ./logs/telegram_bot.log
