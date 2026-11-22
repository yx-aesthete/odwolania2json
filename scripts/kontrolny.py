"""Zbiór kontrolny: odporność reguł na inny układ i inne sformułowania.

Dla każdej sprawy i każdego dokumentu bierze tekst z PDF, stosuje pojedyncze zaburzenie (każde osobno,
na kopii), uruchamia ekstrakcję (same reguły, bez modelu) i liczy F1 w trybie ścisłym wobec tej samej
referencji UZP (funkcje porównania z odwolania2json.eval). Zaburzenie ma zachować znaczenie: jeśli
po nim w tekście nie ma już (w żadnej formie) wartości z referencji, która była w oryginale, dokument
liczymy jako „naruszony” i bierzemy dla niego tekst oryginalny.

    PYTHONPATH=src .venv/bin/python scripts/kontrolny.py [--sprawy 1-60] [--md docs/KONTROLNY.md]
"""
from __future__ import annotations

import argparse
import difflib
import logging
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

KORZEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORZEN / "src"))

from odwolania2json import eval as ev  # noqa: E402
from odwolania2json.normalizacja import data_iso, kwota  # noqa: E402
from odwolania2json.pdftext import wczytaj  # noqa: E402
from odwolania2json.potok import Potok  # noqa: E402

MIESIACE_DOP = ("stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
                "września", "października", "listopada", "grudnia")
_MIES = "|".join(MIESIACE_DOP)
RE_DATA_NUM = re.compile(r"(?<![\d.])(\d{1,2})([.\-/])(\d{1,2})\2(\d{4})(?![\d])")
RE_DATA_ISO = re.compile(r"(?<![\d/])(\d{4})-(\d{2})-(\d{2})(?!\d)")
RE_DATA_SLOW = re.compile(rf"(?<!\d)(\d{{1,2}}) ({_MIES}) (\d{{4}})( r\.| roku)?", re.I)

# Pola bez tekstowego odpowiednika (flagi, identyfikatory słownika) nie są sprawdzane przy walidacji.
POLA_BEZ_TEKSTU = {"przez-pelnomocnika", "prowadzacy_postepowanie", "czynnosc_powod_id", "czynnosc_opis", "typ"}

# Etykiety w potwierdzeniach przelewu (obejrzane w danych treningowych).
ETYKIETY_PRZELEWU = (
    r"Zleceniodawca|Płatnik|Nadawca|Dane nadawcy|Odbiorca|Adresat przelewu|Dane odbiorcy|Beneficjent|"
    r"Rachunek [a-ząćęłńóśźż]+|Z rachunku|Na rachunek|Kwota operacji|Kwota przelewu|Kwota|Wartość|"
    r"Data [a-ząćęłńóśźż]+|Tytuł przelewu|Tytułem|Tytuł|Opis|Numer referencyjny|Nr ref\.|"
    r"Numer transakcji|Status|Waluta|Typ operacji|Kanał|Opłata/prowizja"
)
RE_ETYKIETA_LINIA = re.compile(rf"(?im)^([ \t]*)({ETYKIETY_PRZELEWU})(?=[ \t]|$)([ \t]*)([^\n]*)$")

SLOWNIE = {17: "siedemnaście złotych 00/100", 34: "trzydzieści cztery złote 00/100",
           50: "pięćdziesiąt złotych 00/100", 100: "sto złotych 00/100", 200: "dwieście złotych 00/100"}


@dataclass(frozen=True)
class Ctx:
    gold: dict
    dokument: str  # odwolanie | pelnomocnictwo | przelew


# ---------------------------------------------------------------- zaburzenia (str, Ctx) -> str

def _sub(wzorzec: str, zamiana, flagi: int = 0) -> Callable[[str, Ctx], str]:
    rx = re.compile(wzorzec, flagi)
    return lambda t, _c: rx.sub(zamiana, t)


def _poprawna(d: int, m: int) -> bool:
    return 1 <= d <= 31 and 1 <= m <= 12


def daty_slownie(t: str, _c: Ctx) -> str:
    def num(m):
        d, mi = int(m.group(1)), int(m.group(3))
        return f"{d} {MIESIACE_DOP[mi - 1]} {m.group(4)} r." if _poprawna(d, mi) else m.group(0)

    def iso(m):
        d, mi = int(m.group(3)), int(m.group(2))
        return f"{d} {MIESIACE_DOP[mi - 1]} {m.group(1)} r." if _poprawna(d, mi) else m.group(0)
    return RE_DATA_ISO.sub(iso, RE_DATA_NUM.sub(num, t))


