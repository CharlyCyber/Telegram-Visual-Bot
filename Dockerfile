# Imagen ligera compatible con Hugging Face Spaces (16 GB RAM Free, uid=1000, puerto 7860) y Render / Koyeb.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860

# Crear usuario no-root uid=1000 (requerido por Hugging Face Spaces) si no existe
RUN id -u 1000 >/dev/null 2>&1 || useradd -m -u 1000 appuser

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY bot.py start.sh supervisord.conf ./
COPY visualbot ./visualbot

RUN chmod +x start.sh && mkdir -p logs run && chown -R 1000:1000 /app

USER 1000

EXPOSE 7860

HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; p=os.environ.get('PORT','7860'); urllib.request.urlopen(f'http://127.0.0.1:{p}/health', timeout=5)"

CMD ["./start.sh"]
