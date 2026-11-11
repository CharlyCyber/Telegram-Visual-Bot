"""Consultas a proveedores y publicación de sus fichas."""
import asyncio
from datetime import date
from difflib import SequenceMatcher
import logging
import re
import unicodedata
from urllib.parse import quote
import httpx
from bs4 import BeautifulSoup
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from .cache import TTLCache
from .config import TMDB_API_KEY, OMDB_API_KEY, FIRME, SEP, SEP_SOFT, SEP_STAR
from .formatting import (esc, get_genre_emojis,
                         get_synopsis_with_emojis, get_dynamic_closing, render_tmdb_caption)
from .network import shared_client
from .result_labels import send_options, identity_fields, country_text
from .translator import (
    WIKI_USER_AGENT,
    ensure_spanish,
    needs_translation,
    normalize_season_name,
    translate_genres,
)

logger = logging.getLogger(__name__)

_PLACEHOLDER_TEXTS = frozenset({
    "n/a", "n/d", "none", "tba", "tbd", "...", "-",
    "no overview found.", "no overview found",
    "sin descripción disponible.", "sin descripción disponible",
    "sin descripcion disponible.", "sin descripcion disponible",
    "sin descripción.", "sin descripción",
    "no synopsis available.", "no description available.",
})
_MOVIE_WIKI_HINTS = (
    "película", "pelicula", "film", "largometraje", "cortometraje",
    "documental", "documentary", "movie", "cinta", "animated", "animación",
)
_TV_WIKI_HINTS = (
    "serie", "telenovela", "novela", "miniserie", "miniseries", "programa",
    "reality", "anime", "television", "tv series", "series", "soap opera",
    "sitcom", "teleserie", "concurso",
)


class ProviderError(RuntimeError):
    """Un proveedor no pudo responder correctamente."""


def _clean_text(value) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = " ".join(value.split())
    if not cleaned or cleaned.casefold() in _PLACEHOLDER_TEXTS:
        return ""
    return cleaned


def _clean_html_text(value) -> str:
    if not isinstance(value, str) or not value.strip():
        return ""
    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    return _clean_text(text)


def _norm_title(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(re.findall(r"\w+", text))


def _pick_tmdb_translation(translations_obj, *, field: str = "overview", original_language: str | None = None):
    entries = (translations_obj or {}).get("translations") if isinstance(translations_obj, dict) else None
    if not isinstance(entries, list):
        return None
    best = None
    best_rank = None
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        data = entry.get("data")
        if not isinstance(data, dict):
            continue
        value = _clean_text(data.get(field))
        if not value:
            continue
        lang = (entry.get("iso_639_1") or "").lower()
        region = (entry.get("iso_3166_1") or "").upper()
        if lang == "es" and region == "ES":
            prio = 0
        elif lang == "es" and region == "MX":
            prio = 1
        elif lang == "es" and region == "419":
            prio = 2
        elif lang == "es":
            prio = 3
        elif lang == "en" and region == "US":
            prio = 4
        elif lang == "en":
            prio = 5
        elif original_language and lang == original_language.lower():
            prio = 6
        else:
            prio = 7
        rank = (prio, idx)
        if best_rank is None or rank < best_rank:
            best_rank = rank
            best = (value, lang or None)
    return best


def _pick_tmdb_spanish_name(translations_obj) -> str:
    entries = (translations_obj or {}).get("translations") if isinstance(translations_obj, dict) else None
    if not isinstance(entries, list):
        return ""
    best = ""
    best_rank = None
    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        if (entry.get("iso_639_1") or "").lower() != "es":
            continue
        data = entry.get("data")
        if not isinstance(data, dict):
            continue
        name = _clean_text(data.get("name"))
        if not name:
            continue
        region = (entry.get("iso_3166_1") or "").upper()
        prio = 0 if region == "ES" else 1 if region == "MX" else 2 if region == "419" else 3
        rank = (prio, idx)
        if best_rank is None or rank < best_rank:
            best_rank = rank
            best = name
    return best


async def _fetch_omdb_plot(client, *, imdb_id=None, title=None, original_title=None, year=None, is_movie=True) -> str:
    if not OMDB_API_KEY:
        return ""
    year_str = str(year) if year and re.fullmatch(r"(?:19|20)\d{2}", str(year)) else ""
    queries = []
    if imdb_id:
        queries.append(({"i": imdb_id, "apikey": OMDB_API_KEY}, False))
    else:
        seen = set()
        for candidate in (original_title, title):
            cleaned = _clean_text(candidate)
            if not cleaned or cleaned.casefold() in seen:
                continue
            seen.add(cleaned.casefold())
            base = {
                "t": cleaned,
                "type": "movie" if is_movie else "series",
                "apikey": OMDB_API_KEY,
            }
            if year_str:
                queries.append((dict(base, y=year_str), False))
                queries.append((base, True))
            else:
                queries.append((base, False))
    for params, check_year in queries:
        try:
            resp = await client.get("https://www.omdbapi.com/", params=params, timeout=6)
            data = resp.json()
            if isinstance(data, dict) and data.get("Response") == "True":
                if check_year and year_str:
                    omdb_year = str(data.get("Year") or "")[:4]
                    if omdb_year.isdigit() and abs(int(omdb_year) - int(year_str)) > 1:
                        continue
                plot = _clean_text(data.get("Plot"))
                if plot:
                    return plot
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError) as exc:
            logger.warning("No se pudo obtener sinopsis de OMDb: %s", exc)
    return ""


