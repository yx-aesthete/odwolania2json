"""Klient modelu językowego (open-weights) za adresem zgodnym z OpenAI API. Konfiguracja z .env / zmiennych."""
from __future__ import annotations

import os


def klient_z_env():
    """Zwraca funkcję (pytanie, tekst) -> odpowiedź albo None, gdy model nie jest skonfigurowany."""
    if not os.environ.get("LLM_BASE_URL"):
        return None
    raise NotImplementedError("warstwa modelu w Z5")