def _slow_na(fmt: Callable[[int, int, str], str]) -> Callable[[str, Ctx], str]:
    def f(t: str, _c: Ctx) -> str:
        def slow(m):
            return fmt(int(m.group(1)), MIESIACE_DOP.index(m.group(2).lower()) + 1, m.group(3))

        def num(m):
            d, mi = int(m.group(1)), int(m.group(3))
            return fmt(d, mi, m.group(4)) if _poprawna(d, mi) else m.group(0)

        def iso(m):
            d, mi = int(m.group(3)), int(m.group(2))
            return fmt(d, mi, m.group(1)) if _poprawna(d, mi) else m.group(0)
        t = RE_DATA_SLOW.sub(slow, t)
        t = RE_DATA_ISO.sub(iso, t)
        return RE_DATA_NUM.sub(num, t)
    return f


daty_kropki = _slow_na(lambda d, m, r: f"{d:02d}.{m:02d}.{r}")
daty_iso = _slow_na(lambda d, m, r: f"{r}-{m:02d}-{d:02d}")
daty_ukosnik = _slow_na(lambda d, m, r: f"{d:02d}/{m:02d}/{r}")


def dnia_w_naglowku(t: str, _c: Ctx) -> str:
    """„Łódź, 1 kwietnia 2026” -> „Łódź, dnia 1 kwietnia 2026 r.”."""
    rx = re.compile(r"(?m)^([ \t]*[A-ZŁŚŻŹĆ][\wąćęłńóśźż]+(?:[ -][\wąćęłńóśźż]+){0,2},[ \t]*)(?!dnia)"
                    rf"(\d{{1,2}}(?:[.\-/]\d{{1,2}}[.\-/]\d{{4}}| (?:{_MIES}) \d{{4}}))(?! r\.)")
    return rx.sub(lambda m: f"{m.group(1)}dnia {m.group(2)} r.", t)


def nip_kreski(t: str, _c: Ctx) -> str:
    return re.sub(r"(NIP\W{0,3})(\d{3})(\d{3})(\d{2})(\d{2})\b", r"\1\2-\3-\4-\5", t)


def kwota_slownie(t: str, _c: Ctx) -> str:
    def f(m):
        v = kwota(m.group(1))
        s = SLOWNIE.get(int(v)) if v is not None and float(v).is_integer() else None
        return f"{m.group(0)} (słownie: {s})" if s else m.group(0)
    return re.sub(r"(\d+[,.]\d{2})[ \t]*(?:PLN|zł)", f, t)


def _pary_rachunku(t: str, fn) -> str:
    return re.sub(r"(PL)?[ \t]?(\d{2}(?:[ \t]?\d{4}){6})(?!\d)", fn, t)


def rachunek_ciag(t: str, _c: Ctx) -> str:
    return _pary_rachunku(t, lambda m: (m.group(1) or "") + re.sub(r"\s", "", m.group(2)))


def rachunek_spacje(t: str, _c: Ctx) -> str:
    def f(m):
        c = re.sub(r"\s", "", m.group(2))
        return (m.group(1) or "") + c[:2] + " " + " ".join(c[i:i + 4] for i in range(2, 26, 4))
    return _pary_rachunku(t, f)


def rachunek_bez_pl(t: str, _c: Ctx) -> str:
    return re.sub(r"\bPL[ \t]?(?=\d{2}[ \t]?\d{4})", "", t)


def zlamanie_nazwy(t: str, c: Ctx) -> str:
    """Złamanie linii w środku nazwy firmy (z referencji), jak przy zawijaniu w PDF."""
    nazwy = {v for k, v in ev.splaszcz(c.gold).items()
             if k.endswith(".nazwa") and isinstance(v, str) and len(v.split()) >= 2}
    for n in sorted(nazwy, key=len, reverse=True):
        slowa = n.split()
        pol = len(slowa) // 2
        t = t.replace(n, " ".join(slowa[:pol]) + "\n" + " ".join(slowa[pol:]))
    return t


_KONIEC_BLOKU = (r"(?m)^[ \t]*(?:O\s?D\s?W\s?O\s?Ł\s?A\s?N\s?I\s?E[ \t]*$|dotyczy|Prezes|Krajowa|Wykonawc|"
                 r"Uczestni|Przyst[eę]puj|Warto[śs][ćc]\s+zam)")


