# 🟢 Guía Rápida: Cómo mantener el Bot Siempre Despierto 24/7 Gratis ($0/mes)

Esta guía explica cómo desplegar **Telegram Visual Bot** para que **no se duerma**, siga escuchando el grupo en tiempo real y se reinicie automáticamente si hay fallos, sin gastar dinero ni necesitar tarjeta de crédito.

---

## 🧠 ¿Por qué se dormían los bots gratuitos (y cómo funciona aquí)?

1. **GitHub Actions `cron` sufre retrasos**: un cron de `*/14` en GitHub Actions puede retrasarse varias horas cuando hay carga en GitHub, por lo que **no basta por sí solo** para evitar la suspensión a los 15 minutos de Render Free.
2. **El servidor HTTP arranca primero**: `bot.py` abre el puerto web (`/` y `/health`) antes de iniciar el *long polling* con Telegram, usando Supervisor (`start.sh`) para reiniciar automáticamente el proceso ante cualquier caída.
3. **Tráfico externo puntual**:
   - **Opción recomendada**: **Hugging Face Spaces (Docker · 2 vCPU · 16 GB RAM gratis)**, que no se suspende cada 15 minutos (solo tras 48 h sin tráfico).
   - **Alternativa**: **Render Free** (`render.yaml` con `plan: free`) + **cron-job.org** haciendo `GET /health` cada 10 minutos.
   - **Respaldo adicional**: este repo incluye `self_ping` interno cada 5 min y `.github/workflows/keep_alive.yml` cada 14 min si configuras el secreto `BOT_URL`.

> ⚠️ **Importante (diferencia frente a bots de scraping por cron)**:
> Este bot responde **en tiempo real** a mensajes de Telegram mediante *long polling*. **No ejecutes dos instancias a la vez con el mismo `BOT_TOKEN`** (ni en otro servidor ni en GitHub Actions), porque Telegram cerraría una con error `Conflict: terminated by other getUpdates request`.

---

## 🏆 Opción Recomendada #1: Hugging Face Spaces (Gratis · Sin tarjeta)

1. Crea una cuenta gratuita en [huggingface.co](https://huggingface.co) y pulsa **New Space**:
   - **Space name**: `telegram-visual-bot` (o el que prefieras)
   - **SDK**: **Docker** → plantilla **Blank**
   - **Hardware**: **CPU basic · 2 vCPU · 16 GB · FREE**
   - **Visibility**: **Public** (los Spaces privados bloquean el ping externo sin token)
2. En **Settings → Variables and secrets** del Space añade como **Secrets**:
   - `BOT_TOKEN` = *(tu token de BotFather)*
   - `TMDB_API_KEY` = *(tu clave de TMDb)*
   - `OMDB_API_KEY` = *(tu clave de OMDb, opcional)*
   - `GROUP_CHAT_ID` = *(ID numérico del grupo, ej. `-100...`)*
   - `ADMIN_CHAT_ID` = *(opcional, para avisos de errores repetidos)*
3. Sincroniza este repositorio con tu Space (asegurándote de incluir el encabezado YAML de Space en el `README.md` del Space si subes directo):
   ```yaml
   ---
   title: Telegram Visual Bot
   emoji: 🎬
   colorFrom: green
   colorTo: lime
   sdk: docker
   app_port: 7860
   ---
   ```
   El `Dockerfile` de este repositorio ya usa `uid=1000`, expone `7860` y `visualbot/health.py` detecta `SPACE_ID` automáticamente.
4. Tu URL pública será `https://<tu-usuario>-telegram-visual-bot.hf.space` (`/` y `/health`).

---

## ⚡ Paso Clave para 100% Uptime: `cron-job.org` (HF Spaces y Render Free)

**[cron-job.org](https://cron-job.org)** envía peticiones HTTP puntuales gratis:

1. Crea una cuenta gratuita en [console.cron-job.org](https://console.cron-job.org).
2. Pulsa **Create Cronjob**:
   - **Title**: `Keep Telegram Visual Bot Awake`
   - **URL**: `https://<tu-dominio-en-hf-o-render>/health`
   - **Execution schedule**: **Every 10 minutes** (`*/10 * * * *`)
   - Activa **Notify me when cronjob fails** para recibir aviso por email si algún día cae.
3. *(Opcional)* Guarda también la URL base en tu repositorio de GitHub (`Settings → Secrets and variables → Actions → New repository secret`):
   - **Name**: `BOT_URL`
   - **Value**: `https://<tu-dominio-en-hf-o-render>`
   Así `.github/workflows/keep_alive.yml` también hará ping cada ~14 minutos.

---

## 🔄 Opción #2: Render Free (`render.yaml`)

1. En Render → **New + → Blueprint** (o conecta este repositorio).
2. `render.yaml` ya está configurado con `plan: free`, `numInstances: 1`, `startCommand: ./start.sh` y `healthCheckPath: /health`.
3. Rellena tus variables (`BOT_TOKEN`, `TMDB_API_KEY`, `OMDB_API_KEY`, `GROUP_CHAT_ID`, `ADMIN_CHAT_ID`).
4. Configura **cron-job.org** cada 10 minutos apuntando a `https://<tu-servicio>.onrender.com/health` para que Render Free no llegue al límite de 15 minutos sin tráfico.
