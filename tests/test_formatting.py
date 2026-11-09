#!/usr/bin/env python3
"""Pruebas de formato/escapado HTML (sin red)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import esc, get_synopsis_with_emojis


def test_esc_escapes_html_metacharacters():
    assert esc('<b>Tom & Jerry</b>') == '&lt;b&gt;Tom &amp; Jerry&lt;/b&gt;'


def test_esc_escapes_quotes_for_attributes():
    assert '"' not in esc('a"b')
    assert "'" not in esc("a'b")


def test_esc_none_returns_empty():
    assert esc(None) == ''


def test_synopsis_can_be_escaped_safely():
    raw = "Un hacker <script>alert(1)</script> & cía"
    out = esc(get_synopsis_with_emojis(raw))
    assert '<script>' not in out
    assert '&lt;script&gt;' in out


def test_synopsis_emoji_after_each_matching_word():
    out = get_synopsis_with_emojis("El asesino busca amor en el espacio")
    for word, emoji in (("asesino", "🔪"), ("amor", "❤️"), ("espacio", "🚀")):
        assert emoji in out, f"falta emoji {emoji} para {word}"
        assert out.index(word) < out.index(emoji), f"{emoji} no va tras {word}"


def test_synopsis_no_match_returns_original():
    txt = "xyzzy qwerty zzz"
    assert get_synopsis_with_emojis(txt) == txt


def test_synopsis_empty():
    assert get_synopsis_with_emojis("") == ""


def test_synopsis_emoji_count_capped():
    words = " ".join(["amor guerra espacio asesino robot fuego"] * 20)
    out = get_synopsis_with_emojis(words)
    assert out.count("❤️") <= 30


def test_long_html_keeps_tags_balanced_and_counts_emojis():
    from visualbot.formatting import fit_html, utf16_length
    from bs4 import BeautifulSoup
    from xml.etree import ElementTree
    result = fit_html('<b>😀 &amp; ' + 'amor ' * 100 + '</b><i>Final</i>', 24)
    ElementTree.fromstring('<root>' + result + '</root>')
    assert utf16_length(BeautifulSoup(result, 'html.parser').get_text()) <= 24
    assert '…' in result


def test_tmdb_caption_retains_signature_when_metadata_is_long():
    from visualbot.config import FIRME
    from visualbot.formatting import render_tmdb_caption, utf16_length
    from bs4 import BeautifulSoup
    from xml.etree import ElementTree
    poster, caption = render_tmdb_caption('Tom & Jerry 😀', {
        'poster_path': '/poster.jpg', 'tagline': 'Amor <aventura> ' * 300,
        'genres': [{'name': 'Animación'}],
    }, True, 'En un mundo de aventuras ' * 300)
    assert poster.endswith('/poster.jpg')
    assert FIRME in caption
    assert 'Tom &amp; Jerry' in caption
    assert utf16_length(BeautifulSoup(caption, 'html.parser').get_text()) <= 1024
    ElementTree.fromstring('<root>' + caption + '</root>')


def test_tmdb_long_synopsis_preserves_movie_metadata_with_poster():
    from visualbot.config import FIRME, SEP_SOFT
    from visualbot.formatting import render_tmdb_caption, utf16_length
    from bs4 import BeautifulSoup
    from xml.etree import ElementTree

    details = {
        'poster_path': '/poster.jpg', 'release_date': '2026-01-01',
        'original_title': 'Original & título', 'origin_country': ['TH'],
        'production_countries': [{'name': 'Thailand'}],
        'credits': {'cast': [{'name': 'Actor & actriz'}],
                    'crew': [{'job': 'Director', 'name': 'Director'}]},
        'genres': [{'name': 'Comedia'}], 'vote_average': 8.6, 'vote_count': 15,
    }
    _, caption = render_tmdb_caption('¡Vaya numerito!', details, True,
                                    'Un policía & su familia viven aventuras. ' * 60)
    text = BeautifulSoup(caption, 'html.parser').get_text()
    assert utf16_length(text) <= 1024
    assert 'Sinopsis:' in text and '…' in text
    for field in (SEP_SOFT, 'Reparto: Actor & actriz', 'Dirección: Director',
                  'Estreno: 2026-01-01', 'País de producción: Thailand',
                  'Calificación: 8.6/10', 'Géneros: Comedia', FIRME):
        assert field in text
    assert text.index('Sinopsis:') < text.index('Reparto:') < text.index(FIRME)
    ElementTree.fromstring('<root>' + caption + '</root>')


def test_tmdb_series_short_synopsis_and_metadata_are_not_truncated():
    from visualbot.formatting import render_tmdb_caption
    details = {
        'poster_path': '/poster.jpg', 'first_air_date': '2025-10-11',
        'number_of_seasons': 2, 'number_of_episodes': 69,
        'credits': {'cast': [{'name': 'Murat Yıldırım'}]},
        'production_countries': [{'name': 'Turkey'}],
        'vote_average': 8.6, 'vote_count': 15, 'genres': [{'name': 'Drama'}],
    }
    _, caption = render_tmdb_caption('El Secreto', details, False,
                                    'Berrak ha ocultado un secreto durante años.')
    assert 'secreto 🤫 durante años.' in caption
    assert 'Temporadas:</b> 2  •  🎞️ <b>Episodios:</b> 69' in caption
    assert 'Reparto:' in caption and 'Calificación:' in caption and 'Géneros:' in caption
    assert '…' not in caption


def test_tmdb_without_poster_uses_text_limit_and_keeps_metadata():
    from visualbot.formatting import render_tmdb_caption, utf16_length
    from bs4 import BeautifulSoup
    from xml.etree import ElementTree
    _, caption = render_tmdb_caption('Una serie', {
        'first_air_date': '2025-10-11', 'number_of_seasons': 2,
        'number_of_episodes': 69, 'genres': [{'name': 'Drama'}],
    }, False, 'Secreto & amor 😀 ' * 500)
    text = BeautifulSoup(caption, 'html.parser').get_text()
    assert utf16_length(text) <= 4096
    assert '…' in text and 'Temporadas: 2' in text and 'Géneros: Drama' in text
    ElementTree.fromstring('<root>' + caption + '</root>')