def zamiana_blokow(t: str, _c: Ctx) -> str:
    """Zamienia kolejność bloków Odwołujący / Zamawiający."""
    o = re.search(r"(?m)^[ \t]*Odwołujący[^\n]*:", t)
    z = re.search(r"(?m)^[ \t]*Zamawiający\b[^\n]*[:(]", t)
    if not o or not z:
        return t
    a, b = sorted((o, z), key=lambda m: m.start())
    koniec = re.compile(_KONIEC_BLOKU).search(t, b.end())
    if not koniec:
        return t
    pierwszy, drugi = t[a.start():b.start()], t[b.start():koniec.start()]
    if t[a.start():b.start()].strip() == "" or not drugi.endswith("\n"):
        return t
    return t[:a.start()] + drugi + pierwszy + t[koniec.start():]


def bez_naglowka_prezes(t: str, _c: Ctx) -> str:
    return re.sub(r"(?m)^[ \t]*Prezes Krajowej Izby Odwoławczej[ \t]*\n(?:[ \t]*ul\.[^\n]*\n)?(?:[ \t]*\d{2}-\d{3}[^\n]*\n)?",
                  "", t)


def _w_srodku(wstawka: str) -> Callable[[str, Ctx], str]:
    def f(t: str, _c: Ctx) -> str:
        linie = t.split("\n")
        if len(linie) < 6:
            return t
        i = len(linie) // 2
        return "\n".join(linie[:i] + [wstawka] + linie[i:])
    return f


def puste_linie(t: str, _c: Ctx) -> str:
    return t.replace("\n", "\n\n")


def podwojne_spacje(t: str, _c: Ctx) -> str:
    return t.replace(" ", "  ")


def cudzyslowy(otw: str, zam: str) -> Callable[[str, Ctx], str]:
    return lambda t, _c: re.sub(r"[„“]", otw, re.sub(r"[”]", zam, t))


def etykiety_wielkie(t: str, _c: Ctx) -> str:
    return re.sub(r"(?m)^([ \t]*)(Odwołujący|Zamawiający|dotyczy|reprezentowan\w+ przez)(?=[ \t]*[:(])",
                  lambda m: m.group(1) + m.group(2).upper(), t)


# --- przelew: układ etykiet

def _etykiety(fn) -> Callable[[str, Ctx], str]:
    return lambda t, c: RE_ETYKIETA_LINIA.sub(fn, t) if c.dokument == "przelew" else t


def _dwukropek(m):
    if m.group(4).startswith((":", ".")):
        return m.group(0)
    return f"{m.group(1)}{m.group(2)}:{' ' + m.group(4) if m.group(4) else ''}"


def _wartosc_pod(m):
    if not m.group(4) or m.group(4).startswith((":", ".")):
        return m.group(0)
    return f"{m.group(1)}{m.group(2)}\n{m.group(4)}"


def przelew_wartosc_obok(t: str, c: Ctx) -> str:
    """„Kwota operacji\\n200,00 PLN” -> „Kwota operacji: 200,00 PLN”."""
    if c.dokument != "przelew":
        return t
    rx = re.compile(rf"(?im)^([ \t]*)({ETYKIETY_PRZELEWU})[ \t]*\n(?![ \t]*(?:{ETYKIETY_PRZELEWU})\b)([ \t]*\S[^\n]*)")
    return rx.sub(lambda m: f"{m.group(1)}{m.group(2)}: {m.group(3).strip()}", t)


def _przelew(wzorzec: str, zamiana: str) -> Callable[[str, Ctx], str]:
    rx = re.compile(wzorzec, re.I | re.M)
    return lambda t, c: rx.sub(zamiana, t) if c.dokument == "przelew" else t


def _pelnom(wzorzec: str, zamiana: str) -> Callable[[str, Ctx], str]:
    rx = re.compile(wzorzec)
    return lambda t, c: rx.sub(zamiana, t) if c.dokument == "pelnomocnictwo" else t


