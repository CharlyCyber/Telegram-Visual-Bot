"""Detección básica de idioma y traducción automática al español."""
import logging
import re
import httpx

from .cache import TTLCache
from .network import shared_client

logger = logging.getLogger(__name__)
WIKI_USER_AGENT = "TelegramVisualBot/1.0 (https://github.com/CharlyCyber/Telegram-Visual-Bot)"

# Géneros habituales en inglés (TMDb, OMDb, TVmaze) -> español.
GENRE_TRANSLATIONS = {
    "action": "Acción",
    "action & adventure": "Acción y Aventura",
    "adventure": "Aventura",
    "animation": "Animación",
    "anime": "Anime",
    "biography": "Biografía",
    "children": "Infantil",
    "comedy": "Comedia",
    "crime": "Crimen",
    "diy": "Bricolaje",
    "documentary": "Documental",
    "drama": "Drama",
    "espionage": "Espionaje",
    "family": "Familia",
    "fantasy": "Fantasía",
    "film-noir": "Cine negro",
    "food": "Gastronomía",
    "game-show": "Concurso",
    "history": "Historia",
    "horror": "Terror",
    "kids": "Infantil",
    "legal": "Legal",
    "medical": "Médico",
    "music": "Música",
    "musical": "Musical",
    "mystery": "Misterio",
    "nature": "Naturaleza",
    "news": "Noticias",
    "reality": "Reality",
    "reality-tv": "Reality",
    "romance": "Romance",
    "sci-fi": "Ciencia ficción",
    "sci-fi & fantasy": "Ciencia ficción y Fantasía",
    "science fiction": "Ciencia ficción",
    "science-fiction": "Ciencia ficción",
    "short": "Cortometraje",
    "soap": "Telenovela",
    "sport": "Deportes",
    "sports": "Deportes",
    "supernatural": "Sobrenatural",
    "talk": "Programa de entrevistas",
    "talk-show": "Programa de entrevistas",
    "thriller": "Suspense",
    "travel": "Viajes",
    "tv movie": "Película de TV",
    "war": "Bélica",
    "war & politics": "Guerra y Política",
    "western": "Western",
}

# Palabras claramente españolas que no coinciden con inglés/portugués habituales.
_ES_STRICT_WORDS = frozenset({
    "el", "los", "las", "un", "una", "unos", "unas", "del", "al",
    "en", "con", "sin", "hacia", "hasta", "desde", "pero", "sino",
    "sus", "les", "lo", "es", "fue", "fueron", "están", "tiene", "tienen",
    "también", "después", "mientras", "cuando", "donde", "quien", "quienes",
    "cual", "todos", "todas", "nuevo", "nueva", "nuevos", "nuevas",
    "historia", "familia", "temporada", "sinopsis", "película", "pelicula",
    "ficha", "edición", "edicion", "más", "mujer", "hombre", "años",
    "serie", "misterio", "asesino", "venganza", "parejas", "prueba",
    "novela", "telenovela", "programa", "descubre", "programador",
    "simulación", "secreto", "hermanos", "ambiciosa", "llega", "viven",
    "ocultado", "durante", "policía", "policia", "cía", "cia", "y",
})

# Palabras españolas generales (incluyendo cognados románicos ausentes del inglés).
_ES_WORDS = _ES_STRICT_WORDS | frozenset({
    "la", "de", "que", "por", "porque", "sobre", "entre", "amor",
    "aventura", "mundo", "vida", "joven", "mas", "está", "o",
})

