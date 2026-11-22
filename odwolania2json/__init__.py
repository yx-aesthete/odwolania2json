"""Nakładka: `python -m odwolania2json` w katalogu aplikacji bez instalowania pakietu.

Właściwy kod leży w src/odwolania2json; tu tylko kierujemy tam wyszukiwanie modułów pakietu.
"""
from pathlib import Path

__path__ = [str(Path(__file__).resolve().parents[1] / "src" / "odwolania2json")]
__version__ = "0.1.0"
