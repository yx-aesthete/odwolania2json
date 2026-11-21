"""Tekst z PDF: warstwa tekstowa przez pypdf (OCR na wyzwalacz)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class Dokument:
    sciezka: Path
    strony: tuple[str, ...]

    @property
    def tekst(self) -> str:
        return "\n".join(self.strony)


def wczytaj(sciezka: Path) -> Dokument:
    try:
        reader = PdfReader(str(sciezka))
        strony = tuple((p.extract_text() or "") for p in reader.pages)
    except Exception as exc:  # uszkodzony PDF -> pusty dokument, decyzja wyżej
        print(f"[pdf] nie da się odczytać {sciezka}: {exc}")
        strony = ()
    return Dokument(sciezka=sciezka, strony=strony)