async def _fetch_tvmaze_overview(
    client,
    *,
    imdb_id=None,
    tvdb_id=None,
    title=None,
    original_title=None,
    year=None,
    season_number=None,
) -> str:
    show_data = None
    lookup_candidates = []
    if imdb_id:
        lookup_candidates.append(("https://api.tvmaze.com/lookup/shows", {"imdb": imdb_id}))
    if tvdb_id:
        lookup_candidates.append(("https://api.tvmaze.com/lookup/shows", {"thetvdb": tvdb_id}))
    for url, params in lookup_candidates:
        try:
            resp = await client.get(url, params=params, timeout=6)
            data = resp.json()
            if isinstance(data, dict) and data.get("id"):
                show_data = data
                break
        except (httpx.HTTPError, ValueError, TypeError):
            continue

    if show_data is None:
        targets = {_norm_title(t) for t in (title, original_title) if _clean_text(t)}
        for q in dict.fromkeys(t for t in (original_title, title) if _clean_text(t)):
            try:
                resp = await client.get("https://api.tvmaze.com/search/shows", params={"q": q}, timeout=6)
                results = resp.json()
                if not isinstance(results, list):
                    continue
                for entry in results[:5]:
                    show = entry.get("show") if isinstance(entry, dict) else None
                    if not isinstance(show, dict):
                        continue
                    if _norm_title(show.get("name", "")) not in targets:
                        continue
                    premiered = str(show.get("premiered") or "")[:4]
                    if year and premiered.isdigit() and abs(int(premiered) - int(year)) > 1:
                        continue
                    show_data = show
                    break
                if show_data is not None:
                    break
            except (httpx.HTTPError, ValueError, TypeError):
                continue

    if not isinstance(show_data, dict):
        return ""

    if season_number is not None and show_data.get("id"):
        try:
            resp = await client.get(f"https://api.tvmaze.com/shows/{show_data['id']}/seasons", timeout=6)
            seasons = resp.json()
            if isinstance(seasons, list):
                for season in seasons:
                    if isinstance(season, dict) and season.get("number") == season_number:
                        return _clean_html_text(season.get("summary"))
        except (httpx.HTTPError, ValueError, TypeError):
            return ""
        return ""

    return _clean_html_text(show_data.get("summary"))


async def _fetch_wiki_rest_summary(client, lang: str, page_title: str) -> dict | None:
    slug = quote(page_title.replace(" ", "_"), safe="")
    try:
        resp = await client.get(
            f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{slug}",
            headers={"User-Agent": WIKI_USER_AGENT},
            timeout=6,
        )
        data = resp.json()
        return data if isinstance(data, dict) else None
    except (httpx.HTTPError, ValueError, TypeError):
        return None