ZABURZENIA: dict[str, tuple[str, Callable[[str, Ctx], str]]] = {
    # daty
    "daty_slownie": ("16.06.2025 / 2025-06-16 -> 16 czerwca 2025 r.", daty_slownie),
    "daty_kropki": ("16 czerwca 2025 / 2025-06-16 -> 16.06.2025", daty_kropki),
    "daty_iso": ("16.06.2025 / 16 czerwca 2025 -> 2025-06-16", daty_iso),
    "daty_ukosnik": ("dowolna data -> 16/06/2025", daty_ukosnik),
    "dnia_w_naglowku": ("„Łódź, 1 kwietnia 2026” -> „Łódź, dnia 1 kwietnia 2026 r.”", dnia_w_naglowku),
    "w_dniu_na_dnia": ("„w dniu 20 marca” -> „dnia 20 marca”", _sub(r"\bw dniu\b", "dnia")),
    # identyfikatory
    "nip_kreski": ("NIP 9999284065 -> NIP 999-928-40-65", nip_kreski),
    "nip_nr_po": ("„NIP:” -> „NIP nr”", _sub(r"\bNIP:?[ \t]*(?=\d)", "NIP nr ")),
    "nip_nr_przed": ("„NIP:” -> „nr NIP”", _sub(r"\bNIP:?[ \t]*(?=\d)", "nr NIP ")),
    "nip_numer_identyfikacji": ("„NIP:” -> „numer identyfikacji podatkowej (NIP):”",
                                _sub(r"\bNIP:?[ \t]*(?=\d)", "numer identyfikacji podatkowej (NIP): ")),
    "regon_nr": ("„REGON:” -> „REGON nr”", _sub(r"\bREGON:?[ \t]*(?=\d)", "REGON nr ")),
    "krs_pod_numerem": ("„KRS:” -> „wpisana do KRS pod numerem”",
                        _sub(r"\bKRS:?[ \t]*(?=\d)", "wpisana do KRS pod numerem ")),
    "krs_nr": ("„KRS:” -> „nr KRS”", _sub(r"\bKRS:?[ \t]*(?=\d)", "nr KRS ")),
    "identyfikatory_srednik": ("„KRS: X, NIP: Y” -> „KRS – X; NIP – Y”",
                               _sub(r"\b(KRS|NIP|REGON):?[ \t]*(?=\d)", r"\1 – ")),
    # rachunek i kwota
    "rachunek_ciag": ("PL64 6217 1965 ... -> PL646217...", rachunek_ciag),
    "rachunek_spacje": ("PL05470680... -> PL05 4706 80...", rachunek_spacje),
    "rachunek_bez_pl": ("PL05 4706 ... -> 05 4706 ...", rachunek_bez_pl),
    "kwota_pln_na_zl": ("200,00 PLN -> 200,00 zł", _sub(r"(?<=\d)[ \t]*PLN\b", " zł")),
    "kwota_zl_na_pln": ("200,00 zł -> 200,00 PLN", _sub(r"(?<=\d)[ \t]*zł", " PLN")),
    "kwota_kropka": ("200,00 -> 200.00", _sub(r"(?<=\d),(?=\d{2}\b)", ".")),
    "kwota_bez_groszy": ("200,00 PLN -> 200 PLN", _sub(r"(?<=\d)[,.]00(?=[ \t]*(?:PLN|zł))", "")),
    "kwota_waluta_przed": ("200,00 PLN -> PLN 200,00", _sub(r"(\d+[,.]\d{2})[ \t]*PLN\b", r"PLN \1")),
    "kwota_slownie": ("200,00 PLN -> 200,00 PLN (słownie: dwieście złotych 00/100)", kwota_slownie),
    # etykiety odwołania
    "odwolujacy_wykonawca": ("„Odwołujący:” -> „Odwołujący (Wykonawca):”",
                             _sub(r"(?m)^([ \t]*)Odwołujący:", r"\1Odwołujący (Wykonawca):")),
    "zamawiajacy_myslnik": ("„Zamawiający:” -> „Zamawiający – ”", _sub(r"(?m)^([ \t]*)Zamawiający:", r"\1Zamawiający –")),
    "reprezentowany_w_imieniu": ("„reprezentowana przez:” -> „w imieniu którego działa:”",
                                 _sub(r"reprezentowan\w* przez", "w imieniu którego działa")),
    "reprezentowany_pelnomocnik": ("„reprezentowana przez:” -> „działający przez pełnomocnika:”",
                                   _sub(r"reprezentowan\w* przez", "działający przez pełnomocnika")),
    "pn_pod_nazwa": ("„pn.” -> „pod nazwą”", _sub(r"\bpn\.", "pod nazwą")),
    "pn_pt": ("„pn.” -> „pt.”", _sub(r"\bpn\.", "pt.")),
    "nr_referencyjny_znak": ("„nr referencyjny sprawy:” -> „znak postępowania:”",
                             _sub(r"(?:nr|numer) referencyjny(?: sprawy)?", "znak postępowania")),
    "cudzyslowy_proste": ("„…” -> \"…\"", cudzyslowy('"', '"')),
    "cudzyslowy_francuskie": ("„…” -> «…»", cudzyslowy("«", "»")),
    "etykiety_wielkie": ("„Odwołujący:” -> „ODWOŁUJĄCY:” (też Zamawiający, dotyczy)", etykiety_wielkie),
    "zamiana_blokow": ("blok Zamawiającego przed blokiem Odwołującego", zamiana_blokow),
    "bez_naglowka_prezes": ("usunięty nagłówek „Prezes KIO, ul. Postępu 17A, …”", bez_naglowka_prezes),
    # układ strony
    "puste_linie": ("pusta linia po każdej linii", puste_linie),
    "zlamanie_nazwy": ("złamanie linii w środku nazwy firmy", zlamanie_nazwy),
    "strona_w_srodku": ("„Strona 1 z 3” w środku strony", _w_srodku("Strona 1 z 3")),
    "strona_inna_forma": ("„str. 1/3” w środku strony", _w_srodku("str. 1/3")),
    "podwojne_spacje": ("każda spacja podwojona", podwojne_spacje),
    # przelew
    "przelew_dwukropek": ("„Kwota operacji 50,00” -> „Kwota operacji: 50,00”", _etykiety(_dwukropek)),
    "przelew_wartosc_pod": ("„Wartość 50,00” -> „Wartość\\n50,00”", _etykiety(_wartosc_pod)),
    "przelew_wartosc_obok": ("„Kwota operacji\\n200,00” -> „Kwota operacji: 200,00”", przelew_wartosc_obok),
    "przelew_etykiety_wielkie": ("„Rachunek odbiorcy” -> „RACHUNEK ODBIORCY” itd.",
                                 _etykiety(lambda m: f"{m.group(1)}{m.group(2).upper()}{m.group(3)}{m.group(4)}")),
    "przelew_nadawca": ("„Zleceniodawca/Płatnik” -> „Nadawca”, „Rachunek zleceniodawcy/obciążany” -> „Rachunek nadawcy”",
                        lambda t, c: _przelew(r"^([ \t]*)(?:Zleceniodawca|Płatnik|Dane nadawcy)\b", r"\1Nadawca")(
                            _przelew(r"^([ \t]*)Rachunek (?:zleceniodawcy|obciążany|płatnika)\b", r"\1Rachunek nadawcy")(t, c), c)),
    "przelew_beneficjent": ("„Odbiorca” -> „Beneficjent”, „Rachunek odbiorcy/uznawany” -> „Rachunek beneficjenta”",
                            lambda t, c: _przelew(r"^([ \t]*)(?:Odbiorca|Adresat przelewu|Dane odbiorcy)\b", r"\1Beneficjent")(
                                _przelew(r"^([ \t]*)Rachunek (?:odbiorcy|uznawany)\b", r"\1Rachunek beneficjenta")(t, c), c)),
    "przelew_nr_rachunku": ("„Rachunek odbiorcy” -> „Nr rachunku odbiorcy” (też nadawcy)",
                            _przelew(r"^([ \t]*)Rachunek (\w+)", r"\1Nr rachunku \2")),
    "przelew_tytulem": ("„Tytuł przelewu/Tytuł/Opis” -> „Tytułem”",
                        _przelew(r"^([ \t]*)(?:Tytuł przelewu|Tytuł|Opis)(?=[ \t:.]|$)", r"\1Tytułem")),
    "przelew_kwota_przelewu": ("„Kwota/Kwota operacji/Wartość” -> „Kwota przelewu”",
                               _przelew(r"^([ \t]*)(?:Kwota operacji|Kwota(?! przelewu)|Wartość)(?=[ \t:.]|$)",
                                        r"\1Kwota przelewu")),
    "przelew_data_ksiegowania": ("„Data operacji/transakcji/realizacji” -> „Data księgowania”",
                                 _przelew(r"^([ \t]*)Data (?:operacji|transakcji|realizacji|wykonania)", r"\1Data księgowania")),
    "przelew_data_zaksiegowania": ("„Data operacji/…” -> „Data zaksięgowania”",
                                   _przelew(r"^([ \t]*)Data (?:operacji|transakcji|realizacji|wykonania)",
                                            r"\1Data zaksięgowania")),
    "przelew_identyfikator": ("„Numer referencyjny/Nr ref.” -> „Identyfikator transakcji”",
                              _przelew(r"^([ \t]*)(?:Numer referencyjny|Nr ref\.)", r"\1Identyfikator transakcji")),
    # pełnomocnictwo
    "pel_tytul_pelny": ("„r. pr.” -> „radca prawny”, „adw.” -> „adwokat”",
                        lambda t, c: _pelnom(r"\badw\.", "adwokat")(_pelnom(r"\br\. ?pr\.", "radca prawny")(t, c), c)),
    "pel_tytul_biernik": ("„ustanawiam pełnomocnikiem r. pr. X” -> „… radcę prawnego X” / „adwokata X”",
                          lambda t, c: _pelnom(r"\badw\.", "adwokata")(_pelnom(r"\br\. ?pr\.", "radcę prawnego")(t, c), c)),
    "pel_tytul_bez_spacji": ("„r. pr.” -> „r.pr.”", _pelnom(r"\br\. pr\.", "r.pr.")),
    "pel_ustanawia": ("„ustanawiam pełnomocnikiem” -> „ustanawia pełnomocnikiem”",
                      _pelnom(r"ustanawiam\b", "ustanawia")),
    "pel_udzielam": ("„ustanawiam pełnomocnikiem” -> „udziela pełnomocnictwa”",
                     _pelnom(r"ustanawiam pełnomocnikiem|ustanawiam pełnomocników", "udziela pełnomocnictwa")),
    "pel_mocodawca_dwukropek": ("„Mocodawcą jest X,” -> „Mocodawca: X,”", _pelnom(r"Mocodawcą jest", "Mocodawca:")),
}


