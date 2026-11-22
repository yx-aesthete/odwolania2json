"""Potok dla jednego pliku: tekst -> klasa -> ekstrakcja -> wynik + audyt."""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .arbitraz import Arbitraz, json_z_odpowiedzi
from .arbitraz_szeroki import ArbitrazSzeroki
from .klasy import UstawieniaKlasyfikacji, rozpoznaj, wczytaj_klasy
from . import opisowa
from .pdftext import wczytaj
from .silnik import Silnik

log = logging.getLogger("odwolania2json")


def ujednolic_biale(tekst: str) -> str:
    """Wielokrotne spacje -> jedna, puste linie usunięte, spacje na końcach linii zdjęte.
    Układ dokumentu (kolejność linii) zostaje; reguły nie zależą od liczby spacji."""
    tekst = tekst.replace("\u00a0", " ")
    tekst = re.sub(r"[ \t]{2,}", " ", tekst)
    tekst = re.sub(r"[ \t]+\n", "\n", tekst)
    return re.sub(r"\n[ \t]*\n+", "\n", tekst)


def oczysc(tekst: str, wzorce: list[str]) -> str:
    tekst = ujednolic_biale(tekst)
    for w in wzorce:
        tekst = re.sub(w, "", tekst)
    return tekst


@dataclass(frozen=True)
class WynikPliku:
    klasa: str | None
    dane: Any
    audyt: dict


def _strona(pozycja: int | None, granice: list[int]) -> int | None:
    if pozycja is None:
        return None
    return next((i + 1 for i, g in enumerate(granice) if pozycja < g), len(granice))


def katalogi_dodatkowe(konf_aplikacji: Path, z_wywolania: list[Path] | tuple = ()) -> list[Path]:
    """Katalogi klas spoza zestawu podstawowego (np. config/klasy-demo): `klasy_dodatkowe` w aplikacja.yaml
    (ścieżki względem katalogu aplikacji), zmienna KLASY_DODATKOWE (rozdzielone `os.pathsep`) i argument.
    Domyślnie pusto: ocena UZP widzi tylko config/klasy."""
    import yaml
    konf = (yaml.safe_load(konf_aplikacji.read_text(encoding="utf-8")) or {}) if konf_aplikacji.exists() else {}
    baza = konf_aplikacji.parent.parent
    sciezki = [baza / str(k) for k in konf.get("klasy_dodatkowe") or []]
    sciezki += [Path(k) for k in os.environ.get("KLASY_DODATKOWE", "").split(os.pathsep) if k.strip()]
    sciezki += [Path(k) for k in z_wywolania]
    for k in sciezki:
        if not k.is_dir():
            raise ValueError(f"brak katalogu klas dodatkowych: {k}")
    return list(dict.fromkeys(sciezki))


def siatka_modelu(konf_aplikacji: Path) -> bool:
    """Przełącznik siatki modelu (metody `llm` z `siatka: true` w YAML klas): `siatka_modelu` w aplikacja.yaml,
    domyślnie włączona; zmienna SIATKA_MODELU=0/1 nadpisuje. Wyłączona = te metody są pomijane."""
    z_env = os.environ.get("SIATKA_MODELU")
    if z_env in ("0", "1"):
        return z_env == "1"
    import yaml
    konf = (yaml.safe_load(konf_aplikacji.read_text(encoding="utf-8")) or {}) if konf_aplikacji.exists() else {}
    return bool(konf.get("siatka_modelu", True))


