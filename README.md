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
GROUP_CHAT_ID=-1001234567890
```

### Disponibilidad 24/7: evitar la suspensión

**El código no puede impedir que el proveedor suspenda una instancia gratuita.**
Para mantener el bot activo sin tráfico, usa un servicio de pago que no se
suspenda por inactividad o un VPS siempre encendido. Los auto-pings no son una
garantía de disponibilidad. Tampoco existe garantía absoluta frente a caídas
del proveedor, de la red o de Telegram.

### Deploy en Render (siempre activo)

El archivo `render.yaml` define un servicio web con **plan Starter (de pago)**,
una sola instancia y comprobación de salud en `/health`.

1. En Render, crea un **Blueprint** y conecta este repositorio y la rama que
   contenga estos cambios.
2. Revisa y acepta el costo del plan Starter antes de crear el servicio.
3. Introduce las variables de entorno en Render; no subas secretos al repositorio.
   `BOT_TOKEN` y `TMDB_API_KEY` son obligatorias para arrancar; configura también
   `OMDB_API_KEY` y el `GROUP_CHAT_ID` de tu grupo.
4. Despliega y comprueba los logs y `https://<tu-servicio>.onrender.com/health`.

**Si el servicio ya existe**, añadir el Blueprint al repositorio no modifica por
sí solo el servicio actual. Cambia su instancia a Starter o superior y configura:

- Build command: `pip install -r requirements.txt`
- Start command: `./start.sh`
- Health check path: `/health`
- Instancias: **1** (no actives escalado con el mismo token).

El arranque usa Supervisor para reiniciar el bot cuando termina, incluso si
falla inmediatamente. Telegram se reconecta también durante el arranque si hay
fallos transitorios. `/health` devuelve **200** cuando la aplicación y el polling
están en marcha, o **503** mientras no estén listos; no verifica las APIs de
películas ni garantiza conectividad instantánea con Telegram.

No ejecutes el mismo token en otro servidor al mismo tiempo: Telegram permite
un solo consumidor de long polling. Durante un despliegue puede haber un breve
solapamiento entre la versión anterior y la nueva; revisa los logs si aparecen
conflictos persistentes.

### Alternativa: VPS con systemd

La plantilla `deploy/telegram-bot.service` reinicia el bot tras fallos sin límite
de intentos y permite arrancarlo automáticamente al encender el servidor.
Primero instala las dependencias en el entorno virtual del VPS y configura su
`.env`. Adapta `User`, `WorkingDirectory`, `EnvironmentFile` y `ExecStart` a tus
rutas antes de instalar la unidad:

```bash
sudo cp deploy/telegram-bot.service /etc/systemd/system/telegram-bot.service
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-bot
sudo systemctl status telegram-bot
journalctl -u telegram-bot -f
```

En esta opción systemd ejecuta Python directamente: no arranques Supervisor ni
otra copia del bot en paralelo. El VPS debe permanecer encendido.

### Ejecución Local
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./start.sh
```

Las dependencias se instalan una sola vez (o al actualizar), no en cada reinicio.
Sin las variables obligatorias el proceso termina con código de error y deja un
mensaje en los logs. Detén el servicio si necesitas corregir su configuración
para evitar reinicios continuos.

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
- Render: pestaña **Logs** (salida del bot y de Supervisor).
- Local con Supervisor: salida de la terminal y `logs/supervisord.log`.
- VPS con systemd: `journalctl -u telegram-bot -f`.

### Comandos de Control (Supervisor)
Ejecuta desde la raíz del repositorio, en el mismo entorno donde arrancaste:

```bash
supervisorctl -c supervisord.conf status
supervisorctl -c supervisord.conf restart telegram_bot
# Detener todo de forma controlada
supervisorctl -c supervisord.conf shutdown
```

## 🔧 Testing

### Probar Sistema Anti-Spam
```bash
python -m pytest tests/test_spam.py tests/test_formatting.py tests/test_runtime.py
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

Si aparece `Conflict: terminated by other getUpdates request`, detén las copias
anteriores del bot y deja una sola instancia con ese token. No ejecutes
`python bot.py` manualmente mientras Supervisor o systemd ya lo esté gestionando.

### El servicio se duerme o no arranca

- Comprueba que Render no siga usando el plan gratuito; los cambios en el repo
  no cambian automáticamente un servicio existente.
- Revisa `BOT_TOKEN`, `TMDB_API_KEY` y los errores de arranque en los logs.
- Un `/health` con 503 indica que el polling todavía no está listo.
- Si usas VPS, comprueba que la máquina siga encendida y la unidad habilitada.
