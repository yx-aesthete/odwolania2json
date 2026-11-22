"""Wspólne ustawienia testów: bez lokalnego pliku .env (klucz API i model z niego nie wpływają na wyniki testów)."""
import pytest


@pytest.fixture(autouse=True)
def _bez_lokalnego_env(monkeypatch):
    monkeypatch.setenv("O2J_BEZ_ENV", "1")


@pytest.fixture(autouse=True)
def _wyniki_www_do_tmp(monkeypatch, tmp_path):
    """Z36: podgląd WWW zapisuje do ./output; w testach do katalogu tymczasowego, nie do repozytorium."""
    monkeypatch.setenv("WEB_OUTPUT", str(tmp_path / "output"))
    monkeypatch.setenv("WEB_AUDIT", str(tmp_path / "audit"))
