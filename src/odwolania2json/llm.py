"""Adapter modelu językowego (open-weights) za adresem zgodnym z OpenAI API.

Konfiguracja: `config/model.yaml` (tryb api | lokalny | brak) + zmienne środowiskowe z `.env`.
Klucz API tylko ze zmiennych środowiskowych. Błąd sieci lub API nigdy nie przerywa przetwarzania:
po `max_bledow` błędach model milknie do końca dokumentu, a wyłącznik przebiegu (HTTP 401/403/404 albo
3 kolejne błędy bez udanej odpowiedzi) wyłącza go do końca przebiegu, także dla OCR; zostają same reguły.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import logging
import os
import random
import re
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

log = logging.getLogger("odwolania2json")

DOMYSLNA_KONFIGURACJA = Path(__file__).resolve().parents[2] / "config" / "model.yaml"
TRYBY = ("api", "lokalny", "brak")
from . import budzet  # noqa: E402  budżet czasu przebiegu wsadowego (Z32)
from .klasy import BLAD_MODELU  # noqa: E402  wybierz_klase: awaria modelu, w odróżnieniu od odpowiedzi „obcy”
BRAK = re.compile(r"^\s*(?:brak|null|none|nie\s+(?:ma|podano|wskazano)|-|—|n/?a)\s*\.?\s*$", re.I)

SYSTEM = (
    "Wyciągasz dane z polskiego dokumentu prawnego (odwołanie do KIO, pełnomocnictwo, potwierdzenie przelewu). "
    "Odpowiadasz wyłącznie wartością przepisaną dosłownie z tekstu dokumentu, bez komentarza, bez cudzysłowów "
    "i bez zmiany form wyrazów. Jeśli w tekście nie ma odpowiedzi, odpowiadasz: BRAK."
)


SYSTEM_JSON = (
    "Wyciągasz dane z polskiego dokumentu prawnego do JSON-a w podanym formacie. Imiona i nazwiska osób podajesz "
    "w mianowniku (np. „radcy prawnemu Janowi Nowakowi” -> „Jan Nowak”), bez tytułów (adw., r. pr., Pan, Pani) i bez "
    "funkcji (Prezes Zarządu). Nazwy firm i numery przepisujesz dosłownie z dokumentu. Brakujące wartości: null. "
    "Nie dodajesz osób ani firm, których nie ma w dokumencie."
)


KODY_TRWALE = (401, 403, 404)  # zły klucz, brak dostępu, zły adres albo model: ponawianie nic nie da
BLEDY_DO_WYLACZENIA = 3


@dataclass
class Wylacznik:
    """Wyłącznik modelu na cały przebieg, wspólny dla ekstrakcji i OCR: po HTTP 401/403/404 od razu,
    po `prog` kolejnych błędach bez udanej odpowiedzi pomiędzy. Jedna linia w logu, dalej same reguły."""
    prog: int = BLEDY_DO_WYLACZENIA
    powod: str = ""
    bledy_z_rzedu: int = 0

    @property
    def wylaczony(self) -> bool:
        return bool(self.powod)

    _blokada: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def sukces(self) -> None:
        with self._blokada:
            self.bledy_z_rzedu = 0

    def blad(self, exc: BaseException) -> None:
        if _to_limit_dostawcy(exc):   # Z42: 429 = „zwolnij”, nie wyłącza modelu na resztę przebiegu
            return
        with self._blokada:   # wspólny dla wszystkich wątków plików: decyzja o wyłączeniu pod blokadą
            self.bledy_z_rzedu += 1
            if self.wylaczony:
                return
            if isinstance(exc, urllib.error.HTTPError) and exc.code in KODY_TRWALE:
                powod = f"HTTP {exc.code} ({exc.reason})"
            elif self.bledy_z_rzedu >= self.prog:
                powod = f"{self.bledy_z_rzedu} kolejne błędy bez udanej odpowiedzi, ostatni: {_opis_bledu(exc)}"
            else:
                return
            self.powod = powod
        log.warning("MODEL WYŁĄCZONY: %s. Do końca przebiegu same reguły (OCR: Tesseract, jeśli jest).", powod)

    def wylacz(self, powod: str) -> None:
        with self._blokada:
            self.powod = powod
        log.warning("MODEL WYŁĄCZONY: %s. Do końca przebiegu same reguły (OCR: Tesseract, jeśli jest).", powod)


_LICZNIKI = threading.Lock()  # liczniki klienta (wywołania, błędy, dokumenty) z wielu wątków plików
_WYLACZNIK_PRZEBIEGU = Wylacznik()  # jeden na proces: klient ekstrakcji i klient OCR powstają osobno


def _opis_bledu(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:160]}"


def _tresc(dane: dict) -> str:
    """Treść odpowiedzi: napis albo lista części [{"type": "text", "text": …}] (część dostawców)."""
    tresc = dane["choices"][0]["message"].get("content") or ""
    if isinstance(tresc, list):
        tresc = "".join(str(c.get("text") or "") if isinstance(c, dict) else str(c) for c in tresc)
    return str(tresc).strip()


def _rozwin(wartosc: object) -> str:
    """${ZMIENNA} i ${ZMIENNA:-domyślna} ze środowiska."""
    def podstaw(m: re.Match) -> str:
        return os.environ.get(m.group(1)) or (m.group(2) or "")
    return re.sub(r"\$\{(\w+)(?::-([^}]*))?\}", podstaw, str(wartosc or ""))


@dataclass
class KlientLLM:
    base_url: str
    model: str
    api_key: str = field(default="", repr=False)  # klucz nigdy w logu ani wyjątku
    temperatura: float = 0.0
    timeout_s: float = 60.0
    max_bledow: int = 3
    tryb: str = "api"
    max_tokens: int = 400
    dodatkowe: dict = field(default_factory=dict)
    bledy: int = 0                 # wszystkie błędy w przebiegu (do podsumowania)
    wywolania: int = 0
    dokumenty: int = 0
    dokumenty_bez_modelu: int = 0
    proby: tuple = (1.0, 2.0, 4.0)  # odczekanie przed ponowieniem przy HTTP 429/5xx i przerwanym połączeniu
    _pamiec: dict = field(default_factory=dict)
    wylacznik: Wylacznik = field(default_factory=Wylacznik, repr=False)  # klient_z_env: wspólny na przebieg
    # stan bieżącego dokumentu per wątek (CLI przetwarza pliki równolegle, PLIKI_WATKI)
    _watek: threading.local = field(default_factory=threading.local, repr=False, compare=False)

    @property
    def bledy_dokumentu(self) -> int:
        """Błędy w bieżącym dokumencie (tego wątku): po max_bledow model milknie do końca dokumentu."""
        return getattr(self._watek, "bledy", 0)

    @bledy_dokumentu.setter
    def bledy_dokumentu(self, n: int) -> None:
        self._watek.bledy = n

    @property
    def opis(self) -> str:
        return f"{self.model} ({self.tryb}, {self.base_url})"

    @property
    def aktywny(self) -> bool:
        return (not self.wylacznik.wylaczony and self.bledy_dokumentu < self.max_bledow
                and not budzet.wyczerpany())

    def _udane(self) -> None:
        with _LICZNIKI:
            self.wywolania += 1
        self.wylacznik.sukces()

    def _blad(self, exc: BaseException, gdzie: str) -> None:
        if isinstance(exc, budzet.BudzetWyczerpany):  # koniec budżetu czasu to nie awaria dostawcy
            return
        with _LICZNIKI:
            self.bledy += 1
        self.bledy_dokumentu += 1   # per wątek (dokument tego wątku)
        log.warning("[model] błąd %d/%d w dokumencie (%s): %s", self.bledy_dokumentu, self.max_bledow, gdzie,
                    _opis_bledu(exc))
        self.wylacznik.blad(exc)
        if not self.wylacznik.wylaczony and self.bledy_dokumentu >= self.max_bledow:
            log.warning("[model] w tym dokumencie dalej same reguły")

    def nowy_dokument(self) -> None:
        """Licznik błędów jest per dokument: jeden zły dokument albo chwilowa awaria API nie wyłącza modelu na resztę."""
        if getattr(self._watek, "otwarty", False):   # poprzedni dokument tego wątku nie został zamknięty
            self.koniec_dokumentu()
        with _LICZNIKI:
            self.dokumenty += 1
        self.bledy_dokumentu = 0
        self._watek.otwarty = True

    def koniec_dokumentu(self) -> None:
        """Wołane po dokumencie (w jego wątku): czy model był do końca dostępny."""
        if not getattr(self._watek, "otwarty", False):
            return
        self._watek.otwarty = False
        if not self.aktywny:
            with _LICZNIKI:
                self.dokumenty_bez_modelu += 1

    def podsumowanie(self) -> str:
        bez = self.dokumenty_bez_modelu + (1 if getattr(self._watek, "otwarty", False) and not self.aktywny else 0)
        wyl = f" (wyłączony: {self.wylacznik.powod})" if self.wylacznik.wylaczony else ""
        return f"model {self.model}: {self.wywolania} wywołań, {self.bledy} błędów, {bez} dokumentów bez modelu{wyl}"

    def __call__(self, pytanie: str, tekst: str) -> str | None:
        if not self.aktywny or not tekst.strip():
            return None
        klucz = hashlib.sha256(f"{pytanie}\0{tekst}".encode()).hexdigest()
        if klucz in self._pamiec:
            return self._pamiec[klucz]
        bledy_przed = self.bledy
        odp = self._zapytaj(pytanie, tekst)
        if self.bledy == bledy_przed:  # pamiętamy tylko udane odpowiedzi (także „BRAK”), nie błędy połączenia
            self._pamiec[klucz] = odp
        return odp

    def zapytaj_json(self, polecenie: str, tekst: str, max_tokens: int = 1500) -> str | None:
        """Jedno pytanie o cały dokument; odpowiedź ma być obiektem JSON (arbitraż model ↔ reguły)."""
        if not self.aktywny or not tekst.strip():
            return None
        klucz = hashlib.sha256(f"json\0{polecenie}\0{tekst}".encode()).hexdigest()
        if klucz in self._pamiec:
            return self._pamiec[klucz]
        tresc = f"DOKUMENT:\n<<<\n{tekst}\n>>>\n\n{polecenie}\nOdpowiedz wyłącznie obiektem JSON."
        cialo = {
            "model": self.model, "temperature": self.temperatura, "max_tokens": max_tokens, **self.dodatkowe,
            "messages": [{"role": "system", "content": SYSTEM_JSON}, {"role": "user", "content": tresc}],
        }
        naglowki = {"Content-Type": "application/json"}
        if self.api_key:
            naglowki["Authorization"] = f"Bearer {self.api_key}"
        try:
            odp = _tresc(self._wyslij(cialo, naglowki))
        except Exception as exc:  # sieć, zerwana odpowiedź, nietypowy JSON: nigdy nie przerywa przebiegu
            self._blad(exc, "JSON dokumentu")
            return None
        self._udane()
        self._pamiec[klucz] = odp
        return odp

    def przepisz_obraz(self, obraz) -> str | None:
        """OCR: tekst strony (obraz PIL) przez model z wejściem obrazowym. Błąd = wyjątek (wtedy następny silnik)."""
        import base64
        import io
        bufor = io.BytesIO()
        if self.model.startswith(MODELE_OCR_PDF):
            # modele typowo OCR (lightonocr) na Scaleway: tylko treść typu `file` z PDF-em, bez polecenia i max_tokens
            obraz.convert("RGB").save(bufor, "PDF", resolution=150)
            plik = "data:application/pdf;base64," + base64.b64encode(bufor.getvalue()).decode()
            cialo = {"model": self.model, "temperature": 0, "messages": [{"role": "user", "content": [
                {"type": "file", "file": {"filename": "strona.pdf", "file_data": plik}}]}]}
        else:
            obraz.convert("RGB").save(bufor, "JPEG", quality=85)
            url = "data:image/jpeg;base64," + base64.b64encode(bufor.getvalue()).decode()
            cialo = {
                "model": self.model, "temperature": 0, "max_tokens": 4000, **self.dodatkowe,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": "Przepisz dosłownie cały tekst z tej strony dokumentu, zachowując podział "
                                             "na linie i polskie znaki. Bez komentarzy, bez formatowania Markdown."},
                    {"type": "image_url", "image_url": {"url": url}}]}],
            }
        naglowki = {"Content-Type": "application/json"}
        if self.api_key:
            naglowki["Authorization"] = f"Bearer {self.api_key}"
        if self.wylacznik.wylaczony:
            raise RuntimeError(f"model wyłączony ({self.wylacznik.powod})")
        try:
            tekst = _tresc(self._wyslij(cialo, naglowki))
        except budzet.BudzetWyczerpany:
            raise   # koniec budżetu albo sufitu: nie awaria dostawcy, nie liczy się do wyłącznika
        except Exception as exc:
            with _LICZNIKI:
                self.bledy += 1
            self.wylacznik.blad(exc)
            raise
        self._udane()
        return bez_markdown(re.sub(r"^```\w*\n|\n```$", "", tekst))

    def wybierz_klase(self, tekst: str, klasy: list) -> str | None:
        """Typ dokumentu przy niskiej pewności reguł: nazwa klasy z YAML albo None (dokument obcy)."""
        opisy = "\n".join(f"- {k.nazwa}: {k.spec.get('opis', k.nazwa)}" for k in klasy)
        pytanie = ("Jakiego typu jest ten dokument? Wybierz dokładnie jedną nazwę z listy albo 'obcy', "
                   f"jeśli nie pasuje żadna (np. pismo innej strony, wyrok, ogłoszenie):\n{opisy}\n- obcy: inny dokument\n"
                   "Odpowiedz samą nazwą.")
        if not self.aktywny:
            return BLAD_MODELU
        bledy_przed = self.bledy
        odp = self(pytanie, tekst[:4000])
        if self.bledy > bledy_przed:
            return BLAD_MODELU  # awaria API to nie odpowiedź „obcy”: rozstrzygną reguły
        if not odp:
            return None
        slowo = re.sub(r"[^\wąćęłńóśźż]", "", odp.split()[0].lower()) if odp.split() else ""
        nazwy = {k.nazwa for k in klasy}
        wynik = slowo if slowo in nazwy else None
        log.info("[model] typ dokumentu przy niskiej pewności reguł: %s", wynik or "obcy")
        return wynik

    def _zapytaj(self, pytanie: str, tekst: str) -> str | None:
        # tekst dokumentu na początku: serwery z pamięcią prefiksu liczą go raz dla wielu pytań
        tresc = f"DOKUMENT:\n<<<\n{tekst}\n>>>\n\nPYTANIE: {pytanie}\nODPOWIEDŹ (dosłownie z dokumentu albo BRAK):"
        cialo = {
            "model": self.model, "temperature": self.temperatura, "max_tokens": self.max_tokens, **self.dodatkowe,
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": tresc}],
        }
        naglowki = {"Content-Type": "application/json"}
        if self.api_key:
            naglowki["Authorization"] = f"Bearer {self.api_key}"
        try:
            odpowiedz = _tresc(self._wyslij(cialo, naglowki))
        except Exception as exc:  # sieć, zerwana odpowiedź, nietypowy JSON: nigdy nie przerywa przebiegu
            self._blad(exc, "pytanie")
            return None
        self._udane()
        return oczysc_odpowiedz(odpowiedz)


    def _wyslij(self, cialo: dict, naglowki: dict) -> dict:
        """Zapytanie z ponowieniem. HTTP 429 (i 503 z Retry-After): „zwolnij”, nie awaria — czekamy tyle, ile mówi
        Retry-After, a bez niego coraz dłużej z losowym rozrzutem, łącznie do MAKS_PONOWIEN_429_S; nie liczy się do
        wyłącznika. Inne 5xx i przerwane połączenie: odczekanie wg `proby` (1, 2, 4 s), łącznie do MAKS_PONOWIEN_S."""
        poczatek, proba, proba_429, czas_429 = time.monotonic(), 0, 0, 0.0
        while True:
            budzet.sprawdz()
            try:
                return self._wyslij_raz(cialo, naglowki)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    OGRANICZNIK.zmniejsz()
                po = _retry_after(exc)
                if exc.code == 429 or (exc.code == 503 and po is not None):
                    czekaj = po if po is not None else _odczekanie_429(self.proby, proba_429)
                    if czas_429 + czekaj > MAKS_PONOWIEN_429_S:
                        raise
                    czas_429 += czekaj
                    proba_429 += 1
                    log.warning("[model] HTTP %d, ponawiam za %.1f s (limit dostawcy)", exc.code, czekaj)
                else:
                    czekaj = self._nastepna_proba(proba, poczatek)
                    if czekaj is None or exc.code < 500:
                        raise
                    proba += 1
                    log.warning("[model] HTTP %d, ponawiam za %.0f s (%d/%d)", exc.code, czekaj, proba, len(self.proby))
            except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as exc:
                czekaj = self._nastepna_proba(proba, poczatek)
                if czekaj is None:
                    raise
                proba += 1
                log.warning("[model] połączenie: %s, ponawiam za %.0f s", str(exc)[:80], czekaj)
            _spij(min(czekaj, max(0.0, budzet.pozostalo())))

    def _nastepna_proba(self, proba: int, poczatek: float) -> float | None:
        """Odczekanie przed kolejną próbą po błędzie sieci/5xx albo None (koniec prób albo łączny limit czasu)."""
        if proba >= len(self.proby):
            return None
        czekaj = self.proby[proba]
        if time.monotonic() - poczatek + czekaj > MAKS_PONOWIEN_S + self.timeout_s:
            return None
        return czekaj

    def _wyslij_raz(self, cialo: dict, naglowki: dict) -> dict:
        with OGRANICZNIK:
            opoznienie = float(os.environ.get("OPOZNIENIE_API_S") or 0)   # tylko testy: symulacja wolnego API
            if opoznienie > 0:
                time.sleep(min(opoznienie, max(0.0, budzet.pozostalo())))
            return self._wyslij_raz_bez_limitu(cialo, naglowki)

    def _wyslij_raz_bez_limitu(self, cialo: dict, naglowki: dict) -> dict:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        try:
            req = urllib.request.Request(url, data=json.dumps(cialo).encode(), headers=naglowki, method="POST")
            with urllib.request.urlopen(req, timeout=budzet.limit(self.timeout_s)) as odp:
                return json.load(odp)
        except urllib.error.HTTPError as exc:
            tresc_bledu = exc.read().decode("utf-8", "replace") if exc.fp else ""
            if exc.code != 400 or not self.dodatkowe or not any(k in tresc_bledu for k in self.dodatkowe):
                raise
            # dostawca odrzucił dodatkowy parametr (np. reasoning_effort): ponów bez niego i zapamiętaj
            odrzucone = {k for k in self.dodatkowe if k in tresc_bledu}  # tylko parametr wymieniony w błędzie
            log.warning("[model] %s odrzucił %s, ponawiam bez nich", self.model, sorted(odrzucone))
            self.dodatkowe = {k: v for k, v in self.dodatkowe.items() if k not in odrzucone}
            cialo = {k: v for k, v in cialo.items() if k not in odrzucone}
            req = urllib.request.Request(url, data=json.dumps(cialo).encode(), headers=naglowki, method="POST")
            with urllib.request.urlopen(req, timeout=budzet.limit(self.timeout_s)) as odp:
                return json.load(odp)


class Ogranicznik:
    """Wspólny limit równoczesnych zapytań do API (model i OCR razem, API_WATKI, domyślnie 8). Przy HTTP 429
    pojemność spada o połowę (najmniej 1): pliki i strony idą równolegle, ale dostawca nie jest zalewany."""

    def __init__(self, pojemnosc: int):
        self.pojemnosc = max(1, pojemnosc)
        self._zajete = 0
        self._war = threading.Condition()

    def __enter__(self) -> "Ogranicznik":
        with self._war:
            while self._zajete >= self.pojemnosc:
                self._war.wait(1.0)
            self._zajete += 1
        return self

    def __exit__(self, *_exc) -> None:
        with self._war:
            self._zajete -= 1
            self._war.notify_all()

    def zmniejsz(self) -> None:
        with self._war:
            if self.pojemnosc > 1:
                self.pojemnosc = max(1, self.pojemnosc // 2)
                log.warning("[model] HTTP 429: równoległość zapytań zmniejszona do %d", self.pojemnosc)


def _liczba_env(nazwa: str, domyslna: int) -> int:
    try:
        return max(1, int(os.environ.get(nazwa, domyslna)))
    except ValueError:
        return domyslna


OGRANICZNIK = Ogranicznik(_liczba_env("API_WATKI", 8))
MAKS_PONOWIEN_S = 15.0
MAKS_PONOWIEN_429_S = float(os.environ.get("MAKS_PONOWIEN_429_S", "60"))  # łączne czekanie na limit dostawcy (Z42)
_spij = time.sleep   # podmieniane w testach


def _retry_after(exc: urllib.error.HTTPError) -> float | None:
    """Nagłówek Retry-After w sekundach (0–60) albo None."""
    try:
        wartosc = (exc.headers or {}).get("Retry-After")
        return None if wartosc is None else max(0.0, min(60.0, float(wartosc)))
    except (TypeError, ValueError):
        return None


def _odczekanie_429(proby: tuple, nr: int) -> float:
    """Bez Retry-After: kolejne `proby` (1, 2, 4 s), dalej podwajanie (8, 16, 30 s), z losowym rozrzutem ×0,5–1,5."""
    if not proby:
        baza = 1.0
    elif nr < len(proby):
        baza = proby[nr]
    else:
        baza = proby[-1] * 2 ** (nr - len(proby) + 1)
    return min(30.0, baza) * (0.5 + random.random())


def _to_limit_dostawcy(exc: BaseException) -> bool:
    """HTTP 429 (albo 503 z Retry-After): dostawca prosi o zwolnienie — nie świadczy o awarii."""
    return isinstance(exc, urllib.error.HTTPError) and (exc.code == 429 or (exc.code == 503 and _retry_after(exc) is not None))  # łączny czas ponowień jednego zapytania (bez czasu samego zapytania)


def _parametry_modelu(konf: dict, model: str) -> dict:
    pasujace = [(k, v) for k, v in (konf.get("parametry_modeli") or {}).items() if model.startswith(str(k))]
    return dict(max(pasujace, key=lambda kv: len(str(kv[0])))[1] or {}) if pasujace else {}


MODELE_OCR_PDF = ("lightonocr",)  # modele OCR, którym stronę wysyłamy jako PDF (treść typu file)
_WIERSZ = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_KOMORKA = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)


def _tabela_html(m: re.Match) -> str:
    """Tabela HTML -> każdy wiersz w jednej linii, komórki rozdzielone dwiema spacjami."""
    wiersze = ["  ".join(k for k in (re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip()
                                     for x in _KOMORKA.findall(w)) if k) for w in _WIERSZ.findall(m.group(1))]
    return "\n" + "\n".join(w for w in wiersze if w) + "\n"


def bez_markdown(tekst: str) -> str:
    """Odpowiedź OCR jako zwykły tekst: wiersz tabeli Markdown „| Etykieta | wartość |” -> „Etykieta  wartość”,
    bez linii separatora, pogrubień i nagłówków (część modeli formatuje mimo polecenia)."""
    import html
    tekst = re.sub(r"<table[^>]*>(.*?)</table>", _tabela_html, tekst, flags=re.S | re.I)  # lightonocr: tabele HTML
    tekst = re.sub(r"<br\s*/?>", "\n", tekst, flags=re.I)
    tekst = html.unescape(re.sub(r"</?[a-z][^>]*>", "", tekst, flags=re.I))
    tekst = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", tekst)  # ![image](image_1.png)
    wynik = []
    for linia in tekst.splitlines():
        s = linia.strip()
        if re.fullmatch(r"\|?[\s:|-]*-{3,}[\s:|-]*\|?", s):
            continue
        if s.startswith("|") and s.endswith("|"):
            linia = "  ".join(k.strip() for k in s.strip("|").split("|"))
        linia = re.sub(r"^\s{0,3}#{1,6}\s+", "", linia)
        linia = re.sub(r"\*\*(.+?)\*\*", r"\1", linia)
        # kursywa i podkreślenie wokół całej frazy („*reprezentowany przez pełnomocnika:*”, „_adres do korespondencji:_”);
        # nie w środku słów ani adresów e-mail, nie wypunktowanie „* punkt” i nie linia podpisu z samych podkreśleń
        linia = re.sub(r"(?<![\w*])\*(?=\S)([^*\n]*[^*\s])\*(?![\w*])", r"\1", linia)
        linia = re.sub(r"(?<![\w_@.])_{1,2}(?=[^\s_])([^_\n]*[^_\s])_{1,2}(?![\w_@.])", r"\1", linia)
        wynik.append(linia)
    return "\n".join(wynik)


def oczysc_odpowiedz(odpowiedz: str) -> str | None:
    t = re.sub(r"<think>.*?</think>", "", odpowiedz, flags=re.S).strip()
    t = re.sub(r"^(?:odpowied[źz]\s*:\s*)", "", t, flags=re.I).strip()
    t = t.strip("`\"'„”«» \n")
    if not t or BRAK.match(t):
        return None
    return t.split("\n")[0].strip() if len(t) > 300 else t


def _dekoduj_env(surowe: bytes) -> str:
    """Tekst pliku .env niezależnie od edytora: UTF-16 z BOM albo bez (PowerShell 5.1, Notatnik „Unicode”),
    UTF-8 z BOM albo bez, w ostateczności cp1250 (ANSI w polskim Windows)."""
    if surowe[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return surowe.decode("utf-16")
    poczatek = surowe[:64]
    if b"\x00" in poczatek:  # UTF-16 bez BOM: zera przy znakach ASCII (BE: na pozycjach parzystych)
        parzyste = poczatek[0::2].count(0)
        kodowanie = "utf-16-be" if parzyste > poczatek[1::2].count(0) else "utf-16-le"
        return surowe.decode(kodowanie, errors="replace")
    try:
        return surowe.decode("utf-8-sig")
    except UnicodeDecodeError:
        return surowe.decode("cp1250", errors="replace")


def _linia_env(linia: str) -> tuple[str, str] | None:
    """KLUCZ=wartość z jednej linii .env: bez `set `/`export `, spacji wokół „=”, cudzysłowów i ` #komentarza`."""
    linia = linia.strip()
    if not linia or linia.startswith("#") or "=" not in linia:
        return None
    klucz, wartosc = linia.split("=", 1)
    klucz = re.sub(r"^(?:set|export)\s+", "", klucz.strip(), flags=re.I).strip()
    wartosc = wartosc.strip()
    if wartosc[:1] in ("'", '"') and wartosc.find(wartosc[0], 1) > 0:  # "wartość" # komentarz
        wartosc = wartosc[1:wartosc.find(wartosc[0], 1)]
    else:
        wartosc = re.sub(r"\s+#.*$", "", wartosc).strip()
    return (klucz, wartosc) if klucz else None


def wczytaj_env(sciezka: Path | None = None) -> None:
    """Zmienne z pliku `.env` w katalogu aplikacji (KLUCZ=wartość, # komentarze). Zmienne już ustawione
    w środowisku mają pierwszeństwo, puste wartości są pomijane (wtedy działa późniejsza linia z tym kluczem).
    Bez zależności, żeby działało też z run.bat / start.bat / python -m. Zły plik nie przerywa programu."""
    if sciezka is None and os.environ.get("O2J_BEZ_ENV") == "1":  # testy: bez lokalnego .env
        return
    sciezka = sciezka or DOMYSLNA_KONFIGURACJA.parents[1] / ".env"
    try:
        if not sciezka.exists():
            return
        linie = _dekoduj_env(sciezka.read_bytes()).splitlines()
    except Exception as exc:  # brak uprawnień, zły plik: zostają same reguły
        log.warning("Nie udało się odczytać %s (%s): model bez ustawień z pliku", sciezka.name, type(exc).__name__)
        return
    for linia in linie:
        para = _linia_env(linia.replace("\x00", ""))
        if para and para[1] and para[0] not in os.environ:
            try:
                os.environ[para[0]] = para[1]
            except (ValueError, OSError) as exc:  # nazwa niedozwolona w środowisku: pomijamy tę linię
                log.warning("Pominięto linię %s w %s (%s)", para[0][:40], sciezka.name, type(exc).__name__)


def klient_z_env(sciezka: Path | None = None) -> KlientLLM | None:
    """Klient wg `config/model.yaml`, `.env` i środowiska albo None (same reguły)."""
    wczytaj_env()
    sciezka = sciezka or Path(os.environ.get("MODEL_KONFIG", DOMYSLNA_KONFIGURACJA))
    konf: dict = {}
    if sciezka.exists():
        konf = yaml.safe_load(sciezka.read_text(encoding="utf-8")) or {}
    tryb = (os.environ.get("MODEL_TRYB") or konf.get("tryb") or "brak").strip().lower()
    if tryb not in TRYBY:
        log.warning("[model] nieznany tryb %r (dozwolone: %s), same reguły", tryb, ", ".join(TRYBY))
        return None
    if tryb == "brak":
        return None
    profil = konf.get(tryb, {}) or {}
    base_url, model = _rozwin(profil.get("base_url")).strip(), _rozwin(profil.get("model")).strip()
    api_key = _rozwin(profil.get("api_key")).strip()  # CR albo spacja z pliku pisanego w Windows psuje nagłówek
    if not base_url or base_url.startswith("/") or not model:
        log.warning("[model] tryb %s bez adresu albo nazwy modelu (.env: LLM_BASE_URL, LLM_MODEL), same reguły", tryb)
        return None
    if tryb == "api" and not api_key:
        log.info("[model] tryb api bez klucza (LLM_API_KEY w .env): same reguły")
        return None
    ust = konf.get("ustawienia", {}) or {}
    return KlientLLM(
        base_url=base_url, model=model, api_key=api_key, tryb=tryb,
        temperatura=float(ust.get("temperatura", 0)), timeout_s=float(ust.get("timeout_s", 60)),
        max_bledow=int(ust.get("max_bledow", 3)), max_tokens=int(ust.get("max_tokens", 400)),
        dodatkowe=_parametry_modelu(konf, model), wylacznik=_WYLACZNIK_PRZEBIEGU,
    )


def klienci_ocr(sciezka: Path | None = None) -> list[KlientLLM]:
    """Klienci do OCR stron bez tekstu: ten sam dostawca i klucz, własne modele (`ocr_model` w config/model.yaml,
    zmienna OCR_MODEL; kilka po przecinku = kolejne próby, gdy poprzedni nie zwróci tekstu). Domyślnie model ekstrakcji."""
    klient = klient_z_env(sciezka)
    if klient is None:
        return []
    sciezka = sciezka or Path(os.environ.get("MODEL_KONFIG", DOMYSLNA_KONFIGURACJA))
    konf = (yaml.safe_load(sciezka.read_text(encoding="utf-8")) or {}) if sciezka.exists() else {}
    modele = [m.strip() for m in (os.environ.get("OCR_MODEL") or _rozwin(konf.get("ocr_model")) or klient.model).split(",")
              if m.strip()]
    return [klient if m == klient.model else replace(klient, model=m, dodatkowe=_parametry_modelu(konf, m), _pamiec={},
                                                                  _watek=threading.local())
            for m in modele]


def klient_ocr(sciezka: Path | None = None) -> KlientLLM | None:
    """Pierwszy klient OCR (zgodność wstecz)."""
    klienci = klienci_ocr(sciezka)
    return klienci[0] if klienci else None
