# 🤖 Bot de Telegram Anti-Spam para Películas y Series

Bot inteligente de Telegram que busca y publica información de películas y series con **sistema anti-spam avanzado**.

## ✨ Características Principales

### 🛡️ **SISTEMA ANTI-SPAM AVANZADO**
- **Detección inteligente** de mensajes de spam como "FREE ETH ALERT", "crypto airdrops", etc.
- **Filtros por palabras clave** de scams comunes
- **Verificación de URLs sospechosas** 
- **Análisis de patrones** de spam (emojis excesivos, mayúsculas, etc.)

### 🔒 **Control de Acceso**
- **Solo miembros del grupo** pueden usar el bot
- **Verificación automática** de membresía
- **Logging de intentos no autorizados**

### 🎬 **Búsqueda de Contenido**
- Integración con **TMDb API** (películas y series)
- Integración con **OMDb API** (información detallada)
- Integración con **TVmaze API** (backup)
- **Búsqueda inteligente** con múltiples opciones
- **Formato visual atractivo** con emojis y detalles completos

## 🚀 Instalación y Deployment

### Variables de Entorno Requeridas
```env
BOT_TOKEN=tu_bot_token_aqui
TMDB_API_KEY=tu_tmdb_api_key_aqui
OMDB_API_KEY=tu_omdb_api_key_aqui
```

### Deploy en Render
1. Conecta tu repositorio de GitHub
2. Configura las variables de entorno
3. El `Procfile` iniciará automáticamente el bot con supervisor

### Ejecución Local
```bash
pip install -r requirements.txt
./start.sh
```

## 🛡️ Cómo Funciona el Anti-Spam

El bot **ignora silenciosamente** mensajes que contengan:

### 🚫 Palabras Clave de Spam
- Crypto/Bitcoin relacionados: `free eth`, `airdrop`, `crypto`, `wallet`
- Esquemas de dinero: `make money`, `earn money`, `easy money`
- Llamadas urgentes: `limited time`, `act now`, `hurry`
- URLs sospechosas: `www.`, `click here`, `telegram.me`

### 🚫 Patrones de Spam
- Múltiples emojis de alerta (🚨, 💰, 🔥)
- Exceso de mayúsculas (>30% del texto)
- URLs de dominios conocidos de scam

### ✅ Mensajes Legítimos
- Nombres de películas: `Matrix`, `Avengers`, `El padrino`
- Series: `Breaking Bad`, `Game of Thrones`
- Búsquedas con año: `Inception 2010`

## 📊 Monitoreo

### Logs Disponibles
- `/var/log/supervisor/telegram_bot.log` - Actividad del bot
- `/var/log/supervisor/supervisord.log` - Estado del supervisor

### Comandos de Control
```bash
# Ver estado
supervisorctl -c supervisord.conf status

# Reiniciar bot
supervisorctl -c supervisord.conf restart telegram_bot

# Ver logs en tiempo real
tail -f /var/log/supervisor/telegram_bot.log
```

## 🔧 Testing

### Probar Sistema Anti-Spam
```bash
python test_spam.py
```

### Mensajes de Prueba
- ❌ `"🚨 FREE ETH ALERT! 🚨"` → Detectado como spam
- ✅ `"Matrix"` → Búsqueda legítima

## 👨‍💻 Desarrollado por ANDY

Bot personalizado con firma:
> 💻ANDY (el+lin2)🛠️🪛 📍Ave 3️⃣7️⃣ - #️⃣4️⃣2️⃣1️⃣1️⃣ ➗4️⃣2️⃣ y 4️⃣8️⃣ cerca del CVD 🏟️ 📌MAYABEQUE SAN JOSÉ

## 🆘 Solución de Problemas

### Bot no responde
```bash
supervisorctl -c supervisord.conf restart telegram_bot
```

### Múltiples instancias conflictivas
```bash
pkill -f "python.*bot.py"
supervisorctl -c supervisord.conf restart telegram_bot
```

### Ver errores recientes
```bash
tail -50 /var/log/supervisor/telegram_bot.log
```