def _wiki_title_matches(candidate_title: str, targets: set[str]) -> bool:
    base = re.sub(r"\s*\([^)]*\)\s*$", "", candidate_title).strip()
    norm_base = _norm_title(base)
    if not norm_base:
        return False
    if norm_base in targets:
        return True
    return any(
        len(target.split()) >= 2 and len(norm_base.split()) >= 2
        and SequenceMatcher(None, norm_base, target).ratio() >= 0.92
        for target in targets
    )


async def _fetch_wikipedia_overview(
    client,
    *,
    wikidata_id=None,
    title=None,
    original_title=None,
    year=None,
    is_movie=True,
    season_number=None,
) -> tuple[str, str] | None:
    if wikidata_id and season_number is None:
        try:
            resp = await client.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbgetentities",
                    "ids": wikidata_id,
                    "props": "sitelinks",
                    "sitefilter": "eswiki|enwiki",
                    "format": "json",
                },
                headers={"User-Agent": WIKI_USER_AGENT},
                timeout=6,
            )
            data = resp.json()
            entity = ((data.get("entities") or {}).get(wikidata_id) or {}) if isinstance(data, dict) else {}
            sitelinks = entity.get("sitelinks") or {}
            for site, lang in (("eswiki", "es"), ("enwiki", "en")):
                wiki_title = (sitelinks.get(site) or {}).get("title")
                if not wiki_title:
                    continue
                summary = await _fetch_wiki_rest_summary(client, lang, wiki_title)
                if summary and summary.get("type") != "disambiguation":
                    extract = _clean_text(summary.get("extract"))
                    if len(extract) >= 25:
                        return extract, lang
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            pass

    raw_titles = [t for t in dict.fromkeys((_clean_text(title), _clean_text(original_title))) if t]
    targets = {_norm_title(t) for t in raw_titles if _norm_title(t)}
    if not targets:
        return None

    year_str = str(year) if year and re.fullmatch(r"(?:19|20)\d{2}", str(year)) else ""

    for lang in ("es", "en"):
        queries = []
        if season_number is not None:
            word = "temporada" if lang == "es" else "season"
            for t in raw_titles:
                queries.append(f"{t} ({word} {season_number})")
                queries.append(f"{t} {word} {season_number}")
        else:
            kind_word = (
                ("película" if is_movie else "serie") if lang == "es"
                else ("film" if is_movie else "TV series")
            )
            for t in raw_titles:
                if year_str:
                    queries.append(f"{t} {year_str}")
                queries.append(t)
                queries.append(f"{t} {kind_word}")

        seen_pages = set()
        for q in dict.fromkeys(queries):
            try:
                resp = await client.get(
                    f"https://{lang}.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": q,
                        "srlimit": 4,
                        "format": "json",
                    },
                    headers={"User-Agent": WIKI_USER_AGENT},
                    timeout=6,
                )
                data = resp.json()
                hits = ((data.get("query") or {}).get("search") or []) if isinstance(data, dict) else []
            except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                continue

            for hit in hits:
                hit_title = hit.get("title") if isinstance(hit, dict) else None
                if not hit_title or hit_title in seen_pages:
                    continue
                seen_pages.add(hit_title)

                if season_number is not None:
                    norm_hit = _norm_title(hit_title)
                    has_num = any(
                        token in norm_hit
                        for token in (f"temporada {season_number}", f"season {season_number}", f"series {season_number}")
                    )
                    base_without_season = re.sub(
                        r"\s*\([^)]*(?:temporada|season|series)[^)]*\)\s*$", "", hit_title, flags=re.I
                    )
                    if not has_num or not _wiki_title_matches(base_without_season, targets):
                        continue
                else:
                    if not _wiki_title_matches(hit_title, targets):
                        continue

                summary = await _fetch_wiki_rest_summary(client, lang, hit_title)
                if not summary or summary.get("type") == "disambiguation":
                    continue
                extract = _clean_text(summary.get("extract"))
                if len(extract) < 25:
                    continue

                if season_number is None:
                    combined = f"{summary.get('description') or ''} {extract}".casefold()
                    hints = _MOVIE_WIKI_HINTS if is_movie else _TV_WIKI_HINTS
                    if not any(h in combined for h in hints):
                        continue
                    if year_str:
                        title_years = re.findall(r"\b((?:19|20)\d{2})\b", hit_title)
                        if title_years and year_str not in title_years:
                            continue
                        desc_years = re.findall(r"\b((?:19|20)\d{2})\b", str(summary.get("description") or ""))
                        if desc_years and year_str not in desc_years and all(
                            abs(int(y) - int(year_str)) > 2 for y in desc_years
                        ):
                            continue
                        release_match = re.search(
                            r"(?:película|film|serie|telenovela|miniserie|programa|series|movie|soap opera)"
                            r"[^.]{0,30}\b((?:19|20)\d{2})\b",
                            extract[:240],
                            re.I,
                        )
                        if release_match:
                            found_year = int(release_match.group(1))
                            if abs(found_year - int(year_str)) > 2:
                                continue

                return extract, lang

    return None


