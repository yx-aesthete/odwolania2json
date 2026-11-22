"""Podgląd stron PDF dla przeglądarki: obraz strony (PNG) i położenie cytatu na stronie.

Położenie bierzemy z warstwy tekstowej PDF (prostokąty znaków z PDFium). Strony ze skanu (OCR) nie mają
warstwy tekstowej, więc dla nich położenia nie ma: podgląd pokazuje samą stronę i cytat, bez błędu.
Współrzędne zwracamy jako ułamki szerokości i wysokości strony (0..1, początek w lewym górnym rogu),
żeby przeglądarka mogła je nałożyć na obraz w dowolnej skali.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path

from .pdftext import _PDFIUM

SKALA_PNG = 2.0  # 72 dpi * 2 = 144 dpi: A4 ma ok. 1190 px szerokości, ostre przy powiększeniu
_POMIJANE = re.compile(r"[\s\-‐‑‒–—­]")
MIN_DLUGOSC_CYTATU = 6  # krótsze fragmenty dają przypadkowe trafienia


@dataclass(frozen=True)
class TekstStrony:
    """Znaki strony bez białych znaków i myślników, z indeksem znaku PDFium dla każdej pozycji."""
    zwarty: str
    indeksy: tuple[int, ...]
    ramki: tuple[tuple[float, float, float, float], ...]  # (x0, y0, x1, y1) w ułamkach strony, góra = 0


def zwarty(tekst: str) -> str:
    return _POMIJANE.sub("", str(tekst)).casefold()


def liczba_stron(pdf: Path) -> int:
    import pypdfium2 as pdfium
    with _PDFIUM:
        doc = pdfium.PdfDocument(str(pdf))
        try:
            return len(doc)
        finally:
            doc.close()


def strony_bez_tekstu(pdf: Path, min_znakow: int = 50) -> list[int]:
    """Numery stron (od 1), które nie mają warstwy tekstowej: pójdą przez OCR (szacunek czasu w podglądzie)."""
    import pypdfium2 as pdfium
    wynik = []
    with _PDFIUM:
        doc = pdfium.PdfDocument(str(pdf))
        try:
            for i in range(len(doc)):
                tp = doc[i].get_textpage()
                if len(tp.get_text_range().strip()) < min_znakow:
                    wynik.append(i + 1)
        finally:
            doc.close()
    return wynik


def obraz_strony(pdf: Path, strona: int, skala: float = SKALA_PNG) -> bytes:
    """PNG jednej strony (numer od 1). ValueError, gdy strony nie ma."""
    import pypdfium2 as pdfium
    with _PDFIUM:
        doc = pdfium.PdfDocument(str(pdf))
        try:
            if not 1 <= strona <= len(doc):
                raise ValueError(f"brak strony {strona}")
            obraz = doc[strona - 1].render(scale=skala).to_pil()
        finally:
            doc.close()
    bufor = io.BytesIO()
    obraz.save(bufor, format="PNG", optimize=True)
    return bufor.getvalue()


def tekst_stron(pdf: Path) -> list[TekstStrony]:
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw
    strony = []
    with _PDFIUM:
        doc = pdfium.PdfDocument(str(pdf))
        try:
            for i in range(len(doc)):
                strona = doc[i]
                szer, wys = strona.get_size()
                tp = strona.get_textpage()
                znaki, indeksy, ramki = [], [], []
                for k in range(tp.count_chars()):
                    z = chr(raw.FPDFText_GetUnicode(tp.raw, k) or 32)
                    if _POMIJANE.fullmatch(z):
                        continue
                    x0, y0, x1, y1 = tp.get_charbox(k)
                    for maly in z.casefold():  # casefold może dać 2 znaki (np. ß): każdy z tą samą ramką
                        znaki.append(maly)
                        indeksy.append(k)
                        ramki.append((x0 / szer, 1 - y1 / wys, x1 / szer, 1 - y0 / wys))
                strony.append(TekstStrony("".join(znaki), tuple(indeksy), tuple(ramki)))
        finally:
            doc.close()
    return strony


def _linie(ramki: list[tuple[float, float, float, float]]) -> list[list[float]]:
    """Prostokąty znaków -> jeden prostokąt na wiersz tekstu (znaki o zachodzących na siebie wysokościach)."""
    linie: list[list[float]] = []
    for x0, y0, x1, y1 in ramki:
        if x1 <= x0 or y1 <= y0:
            continue
        ost = linie[-1] if linie else None
        if ost and min(y1, ost[3]) - max(y0, ost[1]) > 0.4 * min(y1 - y0, ost[3] - ost[1]) and x0 >= ost[0] - 0.01:
            linie[-1] = [min(ost[0], x0), min(ost[1], y0), max(ost[2], x1), max(ost[3], y1)]
        else:
            linie.append([x0, y0, x1, y1])
    return [[round(v, 5) for v in linia] for linia in linie]


def _znajdz(tekst: TekstStrony, igla: str, od: int = 0, do: int | None = None) -> tuple[int, int] | None:
    if not igla:
        return None
    i = tekst.zwarty.find(igla, od, do if do is not None else len(tekst.zwarty))
    return (i, i + len(igla)) if i >= 0 else None


def _zakres_cytatu(tekst: TekstStrony, cytat: str) -> tuple[int, int] | None:
    """Cały cytat, a gdy go nie ma (cytat bywa ucięty albo ma inaczej złożone wiersze): coraz krótszy początek."""
    igla = zwarty(cytat)
    for dlugosc in (len(igla), 80, 40, 20):
        kawalek = igla[:dlugosc]
        if len(kawalek) < min(MIN_DLUGOSC_CYTATU, len(igla)):
            break
        trafienie = _znajdz(tekst, kawalek)
        if trafienie:
            return trafienie
    return None


def polozenie(tekst: TekstStrony, cytat: str | None, wartosc) -> dict | None:
    """Prostokąty cytatu i wartości na stronie albo None (brak warstwy tekstowej albo cytatu na stronie)."""
    if not tekst.zwarty or not cytat:
        return None
    zakres = _zakres_cytatu(tekst, cytat)
    if zakres is None:
        return None
    wynik = {"cytat": _linie(list(tekst.ramki[zakres[0]:zakres[1]])), "wartosc": []}
    for w in _warianty(wartosc):
        # wartość szukamy w obrębie cytatu (z zapasem, gdy cytat był ucięty); gdy w piśmie jest zapisana inaczej
        # (np. data słownie), zaznaczony zostaje sam cytat
        trafienie = _znajdz(tekst, w, zakres[0], zakres[1] + len(w) + 200)
        if trafienie:
            wynik["wartosc"] = _linie(list(tekst.ramki[trafienie[0]:trafienie[1]]))
            break
    return wynik


def _warianty(wartosc) -> list[str]:
    """Zapisy wartości, których szukamy w tekście strony: dosłownie, a kwota także jako „20000,00”."""
    if wartosc is None or isinstance(wartosc, bool) or str(wartosc) == "":
        return []
    warianty = [zwarty(wartosc)]
    if isinstance(wartosc, float):
        warianty.append(f"{wartosc:.2f}".replace(".", ","))
    data = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(wartosc))
    if data:  # data w JSON-ie jako RRRR-MM-DD, w piśmie zwykle „14 października 2026” albo „14.10.2026”
        rok, mies, dzien = data.groups()
        for d in dict.fromkeys((dzien, dzien.lstrip("0"))):
            warianty += [f"{d}{_MIESIACE[int(mies) - 1]}{rok}", f"{d}.{mies}.{rok}"]
    return warianty


_MIESIACE = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września",
             "października", "listopada", "grudnia")


def polozenia_pol(pdf: Path, pola: list[dict], strony_ocr: list[int] | tuple = ()) -> list[dict | None]:
    """Dla każdego pola audytu: {"strona", "cytat": [[x0,y0,x1,y1]...], "wartosc": [...]} albo None."""
    try:
        strony = tekst_stron(pdf)
    except Exception:  # podgląd nie może wywrócić przetwarzania: brak zaznaczeń to nie błąd
        return [None] * len(pola)
    wynik = []
    for d in pola:
        nr = d.get("strona")
        if not nr or not 1 <= nr <= len(strony) or nr in strony_ocr:
            wynik.append(None)
            continue
        miejsce = polozenie(strony[nr - 1], d.get("cytat"), d.get("wartosc"))
        if miejsce is None:  # numer strony z audytu bywa przesunięty o stopkę: sprawdź pozostałe strony
            for inny, t in enumerate(strony, start=1):
                if inny != nr and inny not in strony_ocr:
                    miejsce = polozenie(t, d.get("cytat"), d.get("wartosc"))
                    if miejsce:
                        nr = inny
                        break
        wynik.append({"strona": nr, **miejsce} if miejsce else None)
    return wynik
