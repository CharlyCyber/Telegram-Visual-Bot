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

Puedes copiar `.env.example` a `.env` para ejecución local. En Render, configura
las variables desde el panel del servicio.
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

### Ejecutar todas las pruebas
```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Las pruebas usan respuestas HTTP simuladas, sin tokens reales ni acceso a APIs.
Incluyen búsquedas, fallbacks, errores, alertas, caché, ciclo de vida HTTP,
formato, anti-spam y disponibilidad. Una petición externa no simulada hace fallar
la prueba. Las pruebas asíncronas tienen assertions reales: no ocultan fallos
retornando `False`.

GitHub Actions ejecuta la suite en Python 3.11 y 3.12 con cada push y pull request.
Para impedir merges con pruebas fallidas, configura además una regla de protección
en GitHub que requiera estos checks; el workflow por sí solo no bloquea merges.

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

## 🧩 Organización y fiabilidad

`bot.py` es el punto de entrada; los componentes están en `visualbot/`:

- `config.py`: configuración de entorno y constantes.
- `handlers.py`: comandos, membresía y selección de resultados.
- `providers.py`: TMDb, TVmaze, OMDb y fuentes alternativas.
- `formatting.py` / `spam.py`: presentación y análisis de contenido. Las fichas
  largas se acortan sin romper HTML, contando los emojis en unidades UTF-16.
- `network.py` / `cache.py`: conexiones HTTP reutilizables y caché TTL/LRU.
- `errors.py` / `logging_setup.py` / `health.py`: errores, logs y disponibilidad.

**No hay cuotas ni límites de búsquedas por usuario.** Se mantiene la comprobación
de membresía y el filtro de contenido spam. La caché limita únicamente el número
de resultados guardados en memoria: hasta 256 entradas por función, durante
5 minutos, con eliminación de entradas caducadas en la siguiente consulta y
evicción de las menos usadas cuando se llena. Las excepciones no se cachean;
los proveedores secundarios tampoco guardan resultados vacíos. Cada respuesta
cacheada se copia para que una selección no modifique resultados de otra búsqueda.

Las consultas a proveedores comparten un pool HTTP, con timeout y reintentos de
conexión. Se cierra al apagar el bot. Los errores HTTP no se confunden con
búsquedas vacías: se prueban las fuentes alternativas y, si no es posible
completar la búsqueda, el manejador global informa al usuario. Los fallos no
controlados se registran con su traceback; las claves conocidas y los tokens en
URLs se ocultan. No publiques los logs sin revisarlos, pues pueden contener
identificadores de usuario y datos del servicio.

### Alertas opcionales al administrador

Añade `ADMIN_CHAT_ID` a las variables del servicio o a tu `.env` con el ID del
chat que recibirá las alertas. Si es un chat privado, abre antes una conversación
con el bot; si es un grupo, añade el bot y dale permiso para enviar mensajes.
Sin esta variable, el bot sigue funcionando sin alertas al administrador.

El bot avisa tras **3 fallos no controlados en 5 minutos**, con una separación
mínima de 5 minutos entre alertas. Esta agrupación solo afecta a los avisos del
administrador, **no al uso del bot**. No incluye mensajes de usuarios, claves ni
el contenido de excepciones en la alerta. Si Telegram está caído, la alerta
puede no llegar: revisa también los logs del alojamiento.
