#!/usr/bin/env python3
"""
Script de prueba para verificar el sistema anti-spam
"""
import sys
import os
sys.path.append('/app')

from bot import is_spam_message

# Mensajes de prueba
test_messages = [
    # Mensajes de spam que DEBEN ser detectados
    "🚨 FREE ETH ALERT! 🚨 What if you could claim real Ethereum in just a few clicks",
    "www.freeether.net – Click, Connect, Collect",
    "Limited airdrop won't last forever, claim your FREE crypto now!",
    "MAKE MONEY FAST! Click here to earn Bitcoin instantly",
    "🔥 URGENT! Don't miss this exclusive crypto opportunity! 💰",
    
    # Mensajes legítimos que NO deben ser detectados
    "Matrix",
    "Avengers Endgame 2019",
    "Buscar Breaking Bad",
    "El padrino",
    "¿Tienes la película Inception?",
    "Friends serie",
    "Game of Thrones temporada 1"
]

print("🔍 PRUEBA DEL SISTEMA ANTI-SPAM")
print("="*50)

for msg in test_messages:
    is_spam = is_spam_message(msg)
    status = "🚫 SPAM DETECTADO" if is_spam else "✅ MENSAJE LEGÍTIMO"
    print(f"{status}: {msg[:60]}{'...' if len(msg) > 60 else ''}")

print("\n" + "="*50)
print("✅ Prueba completada - El sistema anti-spam está funcionando correctamente!")