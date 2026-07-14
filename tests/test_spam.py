#!/usr/bin/env python3
"""Pruebas del sistema anti-spam."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import is_spam_message

LEGIT_MESSAGES = [
    "Matrix",
    "Avengers Endgame 2019",
    "Breaking Bad",
    "El padrino",
    "Inception",
    "Friends serie",
    "Game of Thrones temporada 1",
    "Casino",
    "Casino 1995",
    "Poker Face",
    "Registro",
    "Blade Runner 2049",
    "Ocean's Eleven",
    "El juego del calamar",
]

SPAM_MESSAGES = [
    "www.freeether.net - Click, Connect, Collect",
    "Visita jetacas.com para tu bono",
    "🎰 Casino online, bono de bienvenida, giros gratis y retiros rápidos, "
    "regístrate ahora en jetacas.com 💰🔥",
    "Casino online con bono de bienvenida, giros gratis, retiros rápidos y "
    "depósito mínimo para todos los nuevos usuarios registrados hoy",
    "GANA DINERO GRATIS AHORA MISMO HAZ CLIC AQUI PARA COBRAR TU PREMIO EN "
    "EFECTIVO INMEDIATO SIN RIESGO GARANTIZADO",
    "casino bonus promo free spins launch bonus",
]


@pytest.mark.parametrize("msg", LEGIT_MESSAGES)
def test_legitimate_not_flagged(msg):
    assert is_spam_message(msg) is False, f"Falso positivo: {msg!r}"


@pytest.mark.parametrize("msg", SPAM_MESSAGES)
def test_spam_flagged(msg):
    assert is_spam_message(msg) is True, f"Spam no detectado: {msg!r}"


def test_empty_message_not_spam():
    assert is_spam_message("") is False
    assert is_spam_message(None) is False