# ---------------------------------------------------------------- walidacja: znaczenie zachowane

def _kanon(t: str) -> dict:
    # stopka strony wstawiona w środek zdania nie zmienia znaczenia (zwykły PDF wielostronicowy)
    t = re.sub(r"(?m)^[ \t]*(?:Strona \d+ z \d+|str\. \d+/\d+)[ \t]*\n?", "", t)
    t = re.sub(r"[ \t]+", " ", t)
    luz = unicodedata.normalize("NFKC", t)
    luz = re.sub(r"-\n(?=[a-ząćęłńóśźż])", "", luz)
    luz = re.sub(r"[„”“\"'’`«»]", "", luz)
    luz = re.sub(r"\s+", " ", luz).casefold()
    daty = {data_iso(m.group(0)) for rx in (RE_DATA_NUM, RE_DATA_ISO, RE_DATA_SLOW) for m in rx.finditer(t)}
    kwoty = {kwota(m.group(0)) for m in re.finditer(r"\d+(?:[,.]\d{2})?", t)}
    return {"luz": luz, "cyfry": re.sub(r"\D", "", t), "daty": daty, "kwoty": kwoty}


def _obecne(v, k: dict) -> bool:
    if isinstance(v, bool):
        return True
    if isinstance(v, (int, float)):
        return float(v) in k["kwoty"]
    s = str(v)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s in k["daty"]
    cyf = re.sub(r"\D", "", s)
    if len(cyf) >= 5 and len(cyf) >= 0.6 * len(re.sub(r"\s", "", s)):
        return cyf in k["cyfry"]
    s = re.sub(r"[„”“\"'’`«»]", "", unicodedata.normalize("NFKC", s))
    return re.sub(r"\s+", " ", s).casefold().strip() in k["luz"]