@TTLCache(ttl_seconds=300, cache_if=lambda result: bool(result[1]))
async def search_tvmaze(query: str):
    """Buscar en TVmaze API"""
    try:
        async with shared_client() as client:
            url = "https://api.tvmaze.com/search/shows"
            response = await client.get(url, params={"q": query}, timeout=10)
            response.raise_for_status()
            data = response.json()

        if not data:
            return None, None

        show = data[0]['show']
        title = show.get('name', 'Sin título')
        summary = _clean_html_text(show.get('summary', ''))
        if summary:
            summary = await ensure_spanish(summary, source_lang='en')
        image_url = show.get('image',
                             {}).get('original') if show.get('image') else None
        premiered = show.get('premiered', '')
        rating = show.get('rating', {}).get('average', 'N/D')
        genres = translate_genres(show.get('genres', []))

        caption = f"📺✨ <b>{esc(title)} ({esc(premiered[:4]) if premiered else 'N/D'})</b> ✨📺\n"
        caption += f"{SEP}\n"
        for label, value in identity_fields(dict(show, __type='tv'), title):
            caption += f"<b>{esc(label)}:</b> {esc(value)}\n"
        if summary:
            caption += f"📝 <b>Sinopsis:</b>\n{esc(get_synopsis_with_emojis(summary))}\n\n{SEP_SOFT}\n"
        if genres:
            caption += f"🎞️ <b>Géneros:</b> {esc(', '.join(genres))} {get_genre_emojis(genres)}\n"
        if rating != 'N/D':
            caption += f"⭐️ <b>Calificación:</b> {esc(rating)}/10\n"
        if premiered:
            caption += f"📅 <b>Estreno:</b> {esc(premiered)}\n"

        caption += f"\n{SEP_STAR}\n{get_dynamic_closing()}{FIRME}"

        return image_url, caption

    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, IndexError) as e:
        raise ProviderError("TVmaze no disponible") from e


