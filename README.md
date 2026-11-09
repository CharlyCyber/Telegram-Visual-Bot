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

## 🌐 Fuentes oficiales adicionales sin API (especialmente novelas)

La mayoría de las fuentes oficiales se consultan si TMDb y los respaldos
actuales no encuentran una ficha. Mediaset se consulta también después de elegir
una serie de TMDb, para ofrecer su ficha como alternativa. La capa adicional
que lee **catálogos HTML públicos**, sin claves nuevas, APIs privadas, buscadores
externos ni navegador automatizado. El JSON-LD que algunas páginas incluyen en
su propio HTML se usa como metadatos, no como un endpoint de API.

| Fuente nueva | Catálogos consultados / cobertura orientativa |
|---|---|
| [Telemundo](https://www.telemundo.com/shows) | Novelas latinas y turcas de su catálogo, series, shows y realities. |
| [Las Estrellas](https://www.lasestrellas.tv/telenovelas) | Telenovelas de su catálogo público. |
| [Caracol TV](https://www.caracoltv.com/programas) | Novelas, series, entretenimiento y concursos. |
| [RTVE Play](https://www.rtve.es/play/colecciones/telenovelas/229/) | Novelas, [archivo](https://www.rtve.es/play/colecciones/play-archivo-novelas/275/), series, documentales y programas con ficha propia. |
| [Globoplay](https://globoplay.globo.com/categorias/novelas/) | Novelas brasileñas, colecciones 2000/2020, series y películas. Metadatos en el idioma original, normalmente portugués. |
| [Atresplayer](https://www.atresplayer.com/series/) | Series, novelas y programas enlazados en sus catálogos públicos. |
| [Mediaset Infinity](https://www.mediasetinfinity.es/programas-tv) | Temporada identificable en la portada de programas del catálogo público. |

No se anuncia una cobertura universal: solo se encuentran obras **enlazadas en
las páginas de catálogo configuradas** y con metadatos recuperables sin ejecutar
JavaScript. No se recorren todas las páginas, temporadas o paginaciones. No se
inventan enlaces, traducciones de títulos, sinopsis ni años. Los nombres
alternativos se usan cuando la propia fuente los proporciona. Si buscas un año
concreto, se exige una fecha de estreno identificable y coincidente; una ficha
sin año no se presenta como si correspondiera a esa versión.

### Compatibilidad y uso

- Orden: TMDb; si no hay coincidencia, Mediaset → TVmaze → OMDb → Danfra →
  Lámpara Turca → los demás catálogos oficiales. Al elegir una serie de TMDb
  también se consulta Mediaset para ofrecer una opción adicional.
- Una ficha oficial se publica en el grupo configurado; varias coincidencias se
  muestran para elegir con el mismo sistema numérico ya existente. Se eliminan
  duplicados, conservando versiones con años diferentes.
- Se comprueba el título y se descartan rutas de noticias/capítulos y metadatos
  editoriales o de episodios. En los catálogos generales, una ficha sin título
  pertinente y descripción no se publica. Son filtros conservadores, no una garantía absoluta de identidad.
- Las fichas incluyen atribución y enlace oficial. Las imágenes se aceptan solo
  de dominios/CDN configurados; si la imagen falla, se envía texto.
- La disponibilidad del vídeo en un país, una suscripción o los derechos de
  distribución **no se deducen** de que exista la ficha. El bot no descarga ni
  redistribuye vídeos.

### Configuración opcional

Sin `WEB_SOURCES`, se habilitan las siete fuentes. Para seleccionar algunas:

```env
WEB_SOURCES=telemundo,las_estrellas,caracol,rtve,globoplay,atresplayer,mediaset
```

Usa `WEB_SOURCES=none` para desactivar únicamente esta nueva capa y volver al
comportamiento previo. No hacen falta nuevas claves. Las APIs ya existentes
siguen funcionando como antes y mantienen sus requisitos de configuración.

### Protección de fuentes y estabilidad

Se consulta y cachea `robots.txt`; si prohíbe el acceso o no se puede verificar,
se omite el sitio (un 404 de robots se interpreta como ausencia de restricciones).
Se respetan reglas con comodines, el agente específico y `Crawl-delay`, con al
menos un segundo entre solicitudes del mismo dominio. No se sortean CAPTCHAs,
logins, bloqueos regionales ni protecciones anti-bot. Un bloqueo 403/429/503
activa una pausa temporal del dominio; otros proveedores siguen disponibles.

Hay comprobación de dominios y redirecciones antes de seguirlas, límites de
tamaño de respuesta, timeout por solicitud y un presupuesto global de **28
segundos para esta capa adicional**. Se conservan los resultados completados y
se cancelan las consultas pendientes. Por defecto se muestran hasta 8 fichas y
se examinan hasta 3 candidatos por página. Esto limita trabajo por búsqueda,
**no el número de búsquedas que puede hacer un usuario**.

Se cachean políticas durante 5 minutos, HTML durante 15 minutos (hasta 64 páginas)
y búsquedas oficiales con resultados durante 5 minutos (hasta 128 entradas).
Los fallos no se guardan como resultados de búsqueda. Las fuentes opcionales
caídas o bloqueadas no generan por sí solas un fallo global del bot.

**Verificación:** se revisaron páginas públicas de catálogo y robots durante el
desarrollo. Las pruebas automáticas de los adaptadores usan HTML sintético y
HTTP simulado; no constituyen una prueba en vivo de cada sitio desde el servidor
del bot. Antes de desplegar, verifica desde tu alojamiento búsquedas concretas
(por ejemplo, `Pasión de Gavilanes`, `Rubí`, `La Promesa`, `Rosalinda`), los logs y
los permisos de uso. No se garantiza que cada ejemplo se resuelva en cada país.
Las estructuras web y las restricciones pueden cambiar.

Respetar robots **no concede licencia** para reutilizar textos o imágenes ni
reemplaza revisar las condiciones de uso de cada fuente, especialmente si vas
a comercializar el servicio. No se añaden sitios indiscriminadamente solo por
ser conocidos: una página inaccesible o sin catálogo utilizable no es una fuente
fiable para este bot.

## 🏷️ Identificar resultados con títulos parecidos

Las opciones numéricas muestran, cuando la fuente aporta los datos:

- Tipo: película, serie, telenovela, reality, programa de entrevistas, documental
  o animación. Se usa una categoría genérica si no hay información suficiente.
- País(es) de origen, con bandera y nombres habituales traducidos al español.
- Título original, si difiere del título mostrado.
- Otros títulos, únicamente si la fuente los declara explícitamente.

Ejemplo ilustrativo de formato (no una identificación verificada de una obra):

```text
1. El secreto (2025) · 📺 Telenovela · 🇹🇷 Turquía
   Título original: [nombre original proporcionado por la fuente]
```

En TMDb se aprovechan `origin_country`, `original_name`/`original_title` y los
identificadores de géneros ya incluidos en los resultados. No se hacen consultas
adicionales por cada opción, ni se altera la numeración o la selección. Las listas
largas se reparten en varios mensajes sin exceder el límite de Telegram.
Las fichas publicadas también incluyen estos datos antes de la sinopsis cuando
están disponibles; el país de producción se identifica separadamente.

En los catálogos HTML, el origen se toma de `countryOfOrigin` del JSON-LD y el
tipo de sus metadatos de la obra. Los nombres alternativos declarados se conservan.
En OMDb se muestra el país que la fuente declara; en TVmaze se aprovecha el tipo
de programa, pero **el país del canal emisor no se usa como país de origen**.

No se deduce que una obra sea turca por su idioma, por su título ni por aparecer
en Lámpara Turca, Telemundo u otra plataforma. Tampoco se transforma cualquier
serie de Turquía en «telenovela»: hace falta una clasificación explícita (por
ejemplo, género Soap). Si falta el país, simplemente no se muestra. Esta mejora
no crea equivalencias automáticas entre títulos: solo muestra los datos recibidos.

## 📺 Temporadas de series y realities

Al seleccionar una serie de TMDb, el bot muestra automáticamente la temporada
regular más reciente con fecha de estreno válida que ya haya comenzado. No
selecciona especiales (temporada 0), temporadas futuras ni temporadas sin fecha.
Si hay varias temporadas, se presenta una lista numerada: responde con el número
**de la opción** para mostrar otra temporada, `0` para terminar o `/cancel` para
cancelar. En títulos ambiguos, primero se elige el programa y después la temporada.

Para buscar una temporada por año, escribe por ejemplo `La isla de las tentaciones 2026`. El año filtra el estreno de películas; para series se busca el programa sin
filtrar su primer estreno y se elige la temporada estrenada en ese año. Si hay
varias, se usa la más reciente. Si no hay ninguna, se indica claramente que la
ficha mostrada es general y se permite elegir otras temporadas disponibles.

Los datos de la temporada proceden de TMDb; si no tiene sinopsis de la temporada,
no se presenta la sinopsis general como si fuera de ella. La ficha distingue los
recuentos de la temporada de los totales de la serie. Si no se encuentra una
temporada, se intenta buscar una ficha general en los catálogos oficiales ya
configurados; no se garantiza que tengan datos de temporadas ni cobertura del
programa. La actualidad y cobertura de las fichas dependen de las fuentes y sus fechas.

### Mediaset Infinity

Tras seleccionar un programa en TMDb, se busca también en el catálogo público de
Mediaset. Si se identifica una temporada en su portada, aparece como opción
separada, con atribución y enlace oficial. No se mezclan ni comparan como si
fueran equivalentes los números de temporada de ambas fuentes; el usuario decide
cuál publicar. Si no hay resultados de TMDb, se intenta Mediaset antes de los
respaldos genéricos. Una búsqueda con año solo muestra la ficha si ese año se
identifica explícitamente en la cabecera de la temporada.

La búsqueda requiere un título normalizado exactamente igual, un título de ficha
con número de temporada y un enlace explícito a esa temporada en la misma ficha.
No inventa enlaces, años o sinopsis; sin una descripción estructurada de esa
edición, indica que no está disponible. Solo se consulta la portada enlazada en
el catálogo, no todas las temporadas ni episodios. Programas con nombres de
edición diferentes, acceso restringido o HTML dependiente de JavaScript pueden
no aparecer. La integración usa el mismo control de robots, dominios, caché y
límites de las fuentes web, con un máximo de 15 segundos por búsqueda de Mediaset.
Las pruebas son simuladas: hay que verificar el acceso y la estructura real desde
el servidor de despliegue. Respetar robots no sustituye comprobar las condiciones
de uso y licencias de Mediaset.