def naruszone(gold: dict, orig: str, nowy: str) -> list[str]:
    """Pola z referencji obecne w oryginale, których po zaburzeniu nie ma w tekście w żadnej formie."""
    ko, kn = _kanon(orig), _kanon(nowy)
    wynik = []
    for klucz, v in ev.splaszcz(gold).items():
        if v is None or klucz.rsplit(".", 1)[-1] in POLA_BEZ_TEKSTU:
            continue
        if _obecne(v, ko) and not _obecne(v, kn):
            wynik.append(klucz)
    return wynik


# ---------------------------------------------------------------- przebieg

@dataclass(frozen=True)
class Dok:
    gdzie: str
    dokument: str
    strony: tuple[str, ...]
    gold: dict


@dataclass
class Wynik:
    licznik: ev.Licznik = field(default_factory=ev.Licznik)
    zmienione: int = 0
    pogorszone: int = 0
    poprawione: int = 0
    naruszone: list[str] = field(default_factory=list)
    zepsute: Counter = field(default_factory=Counter)
    przyklady: dict[str, list[dict]] = field(default_factory=lambda: defaultdict(list))


def wczytaj_dokumenty(gold_dir: Path, u: ev.Ustawienia, sprawy: set[int] | None) -> list[Dok]:
    doki = []
    for sprawa in sorted(d for d in gold_dir.iterdir() if d.is_dir() and d.name.startswith("przyklad")):
        if sprawy is not None and ev.numer_sprawy(sprawa.name) not in sprawy:
            continue
        for pdf in sorted(sprawa.glob("*.pdf")):
            nazwa = u.aliasy.get(pdf.stem, pdf.stem)
            gplik = sprawa / f"{nazwa}.json"
            gold = ev.wczytaj_json(gplik) if gplik.exists() else {}
            strony = wczytaj(pdf).strony if pdf.stat().st_size else ()
            doki.append(Dok(f"{sprawa.name}/{nazwa}", nazwa, tuple(strony), gold))
    return doki