@TTLCache(ttl_seconds=300, cache_if=lambda result: bool(result[1]))
async def search_omdb(query: str):
    """Buscar en OMDb API (necesita API key)"""
    if not OMDB_API_KEY:
        logger.warning("OMDB_API_KEY no está configurada.")
        return None, None
    try:
        async with shared_client() as client:
            url = "https://www.omdbapi.com/"
            response = await client.get(
                url, params={"t": query, "apikey": OMDB_API_KEY}, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('Response') == 'False':
                return None, None

            title = data.get('Title', 'Sin título')
            year = data.get('Year', 'N/D')
            plot = _clean_text(data.get('Plot', ''))
            if plot:
                plot = await ensure_spanish(plot, source_lang='en')
            else:
                wiki_res = await _fetch_wikipedia_overview(
                    client,
                    title=title,
                    year=str(year)[:4] if year and year != 'N/D' else None,
                    is_movie=data.get('Type') != 'series',
                )
                if wiki_res:
                    plot = await ensure_spanish(wiki_res[0], source_lang=wiki_res[1])

        poster_url = data.get('Poster') if data.get(
            'Poster') != 'N/A' else None
        rating = data.get('imdbRating', 'N/D')
        genre_raw = data.get('Genre', '')
        genres = (translate_genres([g.strip() for g in genre_raw.split(',') if g.strip()])
                  if genre_raw and genre_raw != 'N/A' else [])
        runtime = data.get('Runtime', '')
        director = data.get('Director', '')
        actors = data.get('Actors', '')

        caption_parts = [f"🎬🍿 <b>{esc(title)} ({esc(year)})</b> 🍿🎬", SEP]
        country = country_text([name.strip() for name in data.get('Country', '').split(',')])
        if country:
            caption_parts.append(f"🌍 <b>País:</b> {esc(country)}")
        if data.get('Type') in ('movie', 'series'):
            for label, value in identity_fields({'__type': 'movie' if data['Type'] == 'movie' else 'tv'}, title):
                caption_parts.append(f"<b>{esc(label)}:</b> {esc(value)}")
        if plot:
            caption_parts.append(
                f"📝 <b>Sinopsis:</b>\n{esc(get_synopsis_with_emojis(plot))}\n\n{SEP_SOFT}")
        if runtime and runtime != 'N/A':
            caption_parts.append(f"⏱️ <b>Duración:</b> {esc(runtime)}")
        if director and director != 'N/A':
            caption_parts.append(f"🎬 <b>Director:</b> {esc(director)}")
        if actors and actors != 'N/A':
            caption_parts.append(f"🎭 <b>Reparto:</b> {esc(actors)}")
        if genres:
            caption_parts.append(f"🎞️ <b>Géneros:</b> {esc(', '.join(genres))} {get_genre_emojis(genres)}")
        if rating and rating != 'N/A':
            caption_parts.append(f"⭐️ <b>Calificación IMDb:</b> {esc(rating)}/10")

        caption_parts.append(f"\n{SEP_STAR}\n{get_dynamic_closing()}{FIRME}")
        caption = '\n'.join(caption_parts)

        return poster_url, caption

    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, IndexError) as e:
        raise ProviderError("OMDb no disponible") from e


async def search_tmdb_and_show_options(update: Update,
                                       context: ContextTypes.DEFAULT_TYPE,
                                       query: str):
    try:
        results = [dict(item, is_movie=item['__type'] == 'movie')
                   for item in await search_catalog(query)]

        if not results:
            return False

        if len(results) == 1:
            item = results[0]
            await publish_tmdb_item(update, context, item, item['is_movie'])
            return True

        # Mostrar opciones
        context.user_data['matches'] = results
        await send_options(update.message, results,
                           'Se encontraron varias coincidencias. Responde con el número de la opción que deseas publicar:')
        return True

    except (httpx.HTTPError, ValueError) as e:
        raise ProviderError("TMDb no disponible") from e


async def _resolve_work_overview(
    client,
    details: dict,
    details_url: str,
    *,
    title: str,
    original_title: str,
    release_year: str,
    is_movie: bool,
) -> str:
    overview = _clean_text(details.get("overview"))
    if overview:
        return await ensure_spanish(overview, source_lang="es")

    orig_lang = details.get("original_language")
    picked = _pick_tmdb_translation(
        details.get("translations"), field="overview", original_language=orig_lang
    )
    if picked:
        return await ensure_spanish(picked[0], source_lang=picked[1])

    if "translations" not in details:
        try:
            fallback_params = {
                "api_key": TMDB_API_KEY,
                "language": "en-US",
                "append_to_response": "credits,videos",
            }
            r2 = await client.get(details_url, params=fallback_params, timeout=10)
            fallback_details = r2.json()
            if isinstance(fallback_details, dict):
                if not _clean_text(details.get("tagline")) and _clean_text(fallback_details.get("tagline")):
                    details["tagline"] = await ensure_spanish(
                        fallback_details["tagline"], source_lang="en"
                    )
                en_overview = _clean_text(fallback_details.get("overview"))
                if en_overview:
                    return await ensure_spanish(en_overview, source_lang="en")
        except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, IndexError) as e:
            logger.warning("No se pudo obtener fallback en inglés de TMDb: %s", e)

    external_ids = details.get("external_ids") if isinstance(details.get("external_ids"), dict) else {}
    imdb_id = details.get("imdb_id") or external_ids.get("imdb_id")
    tvdb_id = external_ids.get("tvdb_id")
    wikidata_id = external_ids.get("wikidata_id")

    omdb_plot = await _fetch_omdb_plot(
        client,
        imdb_id=imdb_id,
        title=title,
        original_title=original_title,
        year=release_year,
        is_movie=is_movie,
    )
    if omdb_plot:
        return await ensure_spanish(omdb_plot, source_lang="en")

    if not is_movie:
        tvmaze_plot = await _fetch_tvmaze_overview(
            client,
            imdb_id=imdb_id,
            tvdb_id=tvdb_id,
            title=title,
            original_title=original_title,
            year=release_year,
        )
        if tvmaze_plot:
            return await ensure_spanish(tvmaze_plot, source_lang="en")

    wiki_res = await _fetch_wikipedia_overview(
        client,
        wikidata_id=wikidata_id,
        title=title,
        original_title=original_title,
        year=release_year,
        is_movie=is_movie,
    )
    if wiki_res:
        return await ensure_spanish(wiki_res[0], source_lang=wiki_res[1])

    return ""


