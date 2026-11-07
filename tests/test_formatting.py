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