class Potok:
    def __init__(self, katalog_klas: Path, uzyj_llm: bool = True, dodatkowe: list[Path] | tuple = ()):
        konf_aplikacji = Path(katalog_klas).parent / "aplikacja.yaml"
        self.klasy = wczytaj_klasy([Path(katalog_klas), *katalogi_dodatkowe(konf_aplikacji, dodatkowe)])
        self.ust = UstawieniaKlasyfikacji.z_pliku(konf_aplikacji)
        self.siatka = siatka_modelu(konf_aplikacji)
        from . import router
        self.router = router.wlaczony(konf_aplikacji)
        self.llm = None
        if uzyj_llm:
            from .llm import klient_z_env
            self.llm = klient_z_env()
        log.info("Klasy: %s; model: %s", ", ".join(k.nazwa for k in self.klasy),
                 getattr(self.llm, "opis", "brak (same reguły)"))

    def przetworz_tekst(self, tekst: str, strony: tuple[str, ...] = (), uzyj_llm: bool = True) -> WynikPliku:
        llm = self.llm if uzyj_llm else None   # parametr, nie podmiana atrybutu: pliki idą równolegle
        if llm is None:
            return self._przetworz_tekst(tekst, strony, None)
        llm.nowy_dokument()
        try:
            return self._przetworz_tekst(tekst, strony, llm)
        finally:
            if hasattr(llm, "koniec_dokumentu"):
                llm.koniec_dokumentu()

    def _przetworz_tekst(self, tekst: str, strony: tuple[str, ...], llm) -> WynikPliku:
        rozp = rozpoznaj(tekst, self.klasy, self.ust,
                         wybor_modelu=llm.wybierz_klase if llm is not None else None)
        audyt: dict = {"klasyfikacja": {"punkty": rozp.punkty, "trafienia": rozp.trafienia, "pewnosc": rozp.pewnosc}}
        if rozp.klasa is None:
            audyt["klasa"] = None
            return WynikPliku(None, None, audyt)
        strony = tuple(oczysc(st, rozp.klasa.spec.get("oczysc", [])) for st in (strony or (tekst,)))
        tekst = "\n".join(strony)
        if opisowa.czy_opisowa(rozp.klasa.spec):
            wynik = opisowa.ekstrahuj(rozp.klasa.spec, tekst, llm)
        else:
            wynik = Silnik(rozp.klasa.spec, llm, siatka=self.siatka).ekstrahuj(tekst)
        if rozp.klasa.spec.get("wskazanie"):
            from .wskazanie import wskaz
            wynik.dane = wskaz(wynik.dane, tekst, rozp.klasa.spec["wskazanie"])
        if rozp.klasa.spec.get("przypisanie"):
            from .przypisanie import przypisz
            wynik.dane = przypisz(wynik.dane, tekst, rozp.klasa.spec["przypisanie"])
        szeroki = ArbitrazSzeroki(rozp.klasa.spec.get("model_szeroki") or {})
        arb = Arbitraz(rozp.klasa.spec.get("model_dokumentu") or {})
        if llm is not None and szeroki.wlaczony and not opisowa.czy_opisowa(rozp.klasa.spec):
            # wariant szeroki zastępuje model_dokumentu: dalej jedno wywołanie na dokument
            z_modelu = json_z_odpowiedzi(llm.zapytaj_json(szeroki.polecenie(), tekst[:12000]))
            if z_modelu is not None:
                wynik.dane = szeroki.scal(wynik.dane, z_modelu, tekst)
                wynik.dowody.extend(szeroki.dowody)
        elif llm is not None and arb.wlaczony and not opisowa.czy_opisowa(rozp.klasa.spec):
            z_modelu = json_z_odpowiedzi(llm.zapytaj_json(arb.polecenie(), tekst[:12000]))
            if z_modelu is not None:
                wynik.dane = arb.scal(wynik.dane, z_modelu, tekst)
                wynik.dowody.extend(arb.dowody)
        if self.router and rozp.klasa.spec.get("router_prozy") and not opisowa.czy_opisowa(rozp.klasa.spec):
            from . import router
            powody = (rozp.klasa.spec.get("slowniki") or {}).get(rozp.klasa.spec["router_prozy"].get("slownik", "powody"), [])
            wynik.dane, audyt["router"] = router.zastosuj(wynik.dane, tekst, strony, rozp.klasa.spec["router_prozy"],
                                                          powody, llm)
        granice, suma = [], 0
        for s in strony:
            suma += len(s) + 1
            granice.append(suma)
        audyt["klasa"] = rozp.klasa.nazwa
        audyt["pola"] = [
            {"pole": d.pole, "wartosc": d.wartosc, "metoda": d.metoda, "cytat": d.cytat,
             "strona": _strona(d.pozycja, granice)}
            for d in wynik.dowody
        ]
        return WynikPliku(rozp.klasa.nazwa, wynik.dane, audyt)

    def przetworz(self, pdf: Path, uzyj_llm: bool = True) -> WynikPliku:
        dok = wczytaj(pdf)
        w = self.przetworz_tekst(dok.tekst, dok.strony, uzyj_llm)
        w.audyt["plik"] = pdf.name
        w.audyt["strony"] = len(dok.strony)
        if dok.strony_ocr:
            w.audyt["strony_ocr"] = list(dok.strony_ocr)
        return w


def przetworz_bezpiecznie(potok: Potok, pdf: Path, logger: logging.Logger = log) -> WynikPliku:
    """Wyjątek na jednym pliku nie przerywa przebiegu: próba samych reguł, a gdy i to zawiedzie, dokument pusty ({})."""
    try:
        return potok.przetworz(pdf)
    except Exception:
        logger.exception("[błąd] %s: przetwarzanie nie powiodło się, próbuję samych reguł", pdf.name)
    try:
        return potok.przetworz(pdf, uzyj_llm=False)
    except Exception:
        logger.exception("[błąd] %s: same reguły też zawiodły, zapisuję pusty wynik", pdf.name)
        return WynikPliku(None, None, {"plik": pdf.name, "blad": "nie udało się przetworzyć pliku"})