async def publish_tmdb_item(update: Update,
                            context,
                            item,
                            is_movie,
                            year=None, *, requested_year=None, season_number=None):
    overview_note = None
    async with shared_client() as client:
        if is_movie:
            title = item.get('title', 'Sin título')
            id_ = item['id']
            details_url = f'https://api.themoviedb.org/3/movie/{id_}'
        else:
            title = item.get('name', 'Sin título')
            id_ = item['id']
            details_url = f'https://api.themoviedb.org/3/tv/{id_}'

        details_params = {
            "api_key": TMDB_API_KEY,
            "language": "es-ES",
            "append_to_response": "credits,videos,translations,external_ids",
        }
        r = await client.get(details_url, params=details_params, timeout=10)
        details = r.json()
        title = (details.get('title') if is_movie else details.get('name')) or title

        original_title = (
            details.get("original_title")
            or details.get("original_name")
            or item.get("original_title")
            or item.get("original_name")
            or ""
        )
        release_year = (
            details.get("release_date")
            or details.get("first_air_date")
            or item.get("release_date")
            or item.get("first_air_date")
            or ""
        )[:4]

        seasons = aired_seasons(details.get('seasons')) if not is_movie else []
        selected = None
        season_fetch_failed = False
        if seasons:
            candidates = [season for season in seasons
                          if not requested_year or season['air_date'][:4] == str(requested_year)]
            if season_number is not None:
                candidates = [season for season in seasons if season['season_number'] == season_number]
            if candidates:
                selected = dict(candidates[0])
                try:
                    season_response = await client.get(
                        f"{details_url}/season/{selected['season_number']}",
                        params={"api_key": TMDB_API_KEY, "language": "es-ES",
                                "append_to_response": "credits,translations"}, timeout=10)
                    season_data = season_response.json()
                    if isinstance(season_data, dict):
                        # El resumen aporta número/fecha y sirve si falta algún dato.
                        selected.update({k: v for k, v in season_data.items()
                                         if k in ('name', 'overview', 'poster_path', 'credits', 'episode_count', 'translations')
                                         and v not in (None, '', [], {})})
                except (httpx.HTTPError, ValueError, TypeError) as e:
                    season_fetch_failed = True
                    logger.warning("No se pudieron obtener los detalles de la temporada: %s", e)

        if selected:
            overview = _clean_text(selected.get('overview'))
            if overview:
                overview = await ensure_spanish(overview, source_lang='es')
            elif not season_fetch_failed:
                picked_season = _pick_tmdb_translation(
                    selected.get('translations'),
                    field='overview',
                    original_language=details.get('original_language'),
                )
                if picked_season:
                    overview = await ensure_spanish(picked_season[0], source_lang=picked_season[1])
                elif 'translations' not in selected:
                    try:
                        s_en_resp = await client.get(
                            f"{details_url}/season/{selected['season_number']}",
                            params={"api_key": TMDB_API_KEY, "language": "en-US"},
                            timeout=10,
                        )
                        s_en = s_en_resp.json()
                        if isinstance(s_en, dict):
                            en_ov = _clean_text(s_en.get('overview'))
                            if en_ov:
                                overview = await ensure_spanish(en_ov, source_lang='en')
                    except (httpx.HTTPError, ValueError, TypeError) as e:
                        logger.warning("No se pudo obtener temporada en inglés de TMDb: %s", e)

                if not overview:
                    external_ids = details.get("external_ids") if isinstance(details.get("external_ids"), dict) else {}
                    tvmaze_season = await _fetch_tvmaze_overview(
                        client,
                        imdb_id=details.get("imdb_id") or external_ids.get("imdb_id"),
                        tvdb_id=external_ids.get("tvdb_id"),
                        title=title,
                        original_title=original_title,
                        year=release_year,
                        season_number=selected['season_number'],
                    )
                    if tvmaze_season:
                        overview = await ensure_spanish(tvmaze_season, source_lang='en')

                if not overview:
                    wiki_season = await _fetch_wikipedia_overview(
                        client,
                        title=title,
                        original_title=original_title,
                        year=release_year,
                        is_movie=False,
                        season_number=selected['season_number'],
                    )
                    if wiki_season:
                        overview = await ensure_spanish(wiki_season[0], source_lang=wiki_season[1])

                if not overview:
                    work_overview = await _resolve_work_overview(
                        client,
                        details,
                        details_url,
                        title=title,
                        original_title=original_title,
                        release_year=release_year,
                        is_movie=False,
                    )
                    if work_overview:
                        overview = work_overview
                        is_single = (
                            details.get('number_of_seasons') == 1
                            or (details.get('number_of_seasons') is None and len(seasons) == 1)
                        )
                        if not is_single:
                            overview_note = "Descripción general de la serie (esta temporada no tiene sinopsis propia):"

            if selected.get('name'):
                season_name = selected['name']
                es_season_name = _pick_tmdb_spanish_name(selected.get('translations'))
                if es_season_name and (
                    re.fullmatch(r'(?:Season|Series)\s+\d+', season_name.strip(), re.I)
                    or needs_translation(season_name, source_lang=None)
                ):
                    season_name = es_season_name
                season_name = normalize_season_name(season_name)
                if needs_translation(season_name, source_lang=None):
                    season_name = await ensure_spanish(season_name)
                selected['name'] = season_name
        else:
            overview = await _resolve_work_overview(
                client,
                details,
                details_url,
                title=title,
                original_title=original_title,
                release_year=release_year,
                is_movie=is_movie,
            )

            tagline = _clean_text(details.get('tagline'))
            if tagline:
                details['tagline'] = await ensure_spanish(tagline, source_lang='es')
            else:
                picked_tag = _pick_tmdb_translation(
                    details.get('translations'),
                    field='tagline',
                    original_language=details.get('original_language'),
                )
                if picked_tag:
                    details['tagline'] = await ensure_spanish(picked_tag[0], source_lang=picked_tag[1])

    poster_url, caption = render_tmdb_caption(
        title,
        dict(item, **details),
        is_movie,
        overview,
        season=selected,
        overview_note=overview_note,
    )

    if poster_url:
        try:
            await update.message.reply_photo(photo=poster_url,
                                         caption=caption,
                                         parse_mode='HTML')
        except TelegramError as e:
            logger.warning(f"Error enviando foto (posiblemente caption): {e}")
            # Reintento enviando solo texto si falla la foto con caption
            await update.message.reply_text(text=caption, parse_mode='HTML')
    else:
        await update.message.reply_text(text=caption,
                                       parse_mode='HTML')
    return {'seasons': seasons, 'selected': selected['season_number'] if selected else None}


