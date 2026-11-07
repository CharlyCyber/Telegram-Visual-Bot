"""Consultas a proveedores y publicación de sus fichas."""
import asyncio
import logging
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

logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    """Un proveedor no pudo responder correctamente."""


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
        summary = show.get('summary', '').replace('<p>', '').replace(
            '</p>', '').replace('<b>', '').replace('</b>', '')
        image_url = show.get('image',
                             {}).get('original') if show.get('image') else None
        premiered = show.get('premiered', '')
        rating = show.get('rating', {}).get('average', 'N/D')
        genres = show.get('genres', [])

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
        plot = data.get('Plot', '')
        poster_url = data.get('Poster') if data.get(
            'Poster') != 'N/A' else None
        rating = data.get('imdbRating', 'N/D')
        genre = data.get('Genre', '')
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
        if plot and plot != 'N/A':
            caption_parts.append(
                f"📝 <b>Sinopsis:</b>\n{esc(get_synopsis_with_emojis(plot))}\n\n{SEP_SOFT}")
        if runtime and runtime != 'N/A':
            caption_parts.append(f"⏱️ <b>Duración:</b> {esc(runtime)}")
        if director and director != 'N/A':
            caption_parts.append(f"🎬 <b>Director:</b> {esc(director)}")
        if actors and actors != 'N/A':
            caption_parts.append(f"🎭 <b>Reparto:</b> {esc(actors)}")
        if genre and genre != 'N/A':
            caption_parts.append(f"🎞️ <b>Géneros:</b> {esc(genre)}")
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


async def publish_tmdb_item(update: Update,
                            context,
                            item,
                            is_movie,
                            year=None):
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
            "append_to_response": "credits,videos",
        }
        r = await client.get(details_url, params=details_params, timeout=10)
        details = r.json()

        overview = details.get('overview') or ''

        # Fallback: si no hay sinopsis en español, intentar en inglés
        if not overview:
            try:
                fallback_params = {
                    "api_key": TMDB_API_KEY,
                    "language": "en-US",
                    "append_to_response": "credits,videos",
                }
                r2 = await client.get(details_url, params=fallback_params, timeout=10)
                fallback_details = r2.json()
                overview = fallback_details.get('overview') or ''
                if 'tagline' not in details or not details.get('tagline'):
                    details['tagline'] = fallback_details.get('tagline') or ''
            except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, IndexError) as e:
                logger.warning(f"No se pudo obtener fallback en inglés: {e}")

        # Fallback 2: si sigue sin sinopsis, buscar en OMDb por IMDb ID
        if not overview and OMDB_API_KEY:
            imdb_id = details.get('imdb_id')
            if imdb_id:
                try:
                    omdb_r = await client.get(
                        "https://www.omdbapi.com/",
                        params={"i": imdb_id, "apikey": OMDB_API_KEY},
                        timeout=10)
                    omdb_data = omdb_r.json()
                    if omdb_data.get('Response') == 'True':
                        plot = omdb_data.get('Plot')
                        if plot and plot != 'N/A':
                            overview = plot
                except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, IndexError) as e:
                    logger.warning(f"No se pudo obtener sinopsis de OMDb: {e}")

    poster_url, caption = render_tmdb_caption(title, dict(item, **details), is_movie, overview)

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
            tv_params['first_air_date_year'] = year
        movie, tv = await asyncio.gather(
            client.get('https://api.themoviedb.org/3/search/movie', params=movie_params),
            client.get('https://api.themoviedb.org/3/search/tv', params=tv_params),
        )
    return [dict(item, __type='movie') for item in movie.json().get('results', [])] + [
        dict(item, __type='tv') for item in tv.json().get('results', [])]
