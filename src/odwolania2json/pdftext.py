"""Tekst z PDF: warstwa tekstowa przez pypdf, OCR (Tesseract, polski) dla stron bez tekstu.

OCR włącza się sam tylko dla stron, które nie mają warstwy tekstowej (skany).
Zmienne środowiskowe:
- OCR=0           wyłącza OCR,
- OCR_LANG        języki Tesseracta (domyślnie "pol"),
- TESSDATA_PREFIX katalog z plikami *.traineddata (gdy nie ma ich w systemie),
- OCR_DPI         rozdzielczość renderowania strony (domyślnie 300).
Brak Tesseracta albo modelu językowego nie wywraca programu: strona zostaje pusta, wpis w logu.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from . import budzet

log = logging.getLogger("odwolania2json")
_PDFIUM = threading.Lock()
# model opisuje obraz zamiast go przepisać („Przesłany obraz jest całkowicie biały…”): to nie jest tekst strony
_ODPOWIEDZ_PUSTA = re.compile(r"\b(?:obraz|strona|zdj[eę]cie)\w*\b[^.\n]{0,60}\b(?:pust|bia[łl]|nie\s+zawiera)", re.I)
MIN_ZNAKOW = 50  # strona z mniejszą liczbą znaków traktowana jak skan
OCR_TIMEOUT_S = 120


class SilnikNiedostepny(RuntimeError):
    """Silnika OCR nie ma w tym uruchomieniu (brak klucza, brak Tesseracta): to nie jest błąd odczytu strony."""


@dataclass(frozen=True)
class Dokument:
    sciezka: Path
    strony: tuple[str, ...]
    strony_ocr: tuple[int, ...] = ()  # numery stron (od 1) odczytanych przez OCR

    @property
    def tekst(self) -> str:
        return "\n".join(self.strony)


def ocr_dostepny() -> bool:
    return os.environ.get("OCR", "1") != "0" and shutil.which("tesseract") is not None


def _obraz_strony(sciezka: Path, indeks: int, dpi: int):
    import pypdfium2 as pdfium  # import leniwy: potrzebny tylko dla skanów

    with _PDFIUM:  # PDFium nie jest bezpieczny wątkowo (równoległe renderowanie daje puste strony)
        pdf = pdfium.PdfDocument(str(sciezka))
        try:
            return pdf[indeks].render(scale=dpi / 72).to_pil().copy()
        finally:
            pdf.close()


def silniki_ocr() -> list[str]:
    """Kolejność silników OCR: zmienna OCR_SILNIKI („model,tesseract”) albo `ocr` w config/aplikacja.yaml."""
    z_env = os.environ.get("OCR_SILNIKI")
    if z_env:
        return [s.strip() for s in z_env.split(",") if s.strip()]
    konf = Path(__file__).resolve().parents[2] / "config" / "aplikacja.yaml"
    if konf.exists():
        import yaml
        wartosc = (yaml.safe_load(konf.read_text(encoding="utf-8")) or {}).get("ocr")
        if wartosc:
            return list(wartosc) if isinstance(wartosc, list) else [str(wartosc)]
    return ["model", "tesseract"]


@dataclass
class LicznikOCR:
    """Licznik OCR na cały przebieg (linia podsumowania): strony odczytane, błędy silników, czas."""
    strony: int = 0
    z_pamieci: int = 0
    bledy: int = 0
    czas_s: float = 0.0
    silniki: dict = field(default_factory=dict)

    def opis(self) -> str:
        skad = ", ".join(f"{k} {v}" for k, v in sorted(self.silniki.items()))
        return (f"OCR: {self.strony} stron{f' ({skad})' if skad else ''}, {self.bledy} błędów, {self.czas_s:.1f} s"
                + (f", {self.z_pamieci} z pamięci" if self.z_pamieci else ""))


LICZNIK_OCR = LicznikOCR()
_KLIENT_OCR: list = []  # leniwie tworzony klient modelu (jeden na przebieg)
# skrót obrazu strony -> tekst z modelu: ta sama strona (np. ten sam skan w dwóch sprawach) idzie do modelu raz,
# więc daje ten sam tekst w całym przebiegu (model przy temperaturze 0 i tak nie jest w pełni powtarzalny)
_PAMIEC_OCR: dict[str, str] = {}


def _ocr_modelem(sciezka: Path, indeks: int, obrot: int = 0) -> str:
    """OCR modelem z wejściem obrazowym po API (bez instalacji systemowych). Kilka modeli OCR (OCR_MODEL „a,b”):
    następny bierze stronę, gdy poprzedni nie zwróci tekstu."""
    if not _KLIENT_OCR:
        from .llm import klienci_ocr
        _KLIENT_OCR.append(klienci_ocr())
    klienci = _KLIENT_OCR[0]
    if not klienci:
        raise SilnikNiedostepny("model niedostępny (brak klucza albo tryb brak)")
    obraz, bledy = None, []
    for klient in klienci:
        if klient.wylacznik.wylaczony:  # wyłącznik przebiegu: od razu następny silnik, bez renderowania strony
            bledy.append(f"{klient.model}: wyłączony ({klient.wylacznik.powod})")
            continue
        if obraz is None:
            obraz = _obraz_strony(sciezka, indeks, int(os.environ.get("OCR_DPI_MODEL", "150")))
            if obrot:
                obraz = obraz.rotate(obrot, expand=True)
        klucz = hashlib.sha256(f"{klient.model}\0{obraz.mode}\0{obraz.size}\0".encode() + obraz.tobytes()).hexdigest()
        if klucz in _PAMIEC_OCR:
            LICZNIK_OCR.z_pamieci += 1
            return _PAMIEC_OCR[klucz]
        try:
            tekst = klient.przepisz_obraz(obraz)
        except budzet.BudzetWyczerpany:
            raise
        except Exception as exc:
            bledy.append(f"{klient.model}: {str(exc)[:80]}")
            continue
        if not tekst or len(tekst.strip()) < MIN_ZNAKOW or _ODPOWIEDZ_PUSTA.search(tekst[:200]):
            bledy.append(f"{klient.model}: brak tekstu strony")
            continue
        _PAMIEC_OCR[klucz] = tekst
        return tekst
    if all("wyłączony" in b for b in bledy):
        raise SilnikNiedostepny("; ".join(bledy))
    raise RuntimeError("; ".join(bledy) or "model nie zwrócił tekstu strony")


def _ocr_strony(sciezka: Path, indeks: int) -> str:
    """OCR Tesseractem (gdy jest w systemie albo w obrazie Dockera)."""
    if shutil.which("tesseract") is None:
        raise SilnikNiedostepny("brak programu tesseract")
    dpi = int(os.environ.get("OCR_DPI", "300"))
    jezyk = os.environ.get("OCR_LANG", "pol")
    obraz = _obraz_strony(sciezka, indeks, dpi)
    with tempfile.TemporaryDirectory(prefix="o2j-ocr-") as tmp:
        png = Path(tmp) / "strona.png"
        obraz.save(png)
        wynik = subprocess.run(
            ["tesseract", str(png), "stdout", "-l", jezyk, "--psm", "3"],
            capture_output=True, text=True, timeout=budzet.limit(OCR_TIMEOUT_S), check=False,
        )
    if wynik.returncode != 0:
        raise RuntimeError(wynik.stderr.strip()[:300])
    return wynik.stdout


# Rozbite polskie znaki w warstwie tekstowej: litera bazowa i osobny znak diakrytyczny („a˛”, „S´”, „z˙”), czasem
# w osobnej linii. Sklejamy je w jedną literę; „ł” rysowane jako „l” z kreską w ogóle nie ma znaku w tekście, więc
# stronę z rozbitymi znakami (gdy OCR jest dostępny) czytamy też z obrazu.
_DIAKRYTYKI = {"\u00b4": "\u0301", "\u02ca": "\u0301", "\u02d9": "\u0307", "\u02db": "\u0328",
               "\u0301": "\u0301", "\u0307": "\u0307", "\u0328": "\u0328"}
_ROZBITY = re.compile(r"([A-Za-z])[ \t]*\n?[ \t]*([\u00b4\u02ca\u02d9\u02db\u0301\u0307\u0328])(?:[ \t]*\n(?=\S))?")
MIN_ROZBITYCH = 3   # od tylu rozbitych znaków na stronie strona idzie do OCR


def _zloz(m: re.Match) -> str:
    zlozony = unicodedata.normalize("NFC", m.group(1) + _DIAKRYTYKI[m.group(2)])
    return zlozony if len(zlozony) == 1 else m.group(1)


def napraw_znaki(tekst: str) -> str:
    """NFKC (ligatury „ﬁ”, „ﬂ” -> „fi”, „fl”, twarde spacje) i sklejenie litery z osobnym znakiem diakrytycznym."""
    t = _ROZBITY.sub(_zloz, tekst)
    return unicodedata.normalize("NFKC", t)


def rozbite_znaki(tekst: str) -> int:
    return len(_ROZBITY.findall(tekst))


# Nagłówek pierwszej strony: tytuł pisma albo data. Skan do góry nogami model OCR „czyta” bez błędu, ale bez nagłówka
# (zaczyna od środka i zmyśla), więc brak nagłówka na stronie 1 = jedna próba po obrocie o 180°.
_NAGLOWEK = re.compile(r"(?im)^[ \t#*]*(?:pe[łl]nomocnictw|upowa[żz]nieni|odwo[łl]ani|potwierdzeni|przelew|wyci[ąa]g|"
                       r"historia\s+rachunku|bank)|\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4}|\d{4}-\d{2}-\d{2}|"
                       r"\d{1,2}\s+[a-ząćęłńóśźż]+\s+\d{4}")


def ma_naglowek(tekst: str, znakow: int = 300) -> bool:
    return bool(_NAGLOWEK.search(tekst[:znakow]))


MARGINES_OBROTU = 2.0   # o ile punktów sygnałów klas wersja obrócona musi być lepsza od prostej (Z43)
_KLASY_DO_OBROTU: list = []


def _punkty_klas(tekst: str) -> float:
    """Najwyższa suma punktów sygnałów `rozpoznanie` po klasach: miara „czy to wygląda na pismo” dla obrotu."""
    from .klasy import _punktuj, scal_rozstrzelone, strefa_tytulu, wczytaj_klasy
    if not _KLASY_DO_OBROTU:
        katalog = Path(os.environ.get("KLASY_DIR") or Path(__file__).resolve().parents[2] / "config" / "klasy")
        try:
            _KLASY_DO_OBROTU.append(wczytaj_klasy(katalog))
        except Exception:
            _KLASY_DO_OBROTU.append([])
    poczatek, tytul = scal_rozstrzelone(tekst[:10000]), strefa_tytulu(tekst, 3000)
    return max((_punktuj(k.spec["rozpoznanie"], poczatek, tytul)[0] for k in _KLASY_DO_OBROTU[0]), default=0.0)


def _zmiennosc(v: list) -> float:
    m = sum(v) / len(v)
    return (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5 / (m + 1e-9)


def tekst_pionowy(obraz) -> bool:
    """Czy linie tekstu na obrazie strony biegną pionowo (strona obrócona o 90° albo 270°). Bez modelu: profil
    tuszu w wierszach i kolumnach; przy tekście poziomym wiersze (linie i odstępy) zmieniają się dużo bardziej.
    Na 30 skanach UZP proste strony mają stosunek >= 1,28, obrócone o 90° <= 0,78."""
    from PIL import Image
    g = obraz.convert("L")
    piksele = lambda im: list(im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata())  # noqa: E731
    jasnosc = sorted(piksele(g.resize((64, 64))))[2048]
    b = g.point(lambda v: 255 if v < jasnosc - 60 else 0)
    w, h = b.size
    b = b.crop((int(w * .08), int(h * .08), int(w * .92), int(h * .92)))
    w, h = b.size
    wiersze = piksele(b.resize((1, h), Image.BOX))
    kolumny = piksele(b.resize((w, 1), Image.BOX))
    return _zmiennosc(wiersze) / (_zmiennosc(kolumny) + 1e-9) < 0.85


def _sprawdz_obrot(sciezka: Path, strony: list[str], zrobione: list[int]) -> None:
    """Po OCR strony 1 (Z43). Model czyta obrócony obraz bez błędu, ale zmyśla albo czyta „od końca” (tytuł i data
    na końcu tekstu), więc decyduje porównanie wersji, nie samo „ma nagłówek”:
    - tekst pionowy na obrazie (bez modelu) -> próby 90° i 270°; wygrywa wersja z nagłówkiem i co najmniej
      MARGINES_OBROTU punktów sygnałów klas więcej niż prosta (przy remisie zostaje prosta);
    - prosta bez nagłówka na początku (300 znaków) -> próba 180°; przyjęta, gdy obrócona ma nagłówek na początku
      i nie mniej punktów klas niż prosta (−1): zmyślony odczyt prostej strony po obrocie ma ich wyraźnie mniej.
    Wybrany obrót stosuje się też do pozostałych stron z OCR (dodatkowe zapytania tylko dla takiego dokumentu)."""
    if 1 not in zrobione or budzet.wyczerpany() or os.environ.get("OCR_OBROT", "1") == "0":
        return
    prosta = strony[0]
    try:
        pionowy = tekst_pionowy(_obraz_strony(sciezka, 0, 100))
    except Exception:
        pionowy = False
    if not pionowy and ma_naglowek(prosta, 300):
        return
    punkty_prostej = _punkty_klas(prosta)

    def odczyt(obrot: int) -> tuple[str, float] | None:
        if budzet.wyczerpany():
            return None
        try:
            tekst = _ocr_modelem(sciezka, 0, obrot)
        except Exception:
            return None
        return tekst, _punkty_klas(tekst)

    najlepszy, tekst_najlepszy, punkty_najlepsze = 0, prosta, punkty_prostej
    if pionowy:
        for obrot in (90, 270):
            w = odczyt(obrot)
            if w and ma_naglowek(w[0], 800) and w[1] >= punkty_najlepsze + MARGINES_OBROTU:
                najlepszy, tekst_najlepszy, punkty_najlepsze = obrot, w[0], w[1]
    else:
        w = odczyt(180)
        if w and ma_naglowek(w[0], 300) and w[1] >= punkty_prostej - 1:
            najlepszy, tekst_najlepszy, punkty_najlepsze = 180, w[0], w[1]
    if not najlepszy:
        return
    log.info("[ocr] %s: strona 1 czytelniejsza po obrocie o %d° (punkty klas %.0f wobec %.0f): czytam dokument "
             "obrócony", sciezka.name, najlepszy, punkty_najlepsze, punkty_prostej)
    strony[0] = tekst_najlepszy
    for nr in zrobione:
        if nr > 1 and not budzet.wyczerpany():
            try:
                strony[nr - 1] = _ocr_modelem(sciezka, nr - 1, najlepszy)
            except Exception as exc:
                log.warning("[ocr] %s s.%d: obrócona strona bez tekstu (%s)", sciezka.name, nr, str(exc)[:80])


def _uzupelnij_ocr(sciezka: Path, strony: list[str], wymuszone: tuple[int, ...] = ()) -> tuple[int, ...]:
    puste = sorted({i for i, s in enumerate(strony) if len(s.strip()) < MIN_ZNAKOW} | set(wymuszone))
    if not puste:
        return ()
    if os.environ.get("OCR", "1") == "0":
        log.warning("[ocr] %s: %d stron bez tekstu, OCR wyłączony (OCR=0)", sciezka.name, len(puste))
        return ()
    if budzet.wyczerpany():
        log.warning("[ocr] %s: %d stron bez tekstu, budżet czasu przebiegu wyczerpany: bez OCR", sciezka.name, len(puste))
        return ()
    # przebieg wsadowy: OCR stron 1–2 (README UZP: kluczowe informacje „z reguły na pierwszych trzech stronach”;
    # na 30 skanach UZP strony 3+ nie dały żadnego pola — pomiar konsultanta i nasz, Z32/Z34). WWW: wszystkie strony
    # (podgląd pokazuje każdą). OCR_MAKS_STRON nadpisuje, 0 = wszystkie.
    limit_stron = int(os.environ.get("OCR_MAKS_STRON") or (2 if budzet.aktywny() else 0))
    if limit_stron > 0 and len(puste) > limit_stron:
        pominiete = puste[limit_stron:]
        puste = puste[:limit_stron]
        log.info("[ocr] %s: OCR stron 1–%d, pominięte %d dalszych (OCR_MAKS_STRON)", sciezka.name, puste[-1] + 1,
                 len(pominiete))
    silniki = {"model": _ocr_modelem, "tesseract": _ocr_strony}
    kolejka = [s for s in silniki_ocr() if s in silniki]
    def jedna_strona(i: int) -> tuple[int, str | None, str | None, list[str], int, float]:
        bledy, prawdziwe, t0 = [], 0, time.monotonic()
        for nazwa in kolejka:  # pierwszy silnik, który da tekst; jedna zła strona nie zatrzymuje reszty
            if budzet.wyczerpany():
                bledy.append("budżet czasu wyczerpany")
                break
            try:
                return i, silniki[nazwa](sciezka, i), nazwa, bledy, prawdziwe, time.monotonic() - t0
            except Exception as exc:
                prawdziwe += not isinstance(exc, (SilnikNiedostepny, budzet.BudzetWyczerpany))
                bledy.append(f"{nazwa}: {str(exc)[:120]}")
        return i, None, None, bledy, prawdziwe, time.monotonic() - t0

    # strony równolegle (renderowanie PDFium i tak po kolei pod blokadą, wywołania API naraz): wielostronicowy
    # skan mieści się w limicie czasu zapytania WWW za tunelem; OCR_WATKI=1 wyłącza równoległość
    watki = max(1, int(os.environ.get("OCR_WATKI", "4")))
    if watki > 1 and len(puste) > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(min(watki, len(puste))) as ex:
            wyniki = list(ex.map(jedna_strona, puste))
    else:
        wyniki = [jedna_strona(i) for i in puste]
    zrobione = []
    for i, tekst, nazwa, bledy, prawdziwe, czas in wyniki:
        LICZNIK_OCR.bledy += prawdziwe
        LICZNIK_OCR.czas_s += czas
        if tekst is not None:
            strony[i] = tekst
            zrobione.append(i + 1)
            LICZNIK_OCR.strony += 1
            LICZNIK_OCR.silniki[nazwa] = LICZNIK_OCR.silniki.get(nazwa, 0) + 1
        else:
            log.warning("[ocr] %s s.%d: OCR niedostępny (%s)", sciezka.name, i + 1, '; '.join(bledy) or 'brak silników')
    if 0 not in wymuszone and any(nazwa == "model" and i == 0 for i, _t, nazwa, *_ in wyniki):
        _sprawdz_obrot(sciezka, strony, zrobione)
    return tuple(zrobione)


_SLOWO = re.compile(r"[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{2,}")
_CZESTE = re.compile(r"\b(?:i|w|z|na|do|nr|ul|dnia|oraz|przez|się|od|że|o|r)\b", re.I)


def jakosc(tekst: str) -> float:
    """Ocena tekstu strony 0..1: udział znaków w słowach z liter + obecność częstych polskich słówek.
    Śmieci z czcionek bez mapy Unicode („ÿþ”, pojedyncze znaki) dają wynik bliski 0."""
    zwarte = re.sub(r"\s+", "", tekst)
    if not zwarte:
        return 0.0
    w_slowach = sum(len(m) for m in _SLOWO.findall(tekst)) / len(zwarte)
    czeste = min(1.0, len(_CZESTE.findall(tekst)) / max(1, len(tekst) / 200))
    return 0.7 * w_slowach + 0.3 * czeste


def _strony_pdfium(sciezka: Path) -> list[str]:
    import pypdfium2 as pdfium

    with _PDFIUM:
        pdf = pdfium.PdfDocument(str(sciezka))
        try:
            wynik = []
            for strona in pdf:
                tp = strona.get_textpage()
                wynik.append(tp.get_text_range().replace("\r\n", "\n").replace("\r", "\n"))
            return wynik
        finally:
            pdf.close()


def _lepsze_strony(sciezka: Path, strony: list[str]) -> list[str]:
    """Dla stron o słabym tekście z pypdf bierze tekst z PDFium, jeśli jest lepszy."""
    slabe = [i for i, s in enumerate(strony) if jakosc(s) < 0.75]
    if not slabe:
        return strony
    try:
        alt = _strony_pdfium(sciezka)
    except Exception as exc:  # brak pdfium albo zły plik: zostaje pypdf
        log.warning("[pdf] %s: PDFium niedostępny (%s)", sciezka.name, exc)
        return strony
    wynik = list(strony)
    for i in slabe:
        if i < len(alt) and jakosc(alt[i]) > jakosc(strony[i]) + 0.05:
            wynik[i] = alt[i]
    return wynik


def wczytaj(sciezka: Path) -> Dokument:
    try:
        reader = PdfReader(str(sciezka))
        strony = [(p.extract_text() or "") for p in reader.pages]
    except Exception as exc:
        # pypdf nie otworzył pliku (np. szyfrowanie AES z pustym hasłem bez pakietu cryptography): tekst z PDFium;
        # dopiero gdy i to zawiedzie (plik uszkodzony) -> pusty dokument, decyzja wyżej
        try:
            strony = _strony_pdfium(sciezka)
            log.info("[pdf] %s: pypdf nie odczytał pliku (%s), tekst z PDFium", sciezka.name, str(exc)[:80])
        except Exception as exc2:
            log.warning("[pdf] nie da się odczytać %s: %s; PDFium: %s", sciezka, exc, exc2)
            return Dokument(sciezka=sciezka, strony=())
    strony = _lepsze_strony(sciezka, strony)
    rozbite = tuple(i for i, s in enumerate(strony) if rozbite_znaki(s) >= MIN_ROZBITYCH)
    strony = [napraw_znaki(s) for s in strony]   # zapas, gdy OCR niedostępny
    ocr = _uzupelnij_ocr(sciezka, strony, rozbite)
    strony = [napraw_znaki(s) for s in strony]
    return Dokument(sciezka=sciezka, strony=tuple(strony), strony_ocr=ocr)