def ekstrahuj(potok: Potok, strony: tuple[str, ...]) -> dict:
    if not strony:
        return {}
    w = potok.przetworz_tekst("\n".join(strony), strony)
    return w.dane or {}


def ocen(gold: dict, pred: dict, u: ev.Ustawienia, d: Dok) -> ev.Raport:
    r = ev.Raport()
    klasa = ev.klasa_z_json(gold) if gold else ev.klasa_z_json(pred)
    ev.porownaj(gold, pred, u, klasa, d.gdzie, r)
    return r


def fragment_zmiany(orig: str, nowy: str, wskazowka: str | None) -> tuple[str, str]:
    """Linia przed/po zaburzeniu, najbliżej miejsca wartości z referencji."""
    a, b = orig.split("\n"), nowy.split("\n")
    hunki = [op for op in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if op[0] != "equal"]
    if not hunki:
        return "", ""
    cel = None
    if wskazowka:
        klucz = re.sub(r"\D", "", wskazowka) if re.fullmatch(r"[\d\s-]+", wskazowka) else wskazowka[:12]
        cel = next((i for i, linia in enumerate(a) if klucz and klucz in (re.sub(r"\D", "", linia)
                    if klucz.isdigit() else linia)), None)
    op = min(hunki, key=lambda h: abs(h[1] - cel)) if cel is not None else hunki[0]
    przed = " ⏎ ".join(a[op[1]:op[2]])[:160]
    po = " ⏎ ".join(b[op[3]:op[4]])[:160]
    return przed, po


def przebieg(doki: list[Dok], potok: Potok, u: ev.Ustawienia, baza: dict[str, tuple[dict, ev.Raport]],
             fn: Callable[[str, Ctx], str] | None) -> Wynik:
    w = Wynik()
    for d in doki:
        pred0, r0 = baza[d.gdzie]
        strony = d.strony
        if fn is not None and strony:
            ctx = Ctx(d.gold, d.dokument)
            nowe = tuple(fn(s, ctx) for s in strony)
            if nowe != strony:
                zlamane = naruszone(d.gold, "\n".join(strony), "\n".join(nowe))
                if zlamane:
                    w.naruszone.append(f"{d.gdzie}: {', '.join(zlamane[:3])}")
                else:
                    strony = nowe
        if strony is d.strony:
            w.licznik.dodaj(r0.ogolem)
            continue
        w.zmienione += 1
        pred = ekstrahuj(potok, strony)
        r = ocen(d.gold, pred, u, d)
        w.licznik.dodaj(r.ogolem)
        bledne0 = {b[1] for b in r0.bledy}
        bledne = {b[1]: b for b in r.bledy}
        nowe_bledy = [k for k in bledne if k not in bledne0]
        w.pogorszone += int(bool(nowe_bledy))
        w.poprawione += int(bool(bledne0 - set(bledne)))
        p0 = ev.splaszcz(pred0)
        for k in nowe_bledy:
            pole = f"{d.dokument}:{ev.ogolne_pole(k)}"
            w.zepsute[pole] += 1
            if len(w.przyklady[pole]) < 3:
                gv = bledne[k][2]
                przed, po = fragment_zmiany("\n".join(d.strony), "\n".join(strony),
                                            str(gv) if gv is not None else None)
                w.przyklady[pole].append({"gdzie": d.gdzie, "klucz": k, "oczekiwane": gv,
                                          "bylo": p0.get(k), "jest": bledne[k][3], "tekst_przed": przed,
                                          "tekst_po": po})
    return w


# ---------------------------------------------------------------- raport

def _krotko(v, n: int = 60) -> str:
    s = repr(v)
    return (s[: n - 1] + "…" if len(s) > n else s).replace("|", "\\|")