# Palabras funcionales inequívocamente inglesas (sin solapamientos ni préstamos habituales en español).
_EN_WORDS = frozenset({
    "the", "and", "of", "to", "in", "is", "that", "it", "for", "with", "as",
    "was", "were", "are", "be", "been", "being", "this", "these", "those",
    "from", "by", "at", "an", "or", "but", "not", "have", "had", "will",
    "would", "could", "should", "must", "their", "they", "them", "there",
    "where", "when", "who", "which", "what", "whose", "while", "after",
    "before", "during", "through", "about", "into", "over", "under",
    "between", "against", "his", "her", "hers", "its", "our", "your", "she",
    "him", "young", "life", "story", "world", "family", "friends", "man",
    "woman", "women", "men", "girl", "boy", "school", "town", "city",
    "house", "home", "team", "group", "finds", "discovers", "learns",
    "follows", "becomes", "begins", "tries", "lives", "years", "love",
    "death", "war", "secret", "mystery", "two", "three", "four", "five",
    "old", "first", "last", "only", "another", "each", "other", "more",
    "most", "some", "all", "many", "such", "than", "then", "now", "out",
    "away", "off", "just", "very", "also", "because", "however", "although",
    "until", "since", "murder", "police", "season", "movie", "based", "true",
    "takes", "struggles", "forced", "save", "he", "we", "you", "can", "set",
    "crime", "investigates", "uncovers", "returns", "escapes", "attempts",
    "confronts", "recounts", "explores", "chronicles", "journey", "survival",
    "relationship", "daughter", "son", "mother", "father", "husband", "wife",
    "brother", "sister", "couple", "village", "island", "country", "battle",
    "power", "evil", "dark",
})

# Palabras inequívocamente portuguesas (distintas del español).
_PT_WORDS = frozenset({
    "não", "nao", "uma", "um", "uns", "umas", "pelo", "pela", "pelos",
    "pelas", "das", "num", "numa", "são", "sao", "estão", "estao", "você",
    "voce", "vocês", "voces", "eles", "elas", "seu", "sua", "seus", "suas",
    "isso", "isto", "aquilo", "muito", "muita", "muitos", "muitas", "mais",
    "também", "tambem", "ainda", "depois", "onde", "quem", "história",
    "família", "série", "filme", "jovem", "após", "apos", "através",
    "atraves", "até", "ate", "sem", "mesmo", "outro", "outra", "é", "ao",
    "aos", "às", "com", "em", "brasileira", "brasileiro", "irmãos", "irmaos",
    "apaixona", "sobrevivência", "casal",
})

# Palabras inequívocamente francesas / italianas / alemanas frecuentes en sinopsis.
_OTHER_ROMANCE_WORDS = frozenset({
    "dans", "avec", "pour", "qui", "sont", "cette", "elle", "ils", "leur",
    "après", "histoire", "jeune", "femme", "homme", "monde", "vie", "nous",
    "vous", "mais", "comme", "être", "avoir", "faire", "tout", "tous",
    "della", "dello", "degli", "delle", "nella", "nel", "alla", "gli",
    "che", "storia", "dopo", "anche", "perché", "più", "donna", "uomo",
    "der", "die", "und", "ein", "eine", "einer", "mit", "für", "von",
    "auf", "ist", "sind", "wird", "sich", "nach", "über", "leben",
})

_NON_LATIN_RE = re.compile(
    r"[\u0400-\u04FF\u0600-\u06FF\u0590-\u05FF\u0370-\u03FF"
    r"\u4E00-\u9FFF\u3040-\u30FF\uAC00-\uD7AF\u0E00-\u0E7F\u0900-\u097F]"
)
_FOREIGN_DIACRITIC_WORD_RE = re.compile(r"\w*[ãõçêâôàèìòùäöüßğşıİœæ]\w*", re.IGNORECASE)
_EN_CONTRACTION_RE = re.compile(r"\b\w+(?:'s|'t|'re|'ve|'ll|'d|'m)\b", re.IGNORECASE)


def translate_genre(name: str) -> str:
    if not isinstance(name, str):
        return str(name or "")
    cleaned = name.strip()
    if not cleaned:
        return ""
    return GENRE_TRANSLATIONS.get(cleaned.casefold(), cleaned)


def translate_genres(genres) -> list[str]:
    if not genres:
        return []
    result = []
    for genre in genres:
        translated = translate_genre(genre)
        if translated and translated not in result:
            result.append(translated)
    return result


