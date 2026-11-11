"""Pruebas de traducción al español y recuperación de sinopsis faltantes."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import unquote

from bs4 import BeautifulSoup
import httpx
import pytest

from visualbot import mediaset, providers, translator, web_catalogs
from visualbot.result_labels import country_text


def _google_response(translated_text: str):
    return httpx.Response(200, json=[[[translated_text, "src", None, None, 10]], None, "en"])


def _conversation():
    message = SimpleNamespace(
        text="Test",
        from_user=SimpleNamespace(id=1),
        reply_text=AsyncMock(),
        reply_photo=AsyncMock(),
    )
    context = SimpleNamespace(
        user_data={},
        bot=SimpleNamespace(
            get_chat_member=AsyncMock(return_value=SimpleNamespace(status="member")),
            send_photo=AsyncMock(),
            send_message=AsyncMock(),
        ),
    )
    return SimpleNamespace(message=message), context


def test_needs_translation_avoids_false_positives_on_spanish():
    assert not translator.needs_translation("Un programador descubre una simulación", source_lang="es")
    assert not translator.needs_translation("Amor & aventura", source_lang="en")
    assert not translator.needs_translation("Ficha general", source_lang="es")
    assert not translator.needs_translation(
        "Protagonizada por Murat Yıldırım y Cansu Dere, cuenta la historia de un amor en Estambul."
    )
    assert not translator.needs_translation(
        "En Los Angeles, un detective investiga el misterio de una familia.", source_lang="es"
    )


def test_needs_translation_detects_english_portuguese_and_non_latin():
    assert translator.needs_translation(
        "A computer hacker learns from mysterious rebels about the true nature of his reality.",
        source_lang="es",
    )
    assert translator.needs_translation(
        "Follows a young woman who discovers a hidden secret in her family's mansion.",
        source_lang="es",
    )
    assert translator.needs_translation(
        "Uma história de amor que mudou sua vida para sempre."
    )
    assert translator.needs_translation("Это история о любви и тайне.")


def test_genre_and_season_name_helpers():
    assert translator.translate_genres(["Action", "Science-Fiction", "Action & Adventure", "Drama"]) == [
        "Acción", "Ciencia ficción", "Acción y Aventura", "Drama"
    ]
    assert translator.normalize_season_name("Season 4") == "Temporada 4"
    assert translator.normalize_season_name("Series 2") == "Temporada 2"
    assert translator.normalize_season_name("Specials") == "Especiales"
    assert translator.normalize_season_name("Miniseries") == "Miniserie"
    assert translator.normalize_season_name("Edición 3 & más") == "Edición 3 & más"


def test_country_aliases_include_english_names():
    assert country_text(["Germany", "France", "USA"]) == "🇩🇪 Alemania, 🇫🇷 Francia, 🇺🇸 Estados Unidos"
    assert country_text(["Japan", "UK"]) == "🇯🇵 Japón, 🇬🇧 Reino Unido"


async def test_ensure_spanish_uses_google_caches_and_falls_back_to_mymemory(api):
    google_down = False

    def respond(request):
        if request.url.host == "translate.googleapis.com":
            if google_down:
                return httpx.Response(503)
            return _google_response("Un hacker descubre la verdad.")
        if request.url.host == "api.mymemory.translated.net":
            return httpx.Response(200, json={
                "responseStatus": 200,
                "responseData": {"translatedText": "Traducción de respaldo en español."},
            })
        raise AssertionError(f"Host inesperado: {request.url.host}")

    requests = api(respond)
    text = "A hacker discovers the truth."
    assert await translator.ensure_spanish(text, source_lang="en") == "Un hacker descubre la verdad."
    assert await translator.ensure_spanish(text, source_lang="en") == "Un hacker descubre la verdad."
    assert len(requests) == 1

    google_down = True
    other = "Another English plot about love and war."
    assert await translator.ensure_spanish(other, source_lang="en") == "Traducción de respaldo en español."


async def test_failed_translation_is_not_cached_and_recovers(api):
    attempt = 0

    def respond(_):
        nonlocal attempt
        attempt += 1
        if attempt <= 2:
            return httpx.Response(503)
        return _google_response("Traducción recuperada.")

    api(respond)
    src = "A movie about a secret mission."
    assert await translator.ensure_spanish(src, source_lang="en") == src
    assert await translator.ensure_spanish(src, source_lang="en") == "Traducción recuperada."
    assert attempt == 3


async def test_long_text_translation_chunks_cleanly(api):
    def respond(request):
        q = request.url.params["q"]
        return _google_response(f"ES({len(q)})")

    requests = api(respond)
    long_en = " ".join(["A young hero begins a dangerous journey across the kingdom."] * 25)
    translated = await translator.ensure_spanish(long_en, source_lang="en")
    assert len(requests) >= 2
    assert translated.startswith("ES(")


async def test_tmdb_prefers_es_mx_translation_over_english(api):
    def respond(request):
        assert request.url.host == "api.themoviedb.org"
        return httpx.Response(200, json={
            "overview": "",
            "translations": {
                "translations": [
                    {"iso_639_1": "en", "iso_3166_1": "US", "data": {"overview": "English plot."}},
                    {"iso_639_1": "es", "iso_3166_1": "MX", "data": {"overview": "Una historia mexicana en español."}},
                ]
            },
        })

    requests = api(respond)
    update, context = _conversation()
    await providers.publish_tmdb_item(update, context, {"id": 10, "title": "Peli"}, True)
    caption = update.message.reply_text.call_args.kwargs["text"]
    assert "Una historia mexicana en español." in caption
    assert len(requests) == 1


async def test_tmdb_translates_misfiled_english_overview_and_english_fallback(api):
    def respond(request):
        if request.url.host == "translate.googleapis.com":
            q = request.url.params["q"]
            if "tagline" in q.lower():
                return _google_response("Nadie puede detenerlo")
            return _google_response("Una mujer descubre un secreto familiar.")
        return httpx.Response(200, json={
            "overview": "A woman discovers a family secret and must save her home.",
            "tagline": "No one can stop this tagline",
            "genres": [{"name": "Mystery"}, {"name": "Action & Adventure"}],
        })

    api(respond)
    update, context = _conversation()
    await providers.publish_tmdb_item(update, context, {"id": 11, "title": "Secret"}, True)
    caption = update.message.reply_text.call_args.kwargs["text"]
    assert "Una mujer descubre un secreto" in caption
    assert "secreto 🤫 familiar." in caption
    assert "Nadie puede detenerlo" in caption
    assert "Misterio, Acción y Aventura" in caption


async def test_tmdb_translates_foreign_original_language_translation(api):
    def respond(request):
        if request.url.host == "translate.googleapis.com":
            assert request.url.params["sl"] == "pt"
            return _google_response("Una novela brasileña sobre el destino.")
        return httpx.Response(200, json={
            "overview": "",
            "original_language": "pt",
            "translations": {
                "translations": [
                    {"iso_639_1": "pt", "iso_3166_1": "BR", "data": {
                        "overview": "Uma novela brasileira sobre o destino e a família."
                    }},
                ]
            },
        })

    api(respond)
    update, context = _conversation()
    await providers.publish_tmdb_item(update, context, {"id": 12, "name": "Novela", "seasons": []}, False)
    caption = update.message.reply_text.call_args.kwargs["text"]
    assert "Una novela brasileña sobre el destino." in caption


async def test_tmdb_tv_uses_external_ids_for_omdb_when_tmdb_lacks_overview(api, monkeypatch):
    monkeypatch.setattr(providers, "OMDB_API_KEY", "omdb-key")

    def respond(request):
        if request.url.host == "api.themoviedb.org":
            return httpx.Response(200, json={
                "overview": "",
                "seasons": [],
                "translations": {"translations": []},
                "external_ids": {"imdb_id": "tt9999999"},
            })
        if request.url.host == "www.omdbapi.com":
            assert request.url.params["i"] == "tt9999999"
            return httpx.Response(200, json={
                "Response": "True",
                "Plot": "A detective investigates a strange crime in the city.",
            })
        if request.url.host == "translate.googleapis.com":
            return _google_response("Un detective investiga un extraño crimen en la ciudad.")
        raise AssertionError(f"Unexpected host: {request.url.host}")

    api(respond)
    update, context = _conversation()
    await providers.publish_tmdb_item(update, context, {"id": 20, "name": "Serie"}, False)
    caption = update.message.reply_text.call_args.kwargs["text"]
    assert "Un detective" in caption
    assert "extraño crimen" in caption
    assert "ciudad. 🏙️" in caption


async def test_tmdb_season_translates_english_season_overview_and_name(api):
    def respond(request):
        if request.url.host == "translate.googleapis.com":
            return _google_response("La segunda temporada sigue una nueva misión.")
        if "/season/2" in request.url.path:
            return httpx.Response(200, json={
                "name": "Season 2",
                "overview": "",
                "translations": {"translations": [
                    {"iso_639_1": "en", "iso_3166_1": "US", "data": {
                        "overview": "The second season follows a new mission."
                    }},
                ]},
            })
        return httpx.Response(200, json={
            "overview": "Sinopsis general de la serie.",
            "number_of_seasons": 2,
            "seasons": [
                {"season_number": 1, "air_date": "2023-01-01"},
                {"season_number": 2, "air_date": "2024-01-01"},
            ],
        })

    api(respond)
    update, context = _conversation()
    await providers.publish_tmdb_item(update, context, {"id": 30, "name": "Misión"}, False)
    caption = update.message.reply_text.call_args.kwargs["text"]
    assert "Nombre:</b> Temporada 2" in caption
    assert "La segunda temporada sigue una nueva misión." in caption
    assert "Sinopsis general" not in caption


async def test_tmdb_season_falls_back_to_tvmaze_season_summary(api, monkeypatch):
    monkeypatch.setattr(providers, "OMDB_API_KEY", None)

    def respond(request):
        if request.url.host == "api.themoviedb.org":
            if "/season/" in request.url.path:
                return httpx.Response(200, json={"overview": "", "translations": {"translations": []}})
            return httpx.Response(200, json={
                "overview": "",
                "number_of_seasons": 2,
                "external_ids": {"imdb_id": "tt1234567"},
                "seasons": [
                    {"season_number": 1, "air_date": "2022-01-01"},
                    {"season_number": 2, "air_date": "2023-01-01"},
                ],
            })
        if request.url.host == "api.tvmaze.com":
            if request.url.path == "/lookup/shows":
                return httpx.Response(200, json={"id": 55})
            if request.url.path == "/shows/55/seasons":
                return httpx.Response(200, json=[
                    {"number": 1, "summary": "<p>Season one</p>"},
                    {"number": 2, "summary": "<p>Season two brings a secret war.</p>"},
                ])
        if request.url.host == "translate.googleapis.com":
            return _google_response("La segunda temporada trae una guerra secreta.")
        raise AssertionError(f"Unexpected: {request.url}")

    api(respond)
    update, context = _conversation()
    await providers.publish_tmdb_item(update, context, {"id": 31, "name": "Show"}, False)
    caption = update.message.reply_text.call_args.kwargs["text"]
    assert "La segunda temporada trae una guerra ⚔️ secreta." in caption


async def test_tmdb_single_season_uses_series_overview_when_season_has_none(api, monkeypatch):
    monkeypatch.setattr(providers, "OMDB_API_KEY", None)

    def respond(request):
        if request.url.host == "api.themoviedb.org":
            if "/season/" in request.url.path:
                return httpx.Response(200, json={"overview": "", "translations": {"translations": []}})
            return httpx.Response(200, json={
                "overview": "Una telenovela apasionante sobre dos familias.",
                "number_of_seasons": 1,
                "seasons": [{"season_number": 1, "air_date": "2024-01-01"}],
            })
        if request.url.host == "api.tvmaze.com":
            return httpx.Response(200, json=[])
        if request.url.host.endswith("wikipedia.org"):
            return httpx.Response(200, json={"query": {"search": []}})
        raise AssertionError(f"Unexpected: {request.url}")

    api(respond)
    update, context = _conversation()
    await providers.publish_tmdb_item(update, context, {"id": 32, "name": "La Pasión"}, False)
    caption = update.message.reply_text.call_args.kwargs["text"]
    assert "Una telenovela apasionante sobre dos familias." in caption
    assert "Sin descripción disponible" not in caption


async def test_tmdb_multi_season_labels_general_series_overview_when_season_has_none(api, monkeypatch):
    monkeypatch.setattr(providers, "OMDB_API_KEY", None)

    def respond(request):
        if request.url.host == "api.themoviedb.org":
            if "/season/" in request.url.path:
                return httpx.Response(200, json={"overview": "", "translations": {"translations": []}})
            return httpx.Response(200, json={
                "overview": "Una historia coral de amor y venganza.",
                "number_of_seasons": 2,
                "seasons": [
                    {"season_number": 1, "air_date": "2023-01-01"},
                    {"season_number": 2, "air_date": "2024-01-01"},
                ],
            })
        if request.url.host == "api.tvmaze.com":
            return httpx.Response(200, json=[])
        if request.url.host.endswith("wikipedia.org"):
            return httpx.Response(200, json={"query": {"search": []}})
        raise AssertionError(f"Unexpected: {request.url}")

    api(respond)
    update, context = _conversation()
    await providers.publish_tmdb_item(update, context, {"id": 33, "name": "Venganza"}, False)
    caption = update.message.reply_text.call_args.kwargs["text"]
    assert "Descripción general de la serie" in caption
    assert "Una historia coral de amor ❤️ y venganza. 😠" in caption
    assert "Sin descripción disponible" not in caption


async def test_tmdb_movie_falls_back_to_wikidata_and_wikipedia(api, monkeypatch):
    monkeypatch.setattr(providers, "OMDB_API_KEY", None)

    def respond(request):
        if request.url.host == "api.themoviedb.org":
            return httpx.Response(200, json={
                "overview": "",
                "translations": {"translations": []},
                "external_ids": {"wikidata_id": "Q424242"},
            })
        if request.url.host == "www.wikidata.org":
            return httpx.Response(200, json={
                "entities": {
                    "Q424242": {"sitelinks": {"eswiki": {"title": "Película de prueba"}}}
                }
            })
        if request.url.host == "es.wikipedia.org":
            assert "Pel%C3%ADcula_de_prueba" in str(request.url) or "Película_de_prueba" in unquote(str(request.url))
            return httpx.Response(200, json={
                "type": "standard",
                "extract": "Película de prueba es una película española sobre un viaje inolvidable.",
            })
        raise AssertionError(f"Unexpected: {request.url}")

    api(respond)
    update, context = _conversation()
    await providers.publish_tmdb_item(update, context, {"id": 40, "title": "Película de prueba"}, True)
    caption = update.message.reply_text.call_args.kwargs["text"]
    assert "Película de prueba es una película española" in caption


async def test_wikipedia_search_ignores_wrong_year_remake_and_picks_correct_film(api, monkeypatch):
    monkeypatch.setattr(providers, "OMDB_API_KEY", None)

    def respond(request):
        if request.url.host == "api.themoviedb.org":
            return httpx.Response(200, json={
                "overview": "",
                "release_date": "2020-01-15",
                "translations": {"translations": []},
            })
        if request.url.host == "es.wikipedia.org":
            if request.url.path == "/w/api.php":
                return httpx.Response(200, json={
                    "query": {
                        "search": [
                            {"title": "Rubí (telenovela de 2004)"},
                            {"title": "Rubí (telenovela de 2020)"},
                        ]
                    }
                })
            if "2020" in unquote(request.url.path):
                return httpx.Response(200, json={
                    "type": "standard",
                    "description": "telenovela de 2020",
                    "extract": "Rubí es una serie dramática de 2020 protagonizada por Camila Sodi.",
                })
            return httpx.Response(200, json={
                "type": "standard",
                "description": "telenovela de 2004",
                "extract": "Versión anterior de 2004.",
            })
        if request.url.host == "api.tvmaze.com":
            return httpx.Response(200, json=[])
        if request.url.host == "en.wikipedia.org":
            return httpx.Response(200, json={"query": {"search": []}})
        raise AssertionError(f"Unexpected: {request.url}")

    api(respond)
    update, context = _conversation()
    await providers.publish_tmdb_item(update, context, {"id": 41, "name": "Rubí", "seasons": []}, False)
    caption = update.message.reply_text.call_args.kwargs["text"]
    assert "Camila Sodi" in caption
    assert "Versión anterior de 2004" not in caption


async def test_tvmaze_and_omdb_translate_summaries_and_genres(api, monkeypatch):
    monkeypatch.setattr(providers, "OMDB_API_KEY", "omdb-key")

    def respond(request):
        if request.url.host == "api.tvmaze.com":
            return httpx.Response(200, json=[{
                "show": {
                    "name": "The Rookie",
                    "summary": "<p>John Nolan <i>becomes</i> the oldest rookie in the LAPD.</p>",
                    "premiered": "2018-10-16",
                    "genres": ["Crime", "Action", "Drama"],
                }
            }])
        if request.url.host == "www.omdbapi.com":
            return httpx.Response(200, json={
                "Response": "True",
                "Title": "Inception",
                "Year": "2010",
                "Type": "movie",
                "Country": "Germany, USA",
                "Plot": "A thief who steals corporate secrets through dream-sharing technology.",
                "Genre": "Action, Sci-Fi",
            })
        if request.url.host == "translate.googleapis.com":
            q = request.url.params["q"]
            if "John Nolan" in q:
                return _google_response("John Nolan se convierte en el novato mayor del LAPD.")
            return _google_response("Un ladrón que roba secretos corporativos mediante sueños.")
        raise AssertionError(f"Unexpected: {request.url}")

    api(respond)
    _, tvmaze_caption = await providers.search_tvmaze("The Rookie")
    assert "John Nolan se convierte en el novato mayor del LAPD." in tvmaze_caption
    assert "<i>" not in BeautifulSoup(tvmaze_caption, "html.parser").get_text()
    assert "Crimen, Acción, Drama" in tvmaze_caption

    _, omdb_caption = await providers.search_omdb("Inception")
    assert "Un ladrón que roba secretos 🤫 corporativos mediante sueños. 💤" in omdb_caption
    assert "Acción, Ciencia ficción" in omdb_caption
    assert "🇩🇪 Alemania, 🇺🇸 Estados Unidos" in omdb_caption


async def test_search_omdb_falls_back_to_wikipedia_when_plot_is_na(api, monkeypatch):
    monkeypatch.setattr(providers, "OMDB_API_KEY", "omdb-key")

    def respond(request):
        if request.url.host == "www.omdbapi.com":
            return httpx.Response(200, json={
                "Response": "True",
                "Title": "Cinta Cubana",
                "Year": "2019",
                "Type": "movie",
                "Plot": "N/A",
                "Genre": "Drama",
            })
        if request.url.host == "es.wikipedia.org":
            if request.url.path == "/w/api.php":
                return httpx.Response(200, json={
                    "query": {"search": [{"title": "Cinta Cubana"}]}
                })
            return httpx.Response(200, json={
                "type": "standard",
                "description": "película de 2019",
                "extract": "Cinta Cubana es una película dramática sobre dos músicos en La Habana.",
            })
        raise AssertionError(f"Unexpected: {request.url}")

    api(respond)
    _, caption = await providers.search_omdb("Cinta Cubana")
    assert "Cinta Cubana es una película dramática sobre dos músicos en La Habana." in caption


async def test_web_catalog_translates_portuguese_and_english_descriptions(api):
    def respond(request):
        assert request.url.host == "translate.googleapis.com"
        return _google_response("Una novela brasileña sobre el amor y el misterio.")

    api(respond)
    context = SimpleNamespace(bot=SimpleNamespace(send_photo=AsyncMock(), send_message=AsyncMock()))
    item = {
        "__type": "web",
        "title": "O Clone",
        "year": "2001",
        "source": "Globoplay",
        "description": "Uma novela brasileira sobre clonagem humana e uma grande história de amor.",
        "url": "https://globoplay.globo.com/o-clone/t/123/",
        "image": None,
    }
    await web_catalogs.publish_web_item(context, item)
    sent = context.bot.send_message.call_args.kwargs["text"]
    assert "Una novela brasileña sobre el amor y el misterio." in sent


def test_mediaset_reads_tvseason_and_matching_og_description():
    url = mediaset.SOURCE.url("/programas-tv/la-isla-de-las-tentaciones/")
    html_season = f'''<html><head><title>La isla de las tentaciones T11 | Mediaset Infinity</title>
    <script type="application/ld+json">{json.dumps({
        "@type": "TVSeason",
        "name": "Edición 11",
        "seasonNumber": 11,
        "description": "Nueva edición en el paraíso.",
    })}</script></head><body>
    <a href="/programas-tv/la-isla-de-las-tentaciones/temporada-11">Ver</a>
    </body></html>'''
    item = mediaset.season_metadata(html_season, url, "La isla de las tentaciones")
    assert item["description"] == "Nueva edición en el paraíso."

    html_og = '''<html><head>
    <title>La isla de las tentaciones T11 | Mediaset Infinity</title>
    <meta property="og:title" content="La isla de las tentaciones T11 | Mediaset Infinity">
    <meta property="og:description" content="Cinco parejas ponen a prueba su relación.">
    </head><body>
    <a href="/programas-tv/la-isla-de-las-tentaciones/temporada-11">Ver</a>
    </body></html>'''
    item_og = mediaset.season_metadata(html_og, url, "La isla de las tentaciones")
    assert item_og["description"] == "Cinco parejas ponen a prueba su relación."
