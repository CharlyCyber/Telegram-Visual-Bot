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