def normalize_season_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    cleaned = " ".join(name.split())
    if not cleaned:
        return ""
    match = re.fullmatch(r"(?:Season|Series)\s+(\d+)", cleaned, re.I)
    if match:
        return f"Temporada {match.group(1)}"
    match = re.fullmatch(r"Part\s+(\d+)", cleaned, re.I)
    if match:
        return f"Parte {match.group(1)}"
    low = cleaned.casefold()
    if low == "specials":
        return "Especiales"
    if low in ("miniseries", "limited series", "mini-series"):
        return "Miniserie"
    return cleaned


def _lang_scores(text: str) -> dict[str, int]:
    words = re.findall(r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑãõçêâôàèìòùäöüßğşıİœæ]+", text.lower())
    es = sum(1 for w in words if w in _ES_WORDS)
    es_strict = sum(1 for w in words if w in _ES_STRICT_WORDS)
    en = sum(1 for w in words if w in _EN_WORDS) + len(_EN_CONTRACTION_RE.findall(text))
    pt = sum(1 for w in words if w in _PT_WORDS)
    other = sum(1 for w in words if w in _OTHER_ROMANCE_WORDS)
    # Puntuar levemente diacriticos exclusivos del español (ñ, ¡, ¿, áéíóúü) si no hay señales portuguesas.
    if any(ch in text for ch in "ñÑ¡¿"):
        es += 2
        es_strict += 2
    elif any(ch in text for ch in "áéíóúüÁÉÍÓÚÜ") and pt == 0 and not _FOREIGN_DIACRITIC_WORD_RE.search(text):
        es += 1
        es_strict += 1
    foreign_diacritics = len(_FOREIGN_DIACRITIC_WORD_RE.findall(text))
    return {
        "total": len(words),
        "es": es,
        "es_strict": es_strict,
        "en": en,
        "pt": pt,
        "other": other,
        "foreign_diacritics": foreign_diacritics,
        "non_latin": len(_NON_LATIN_RE.findall(text)),
    }


def needs_translation(text: str, *, source_lang: str | None = None) -> bool:
    """Indica si el texto necesita traducirse al español."""
    if not isinstance(text, str):
        return False
    cleaned = text.strip()
    if not cleaned or cleaned.casefold() in ("n/a", "n/d", "none"):
        return False

    scores = _lang_scores(cleaned)
    if scores["non_latin"] >= 3:
        return True

    lang = source_lang.split("-")[0].lower() if isinstance(source_lang, str) and source_lang else None

    if lang == "es":
        # Detectar textos en inglés o portugués mal etiquetados en campos es-ES/es-MX.
        if scores["en"] >= 2 and (scores["en"] > scores["es"] * 2 or scores["es"] <= 1):
            return True
        if scores["pt"] >= 2 and (scores["pt"] > scores["es_strict"] * 2 or scores["es_strict"] <= 1):
            return True
        if scores["foreign_diacritics"] >= 3 and scores["es_strict"] <= 1:
            return True
        return False

    if lang == "en":
        # Si ya viene claramente en español (ej. mocks en español), no traducir.
        if scores["es"] >= 1 and scores["en"] == 0 and scores["pt"] == 0 and scores["foreign_diacritics"] == 0:
            return False
        return scores["total"] >= 1

    if lang is not None:
        # Otro idioma declarado explícitamente (pt, fr, tr, de, ja, ko, etc.).
        if scores["es_strict"] >= 2 and scores["en"] == 0 and scores["pt"] == 0 and scores["foreign_diacritics"] == 0:
            return False
        return scores["total"] >= 1 or scores["foreign_diacritics"] >= 1

    # Idioma desconocido: exigir señales positivas de otro idioma y evitar falsos positivos con nombres propios.
    if scores["en"] >= 2 and scores["en"] > scores["es"]:
        return True
    if scores["pt"] >= 2 and scores["pt"] > scores["es_strict"]:
        return True
    if scores["other"] >= 2 and scores["other"] > scores["es_strict"]:
        return True
    if scores["foreign_diacritics"] >= 2 and scores["foreign_diacritics"] > scores["es_strict"]:
        return True
    if scores["es"] == 0 and scores["total"] >= 3 and (
        scores["en"] >= 1 or scores["pt"] >= 1 or scores["other"] >= 1 or scores["foreign_diacritics"] >= 1
    ):
        return True
    return False