def raport_md(bez: Wynik, wyniki: dict[str, Wynik], liczba_dok: int) -> str:
    w = ["# Zbiór kontrolny: odporność reguł na zaburzenia tekstu", "",
         "Uruchomienie:", "", "```", "PYTHONPATH=src .venv/bin/python scripts/kontrolny.py --md docs/KONTROLNY.md", "```", "",
         f"Dokumentów: {liczba_dok} (60 spraw × 3 pliki). Każde zaburzenie stosowane osobno, na kopii tekstu z PDF; "
         "ekstrakcja bez modelu (same reguły z `config/klasy/*.yaml`); F1 w trybie ścisłym (`eval.porownaj`, "
         "`--scisle`) wobec niezmienionej referencji UZP, liczone na wszystkich dokumentach "
         "(niezmienione wnoszą wynik bazowy).", "",
         "Kolumny: **zmienione** = dokumenty, w których zaburzenie coś zmieniło; **gorzej** = dokumenty, w których "
         "co najmniej jedno pole zepsuło się względem wyniku bez zaburzeń; **naruszone** = dokumenty pominięte, "
         "bo po zaburzeniu wartość z referencji zniknęła z tekstu (zaburzenie zmieniłoby znaczenie).", "",
         "| Zaburzenie | Opis | F1 | zmienione | gorzej | naruszone | Zepsute pola (liczba dokumentów) |",
         "|---|---|---|---|---|---|---|",
         f"| **bez zaburzeń** | — | {bez.licznik.f1():.4f} | 0 | 0 | 0 | — |"]
    kolejnosc = sorted(wyniki.items(), key=lambda kv: (kv[1].licznik.f1(), -kv[1].pogorszone))
    for nazwa, r in kolejnosc:
        pola = ", ".join(f"`{p}` ({n})" for p, n in r.zepsute.most_common(4)) or "—"
        w.append(f"| `{nazwa}` | {ZABURZENIA[nazwa][0].replace('|', '/')} | {r.licznik.f1():.4f} | {r.zmienione} | "
                 f"{r.pogorszone} | {len(r.naruszone)} | {pola} |")
    w += ["", "## Przykłady (zaburzenia, które coś psują; najgorsze na górze)", ""]
    for nazwa, r in kolejnosc:
        if not r.zepsute:
            continue
        w += [f"### `{nazwa}` — F1 {r.licznik.f1():.4f}, gorzej w {r.pogorszone} dok.", "",
              f"{ZABURZENIA[nazwa][0]}", ""]
        for pole, n in r.zepsute.most_common(6):
            w.append(f"- **`{pole}`** ({n} dok.)")
            for p in r.przyklady[pole]:
                w.append(f"  - `{p['gdzie']}` `{p['klucz']}`: oczekiwane {_krotko(p['oczekiwane'])}, "
                         f"bez zaburzenia {_krotko(p['bylo'])}, po {_krotko(p['jest'])}")
                if p["tekst_przed"] or p["tekst_po"]:
                    w.append(f"    - tekst przed: `{p['tekst_przed']}`")
                    w.append(f"    - tekst po: `{p['tekst_po']}`")
        if r.naruszone:
            w.append(f"- pominięte (naruszone znaczenie): {'; '.join(r.naruszone[:3])}")
        w.append("")
    bez_zmian = [n for n, r in kolejnosc if not r.zepsute]
    w += ["## Zaburzenia bez wpływu", "", ", ".join(f"`{n}`" for n in bez_zmian) or "—", ""]
    return "\n".join(w)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Zbiór kontrolny: F1 po pojedynczych zaburzeniach tekstu")
    ap.add_argument("--gold", type=Path, default=KORZEN / "data/raw/uzp/dane")
    ap.add_argument("--klasy", type=Path, default=KORZEN / "config/klasy")
    ap.add_argument("--config", type=Path, default=KORZEN / "config/ewaluacja.yaml")
    ap.add_argument("--sprawy", help="np. 1-40")
    ap.add_argument("--tylko", help="nazwy zaburzeń po przecinku")
    ap.add_argument("--md", type=Path, help="zapisz raport Markdown (np. docs/KONTROLNY.md)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("odwolania2json").setLevel(logging.ERROR)

    u = ev.wczytaj_ustawienia(a.config, listy_po_tresci=False, scisle=True)
    potok = Potok(a.klasy, uzyj_llm=False)
    doki = wczytaj_dokumenty(a.gold, u, ev.zakres_spraw(a.sprawy))
    baza = {}
    for d in doki:
        pred = ekstrahuj(potok, d.strony)
        baza[d.gdzie] = (pred, ocen(d.gold, pred, u, d))
    bez = przebieg(doki, potok, u, baza, None)
    print(f"bez zaburzeń: F1 {bez.licznik.f1():.4f} ({len(doki)} dokumentów)")

    wybrane = a.tylko.split(",") if a.tylko else list(ZABURZENIA)
    wyniki = {}
    for nazwa in wybrane:
        r = przebieg(doki, potok, u, baza, ZABURZENIA[nazwa][1])
        wyniki[nazwa] = r
        print(f"{nazwa:28s} F1 {r.licznik.f1():.4f}  zmienione {r.zmienione:3d}  gorzej {r.pogorszone:3d}  "
              f"naruszone {len(r.naruszone):3d}  {dict(r.zepsute.most_common(3))}")
    if a.md:
        a.md.write_text(raport_md(bez, wyniki, len(doki)), encoding="utf-8")
        print(f"\nRaport: {a.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