def aired_seasons(raw, today=None):
    """Solo temporadas regulares con fecha válida y ya estrenadas, más reciente primero."""
    today = today or date.today()
    result = []
    seen = set()
    for season in raw if isinstance(raw, list) else []:
        if not isinstance(season, dict):
            continue
        number, air_date = season.get('season_number'), season.get('air_date')
        if not isinstance(number, int) or isinstance(number, bool) or number <= 0 or number in seen:
            continue
        if not isinstance(air_date, str) or len(air_date) != 10:
            continue
        try:
            released = date.fromisoformat(air_date)
        except (TypeError, ValueError):
            continue
        if released <= today:
            result.append(season)
            seen.add(number)
    return sorted(result, key=lambda s: (s['air_date'], s['season_number']), reverse=True)


async def search_danfra(query: str):
    """Buscar en Danfra.com"""
    try:
        async with shared_client() as client:
            url = "https://www.danfra.com/ajax/search"
            response = await client.post(url, data={'search_text': query}, timeout=10)
            response.raise_for_status()
            data = response.json()

        if not data:
            return None, None

        # Tomamos el primer resultado
        item = data[0]
        title = item.get('nombre', 'Sin título')
        slug = item.get('slug', '')
        image_path = item.get('foto', '')
        image_url = f"https://www.danfra.com/{image_path}" if image_path else None
        page_url = f"https://www.danfra.com/serie/{slug}/" if item.get('tipo') == 'serie' else f"https://www.danfra.com/novela/{slug}/"

        caption = f"🎬✨ <b>{esc(title)}</b> ✨🎬\n"
        caption += f"🌐 <i>Fuente: Danfra</i>\n{SEP}\n"
        caption += f"🔗 <a href='{esc(page_url)}'>📺 Ver en Danfra</a>\n"
        caption += f"\n🎉 ¡No te pierdas esta emocionante historia! 🚀🍿\n{SEP_STAR}{FIRME}"

        return image_url, caption

    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, IndexError) as e:
        raise ProviderError("Danfra no disponible") from e


