"""Detección de contenido spam, sin cuotas por usuario."""
import re

SPAM_KEYWORDS = [
    # Criptomonedas/Casino
    "eth libre",
    "Ethereum gratis",
    "jetacas",
    "casino",
    "bonificación",
    "código promocional",
    "bienvenido1k",
    "lanzamiento aéreo",
    "cripto",
    "cartera",
    "btc",
    "bitcoin",
    "freeether.net",
    "eth alerta",
    "etéreo",
    "bono instantáneo",
    "plataforma con licencia",
    "apuesta",
    "retirar",
    "depósito",
    "tragaperras",
    "póker",
    "ruleta",
    "blackjack",
    "bingo",
    "lotería",
    "jackpot",
    "giros gratis",
    "sin identificación",
    "24/7 soporte",
    "mínimo depósito",
    "pagos justos",
    "retiros rápidos",
    "e-wallets",
    "live casino",
    "online casino",
    "online gambling",
    "online betting",
    "slots",
    "poker",
    "roulette",
    "free spins",
    "welcome bonus",
    "deposit bonus",
    "no strings attached",
    "no id required",
    "instant bonus activation",
    "top-tier providers",
    "licensed platform",
    "fair payouts",

    # Términos financieros sospechosos
    "ganar dinero",
    "dinero gratis",
    "dinero fácil",
    "ingresos pasivos",
    "roi",
    "forex",
    "sin tarifas",
    "libre de riesgos",
    "garantizado",

    # Llamadas a la acción urgentes
    "haga clic aquí",
    "regístrate ahora",
    "actúa ahora",
    "tiempo limitado",
    "no te lo pierdas",
    "por tiempo limitado",
    "no dura para siempre",
    "lanzamiento aire limitado",
    "reclama ahora",

    # URLs y enlaces sospechosos
    "telegrama.yo",

    # Términos de marketing agresivo
    "trabajar desde casa",
    "mlm",
    "pirámide",
    "Soporte 24 horas al día, 7 días a la semana",
    "depósito mío",
    "carteras eléctricas",
    "se requiere verificación",
    "sin condiciones",
    "implementar registro",
    "conecta tu billetera",
    "el equilibrio cree"
]

# Dominios/URLs de scam conocidos (coincidencia por substring).
# Solo dominios reales: las palabras genéricas ("gratis", "dinero", "casino")
# provocaban falsos positivos en títulos legítimos.
SPAM_URLS = [
    "jetacas.com", "freeether.net", "freecrypto", "cryptogift", "freetokens",
    "onlinecasino.com", "gamblingsite.net", "bettingplatform.org"
]

# Patrones de emojis sospechosos
SPAM_EMOJI_PATTERNS = [
    "🚨", "💰", "🔥", "🔑", "📥", "🔒", "⚡️", "🎮", "🕐", "💵", "✅", "💳", "🤑", "⚡️",
    "⏳", "👉", "🟢", "🎰", "🎲", "👑", "💎"
]


def is_spam_message(texto: str) -> bool:
    """Detecta si un mensaje es spam - VERSIÓN SUPER MEJORADA"""
    if not texto:
        return False

    texto_inferior = texto.lower()

    # 1. Palabras clave con regex (coincidencia exacta de palabras)
    spam_count = 0
    for palabra_clave in SPAM_KEYWORDS:
        if re.search(rf"\b{re.escape(palabra_clave)}\b", texto_inferior):
            spam_count += 1

    # 2. URL con expresiones regulares
    is_spam_url = False
    for url in SPAM_URLS:
        if url in texto_inferior:
            is_spam_url = True
            break

    # 3. Nombres de servicios de scam específicos (NO "casino" a secas: es un
    # título de película legítimo). Solo marcas/dominios inequívocos.
    nombres_casino = ["jetacas", "freeether.net"]
    has_casino_name = any(
        re.search(rf"\b{re.escape(nombre)}\b", texto_inferior)
        for nombre in nombres_casino)

    # 4. Patrones de spam de casino específicos
    patron_casino_especifico = re.search(
        r"(\b(?:jetacas|casino|online casino|online gambling|online betting)\b.*(?:bonus|promo|free spins|launch bonus)|\$1000.*bonus.*promo|\b(?:no id|no verification) required)",
        texto_inferior)

    # 5. Combinación de elementos (emojis + palabras clave de casino/bono + URL)
    has_spam_combo = (
        sum(1 for emoji in SPAM_EMOJI_PATTERNS if emoji in texto) >= 2
        and  # Al menos 2 emojis sospechosos
        any(palabra_clave in texto_inferior for palabra_clave in [
            "casino", "bonificación", "promoción", "jetacas", "bonus",
            "promo code"
        ]) and
        ("jetacas.com" in texto_inferior or "t.me" in texto_inferior
         or "telegram.me" in texto_inferior or "http" in texto_inferior))

    # 6. Estructura de spam (múltiples líneas con emojis)
    lineas = texto.split('\n')
    lineas_emoji = sum(1 for linea in lineas
                       if any(emoji in linea for emoji in SPAM_EMOJI_PATTERNS))
    has_spam_structure = lineas_emoji >= 4

    # 7. Verificar longitud excesiva (spam típico es muy largo)
    is_too_long = len(
        texto) > 250  # Ajustado a 250 para ser más sensible

    # 8. Detección de mayúsculas excesivas (indicador de spam)
    mayusculas_count = sum(1 for char in texto if char.isupper())
    total_letras = sum(1 for char in texto if char.isalpha())
    has_suspicious_caps = False
    if total_letras > 0:
        porcentaje_mayusculas = (mayusculas_count / total_letras) * 100
        if porcentaje_mayusculas > 50 and len(
                texto) > 50:  # Más del 50% de mayúsculas en mensajes largos
            has_suspicious_caps = True

    # Condiciones de detección (más restricciones)
    return (spam_count >= 3 or  # Aumentado a 3 para mayor precisión
            is_spam_url or has_casino_name or
            patron_casino_especifico is not None or has_spam_combo or
            (has_spam_structure and spam_count >= 1) or
            (is_too_long
             and spam_count >= 1) or has_suspicious_caps)