def _split_chunks(text: str, max_len: int = 900) -> list[str]:
    text = " ".join(text.split())
    if len(text) <= max_len:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_len:
            if current:
                chunks.append(current)
                current = ""
            words = sentence.split(" ")
            part = ""
            for word in words:
                candidate = f"{part} {word}".strip() if part else word
                if len(candidate) <= max_len:
                    part = candidate
                else:
                    if part:
                        chunks.append(part)
                    part = word[:max_len]
            if part:
                chunks.append(part)
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_len:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks or [text[:max_len]]


def _guess_mymemory_source(text: str, source_lang: str | None) -> str:
    if source_lang and source_lang != "auto":
        code = source_lang.split("-")[0].lower()
        if code and code != "es":
            return code
    scores = _lang_scores(text)
    if scores["pt"] > scores["en"] and scores["pt"] > 0:
        return "pt"
    return "en"


async def _google_translate(client, text: str, src: str) -> str | None:
    parts: list[str] = []
    for chunk in _split_chunks(text, max_len=900):
        resp = await client.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": src, "tl": "es", "dt": "t", "q": chunk},
            timeout=6,
        )
        data = resp.json()
        if not isinstance(data, list) or not data or not isinstance(data[0], list):
            return None
        translated = "".join(
            segment[0]
            for segment in data[0]
            if isinstance(segment, list) and segment and isinstance(segment[0], str)
        ).strip()
        if not translated:
            return None
        parts.append(translated)
    return " ".join(parts).strip() or None


async def _mymemory_translate(client, text: str, src: str) -> str | None:
    pair_src = _guess_mymemory_source(text, src)
    parts: list[str] = []
    for chunk in _split_chunks(text, max_len=450):
        resp = await client.get(
            "https://api.mymemory.translated.net/get",
            params={"q": chunk, "langpair": f"{pair_src}|es"},
            timeout=6,
        )
        data = resp.json()
        if not isinstance(data, dict) or str(data.get("responseStatus")) != "200":
            return None
        translated = (data.get("responseData") or {}).get("translatedText")
        if not isinstance(translated, str) or not translated.strip():
            return None
        upper = translated.upper()
        if "MYMEMORY WARNING" in upper or "QUERY LENGTH LIMIT" in upper:
            return None
        parts.append(translated.strip())
    return " ".join(parts).strip() or None


@TTLCache(ttl_seconds=3600, maxsize=512, cache_if=bool)
async def _translate_remote(text: str, src: str) -> str | None:
    async with shared_client() as client:
        for backend in (_google_translate, _mymemory_translate):
            try:
                translated = await backend(client, text, src)
                if translated:
                    return translated
            except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError) as exc:
                logger.warning("Fallo en backend de traducción (%s): %s", backend.__name__, exc)
    return None


async def ensure_spanish(text: str, *, source_lang: str | None = None) -> str:
    """Devuelve el texto en español, traduciéndolo solo si no está ya en español."""
    if not isinstance(text, str):
        return ""
    cleaned = " ".join(text.split())
    if not cleaned:
        return ""
    if not needs_translation(cleaned, source_lang=source_lang):
        return cleaned
    src = source_lang.split("-")[0].lower() if isinstance(source_lang, str) and source_lang else "auto"
    if src == "es":
        # Estaba etiquetado como español pero su contenido no lo es: autodetectar idioma real.
        src = "auto"
    translated = await _translate_remote(cleaned, src)
    return translated or cleaned


def clear_translation_cache():
    _translate_remote.cache_clear()