async def search_lamparaturca(query: str):
    """Buscar en Lamparaturca.com"""
    try:
        async with shared_client() as client:
            url = "https://lamparaturca.com/"
            response = await client.get(
                url, params={"s": query}, timeout=10)
            response.raise_for_status()
            
        soup = BeautifulSoup(response.text, 'html.parser')
        article = soup.find('article')
        
        if not article:
            return None, None

        title_tag = article.find('h2', class_='entry-title') or article.find('h1', class_='entry-title')
        if not title_tag:
            return None, None
            
        title = title_tag.get_text(strip=True)
        link = title_tag.find('a')['href'] if title_tag.find('a') else f"https://lamparaturca.com/?s={query}"
        
        img_tag = article.find('img')
        image_url = img_tag['src'] if img_tag else None

        caption = f"🎬✨ <b>{esc(title)}</b> ✨🎬\n"
        caption += f"🌐 <i>Fuente: Lámpara Turca</i>\n{SEP}\n"
        caption += f"🔗 <a href='{esc(link)}'>📺 Ver en Lámpara Turca</a>\n"
        caption += f"\n💫 ¡Una historia fascinante te espera! ✨🍿\n{SEP_STAR}{FIRME}"

        return image_url, caption

    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, IndexError) as e:
        raise ProviderError("Lámpara Turca no disponible") from e


async def _send_formatted_reply(update: Update, image_url: str | None,
                                caption: str):
    """Envía un mensaje con foto si la URL existe, de lo contrario solo texto."""
    if image_url:
        await update.message.reply_photo(photo=image_url,
                                         caption=caption,
                                         parse_mode='HTML')
    elif caption:
        await update.message.reply_text(caption, parse_mode='HTML')


@TTLCache(ttl_seconds=300)
async def search_catalog(query: str, year=None):
    """Consulta principal compartida por los manejadores; conserva el tipo."""
    async with shared_client() as client:
        params = {"api_key": TMDB_API_KEY, "query": query, "language": "es-ES"}
        movie_params, tv_params = dict(params), dict(params)
        if year:
            movie_params['year'] = year
            # El año de una serie puede referirse a una temporada posterior.
        movie, tv = await asyncio.gather(
            client.get('https://api.themoviedb.org/3/search/movie', params=movie_params),
            client.get('https://api.themoviedb.org/3/search/tv', params=tv_params),
        )
    return [dict(item, __type='movie') for item in movie.json().get('results', [])] + [
        dict(item, __type='tv') for item in tv.json().get('results', [])]
