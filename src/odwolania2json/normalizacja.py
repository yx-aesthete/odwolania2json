"""Normalizatory wartości wywoływane z YAML po nazwie (`normalizuj: [data_iso, ...]`).

Każdy przyjmuje napis i zwraca nową wartość albo None, gdy nie umie jej sprowadzić do formatu UZP.
"""
from __future__ import annotations

import re
from collections.abc import Callable

MIESIACE = {
    "stycz": 1, "luty": 2, "lute": 2, "lut": 2, "marz": 3, "marc": 3, "kwie": 4, "maj": 5, "czerw": 6,
    "lip": 7, "sierp": 8, "wrze": 9, "paźdz": 10, "pazdz": 10, "listop": 11, "grud": 12,
}
_MIES_RE = r"(?:stycz|lut|marz|marc|kwie|maj|czerw|lip|sierp|wrze|pa[źz]dz|listop|grud)\w*"
DATA_WZORCE = (
    re.compile(r"(?P<d>\d{1,2})[.\-/](?P<m>\d{1,2})[.\-/](?P<r>\d{4})"),
    re.compile(r"(?P<r>\d{4})[.\-/](?P<m>\d{1,2})[.\-/](?P<d>\d{1,2})"),
    re.compile(rf"(?P<d>\d{{1,2}})\s+(?P<mn>{_MIES_RE})\s+(?P<r>\d{{4}})", re.I),
)


def _miesiac(slowo: str) -> int | None:
    s = slowo.lower()
    return next((n for k, n in MIESIACE.items() if s.startswith(k)), None)


# Dzień słownie (liczebnik porządkowy w dopełniaczu): „szóstego października 2026 r.”, „dwudziestego pierwszego …”
_DZIEN_SLOWNIE = {
    "pierwszego": 1, "drugiego": 2, "trzeciego": 3, "czwartego": 4, "piątego": 5, "szóstego": 6, "siódmego": 7,
    "ósmego": 8, "dziewiątego": 9, "dziesiątego": 10, "jedenastego": 11, "dwunastego": 12, "trzynastego": 13,
    "czternastego": 14, "piętnastego": 15, "szesnastego": 16, "siedemnastego": 17, "osiemnastego": 18,
    "dziewiętnastego": 19, "dwudziestego": 20, "trzydziestego": 30,
}
_DATA_SLOWNIE = re.compile(rf"\b(?P<d>(?:dwudziestego|trzydziestego)(?:\s+[a-ząćęłńóśźż]+)?|[a-ząćęłńóśźż]+ego)\s+"
                           rf"(?P<mn>{_MIES_RE})\s+(?P<r>\d{{4}})", re.I)


def _dzien_slownie(slowa: str) -> int | None:
    czesci = slowa.lower().split()
    if not czesci or any(c not in _DZIEN_SLOWNIE for c in czesci):
        return None
    d = sum(_DZIEN_SLOWNIE[c] for c in czesci)
    return d if len(czesci) == 1 or (czesci[0] in ("dwudziestego", "trzydziestego") and _DZIEN_SLOWNIE[czesci[1]] < 10) else None


def data_iso(s: str) -> str | None:
    m = _DATA_SLOWNIE.search(s)
    if m and not re.search(r"\d{1,2}[.\-/ ]\s*(?:\d{1,2}[.\-/]|[a-ząćęłńóśźż]+\s+)\d{4}", s[: m.start()]):
        d, mies = _dzien_slownie(m.group("d")), _miesiac(m.group("mn"))
        if d and mies and 1 <= d <= 31:
            return f"{int(m.group('r')):04d}-{mies:02d}-{d:02d}"
    for wz in DATA_WZORCE:
        m = wz.search(s)
        if not m:
            continue
        g = m.groupdict()
        mies = int(g["m"]) if g.get("m") else _miesiac(g["mn"])
        d, r = int(g["d"]), int(g["r"])
        if mies and 1 <= mies <= 12 and 1 <= d <= 31:
            return f"{r:04d}-{mies:02d}-{d:02d}"
    return None


_DATA_NA_POCZATKU = re.compile(r"\d{1,2}[-./]\d{1,2}[-./]\d{2,4}\b|\d{4}-\d{2}-\d{2}\b")


def kwota(s: str) -> float | None:
    m = re.search(r"\d[\d\s. ]*(?:,\d{1,2}|\.\d{2})?", s)
    if not m:
        return None
    if _DATA_NA_POCZATKU.match(s, m.start()):   # „Kwota⏎30-03-2026”: data to nigdy kwota (Z46)
        return None
    t = re.sub(r"[\s ]", "", m.group(0))
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1 or re.search(r"\.\d{3}$", t):
        t = t.replace(".", "")
    try:
        return round(float(t), 2)
    except ValueError:
        return None


def cyfry(s: str) -> str | None:
    t = re.sub(r"\D", "", s)
    return t or None


_RACHUNEK = re.compile(r"(PL)?[ \t]*(\d{2}(?:\s*\d){24})")


def rachunek(s: str) -> str | None:
    """IBAN/NRB tak jak w dokumencie, bez spacji: „PL” + 26 cyfr, gdy PL stoi przed tym numerem, inaczej 26 cyfr
    (UZP 21.11: numer z dokumentu; brak PL w części referencji to błąd)."""
    m = _RACHUNEK.search(s.upper())
    return ((m.group(1) or "") + re.sub(r"\D", "", m.group(2))) if m else None


def rachunek_drugi(s: str) -> str | None:
    """Drugi rachunek z kolumny wartości („Rachunek nadawcy⏎Rachunek odbiorcy⏎<nadawca>⏎<odbiorca>”, numery łamane)."""
    numery = list(_RACHUNEK.finditer(s.upper()))   # PL z fragmentu tego numeru, nie z innego miejsca
    if len(numery) >= 2:
        return (numery[1].group(1) or "") + re.sub(r"\D", "", numery[1].group(2))
    t = re.sub(r"\D", "", s)
    return t[26:52] if len(t) >= 52 else None


def rachunek_pl(s: str) -> str | None:
    """Rachunek z prefiksem kraju, gdy dokument go ma: „PL75 2170 …” -> „PL75217…” (konwencja części referencji UZP)."""
    t = re.sub(r"[\s\-]", "", s.upper())
    m = re.search(r"(PL)?(\d{26})", t)
    return ((m.group(1) or "") + m.group(2)) if m else None


_ZNANE: dict | None = None


def _znane_rachunki() -> dict:
    global _ZNANE
    if _ZNANE is None:
        import yaml
        from pathlib import Path
        p = Path(__file__).resolve().parents[2] / "config" / "znane_rachunki.yaml"
        _ZNANE = (yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None) or {}
    return _ZNANE


def _odleglosc(a: str, b: str) -> int:
    """Odległość edycyjna (Levenshtein) dwóch napisów."""
    poprz = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        biez = [i]
        for j, cb in enumerate(b, 1):
            biez.append(min(poprz[j] + 1, biez[j - 1] + 1, poprz[j - 1] + (ca != cb)))
        poprz = biez
    return poprz[-1]


def rachunek_znany(s: str) -> str | None:
    """Rachunek jak `rachunek`; odczyt z błędem OCR (zgubione/przekręcone cyfry) blisko rachunku z
    config/znane_rachunki.yaml (najwyżej `max_roznica`) -> ten znany rachunek; inaczej None."""
    dobry = rachunek(s)
    if dobry:
        return dobry
    t = re.sub(r"\D", "", s)
    konf = _znane_rachunki()
    if not 20 <= len(t) <= 32:
        return None
    granica = int(konf.get("max_roznica", 3))
    bliskie = [r for r in konf.get("rachunki") or [] if _odleglosc(t, str(r)) <= granica]
    pl = "PL" if re.match(r"\s*PL", s.upper()) else ""
    return pl + str(bliskie[0]) if len(bliskie) == 1 else None


# Rachunek w dowolnym miejscu tekstu: 26 cyfr w grupach „NN NNNN …” albo zwarty, także złamany w komórce na dwie linie.
_RACH_SEP = r"(?:[ \t]?|[ \t]*\n[ \t]*)"
_RACH_W_TEKSCIE = re.compile(rf"(?<![\dA-Za-z])(?:PL[ \t]?)?\d{{2}}(?:{_RACH_SEP}\d{{4}}){{6}}(?!\d)")


def _rachunki_w_tekscie(s: str) -> dict[str, str]:
    """Rachunki w kolejności z dokumentu: 26 cyfr -> zapis do pola („PL” + 26 cyfr, gdy PL stoi przed numerem: Z44)."""
    wynik: dict[str, str] = {}
    for m in _RACH_W_TEKSCIE.finditer(s):
        cyfry = re.sub(r"\D", "", m.group(0))
        wynik.setdefault(cyfry, ("PL" if m.group(0).startswith("PL") else "") + cyfry)
    return wynik


def rachunek_znany_w_tekscie(s: str) -> str | None:
    """Rachunek z config/znane_rachunki.yaml, jeśli stoi w dokumencie (np. rachunek UZP do wpisu od odwołania):
    jest wtedy rachunkiem odbiorcy niezależnie od układu wydruku i kolejności odczytu."""
    znane = {str(r) for r in _znane_rachunki().get("rachunki") or []}
    return next((zapis for cyfry, zapis in _rachunki_w_tekscie(s).items() if cyfry in znane), None)


def rachunek_inny_niz_znany(s: str) -> str | None:
    """Gdy w dokumencie stoi rachunek znany (odbiorca) i dokładnie jeden inny, ten inny to rachunek nadawcy."""
    znane = {str(r) for r in _znane_rachunki().get("rachunki") or []}
    wszystkie = _rachunki_w_tekscie(s)
    inne = [zapis for cyfry, zapis in wszystkie.items() if cyfry not in znane]
    return inne[0] if len(inne) == 1 and len(wszystkie) > 1 else None


def krs(s: str) -> str | None:
    """KRS jako 10 cyfr: zapis bez zer wiodących („KRS 999481”) uzupełniany zerami (jak w referencjach UZP)."""
    t = re.sub(r"\D", "", s)
    return t.zfill(10) if 6 <= len(t) <= 10 else None


def regon(s: str) -> str | None:
    """REGON: 9 albo 14 cyfr, także złamany między liniami („9994⏎81075”)."""
    t = re.sub(r"\D", "", s)
    return t if len(t) in (9, 14) else None


def bzp(s: str) -> str | None:
    m = re.search(r"(\d{4})\s*/\s*BZP\s*(\d{8})(?:\s*/\s*(\d{2}))?", s, re.I)
    if not m:
        return None
    return f"{m.group(1)}/BZP{m.group(2)}" + (f"/{m.group(3)}" if m.group(3) else "")


def ted(s: str) -> str | None:
    m = re.search(r"(\d{4})\s*/\s*S\s*\d{1,3}\s*-\s*(\d{5,7})", s, re.I)
    if m:
        return f"{m.group(2)}-{m.group(1)}"
    m = re.search(r"(\d{5,7})\s*-\s*(\d{4})", s)
    return f"{m.group(1)}-{m.group(2)}" if m else None


# znaki anonimizacji w dokumentach (zaczernienia, bloki) i etykiety adresu doklejone do nazwy (skany szablonów UZP)
_ANONIMIZACJA = re.compile(r"[\u2580-\u259f\u25a0-\u25ab\u25fc-\u25fe\u2b1b\u2b1c]+")
_ETYKIETA_ADRESU = re.compile(r"^(?:adres\s+do\s+(?:dor[eę]cze[ńn]|korespondencji)|adres)\s*:\s*", re.I)


def jedna_linia(s: str) -> str | None:
    t = re.sub(r"-\n(?=[a-ząćęłńóśźż])", "", s)  # dzielenie wyrazów na końcu linii
    t = _ANONIMIZACJA.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = _ETYKIETA_ADRESU.sub("", t).strip(" ,;")
    return t or None


def forma_prawna(s: str) -> str | None:
    """Forma prawna w nazwie przekręcona przez OCR: „Sp. z 0.0.” -> „Sp. z o.o.” (zero zamiast litery „o”),
    „spółkaakcyjna” -> „spółka akcyjna” (zgubiona spacja po słowie „spółka”). Pozostałe nazwy bez zmian."""
    def litery(m: re.Match) -> str:
        if "0" not in m.group(2):
            return m.group(0)
        return m.group(1) + m.group(2).replace("0", "O" if m.group(1).strip() == "Z" else "o")
    t = re.sub(r"(\b[zZ]\s?)([oO0]\.\s?[oO0]\.)", litery, s)
    t = re.sub(r"(?i)\b(sp[oó][łl]ka)(?=akcyjna\b|jawna\b|komandytow|partnerska\b|cywilna\b|z\s*ograniczon)", r"\1 ", t)
    return t or None


def bez_cudzyslowow(s: str) -> str | None:
    t = s.strip().strip("„”\"'«» ").strip()
    return t or None


def bez_kropki(s: str) -> str | None:
    t = s.strip().rstrip(".,;:").strip()
    return t or None


def calkowita(s: str) -> int | None:
    t = cyfry(s)
    return int(t) if t else None


def email(s: str) -> str | None:
    # adres złamany na końcu linii po myślniku, kropce albo „@” („p.kos@kos-⏎radcy.example”) sklejany przed szukaniem
    s = re.sub(r"(@[\w.-]*[-.@]|[\w.+-]+@)[ \t]*\n[ \t]*(?=[\w])", r"\1", s)
    m = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", s)
    return m.group(0) if m else None   # tak jak w dokumencie (Z48), bez zmiany wielkości liter


def bez_tytulu_zawodowego(s: str) -> str | None:
    # także: „aplikant radcowski/adwokacki”, „mecenas”, „dr hab.”, „LL.M.” (tytuł przed nazwiskiem albo po nim)
    t = re.sub(r"\b(?:r\.\s?pr\.|radc\w+\s+prawn\w+|adw\.|adwokat\w*|apl\.\s?(?:adw|radc)\.?|aplikant\w*(?:\s+(?:radcowsk|adwokack)\w+)?"
               r"|mec\.|mecenas(?=\s+[A-ZŁŚŻŹĆÓ])|dr\.?(?=\s)|hab\.|prof\.|LL\.\s?M\.?)\s*", "",
               s, flags=re.I)
    t = re.sub(r"\(.*?\)", "", t)
    return jedna_linia(t.strip(" ,;"))


_CZLON = r"[A-ZŁŚŻŹĆÓ][a-ząćęłńóśźż]+(?:-[A-ZŁŚŻŹĆÓ][a-ząćęłńóśźż]+)?"
_OSOBA = re.compile(rf"^{_CZLON}(?:\s+{_CZLON}){{1,3}}$")


def osoba(s: str) -> str | None:
    """Walidator imienia i nazwiska: 2–4 człony z wielkiej litery. Śmieci z OCR -> None (wtedy następna metoda)."""
    t = jedna_linia(s)
    return t if t and _OSOBA.match(t) else None


def tytulowe(s: str) -> str | None:
    """„CEZARY ZAJĄC” -> „Cezary Zając” (podpis elektroniczny wielkimi literami); inne napisy bez zmian."""
    t = jedna_linia(s)
    if not t or not any(z.isalpha() for z in t) or t != t.upper():
        return t
    return "-".join(" ".join(w.capitalize() for w in cz.split(" ")) for cz in t.split("-"))


_ODMIANA: dict | None = None
_ZENSKIE_MIANOWNIK = re.compile(r"a$")


def _odmiana() -> dict:
    global _ODMIANA
    if _ODMIANA is None:
        import yaml
        from pathlib import Path
        p = Path(__file__).resolve().parents[2] / "config" / "odmiana.yaml"
        _ODMIANA = (yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None) or {}
    return _ODMIANA


def _do_mianownika(slowo: str, reguly: list) -> str:
    wyjatki = _odmiana().get("wyjatki") or {}
    if slowo in wyjatki:
        return wyjatki[slowo]
    for koncowka, zamiana in reguly:
        if slowo.endswith(koncowka) and len(slowo) - len(koncowka) >= 2:
            return slowo[: len(slowo) - len(koncowka)] + (zamiana or "")
    return slowo


def _oboczności(rdzen: str) -> str:
    """Po obcięciu końcówki: e ruchome (Dąbk -> Dąbek, Wróbl -> Wróbel), -ni -> -ń (Jeleni -> Jeleń)."""
    for wzor, zamiana in (_odmiana().get("obocznosci") or []):
        nowy = re.sub(wzor + "$", zamiana, rdzen)
        if nowy != rdzen:
            return nowy
    return rdzen


def mianownik(s: str, zalezny: bool = False) -> str | None:
    """Imię i nazwisko do mianownika regułami z config/odmiana.yaml („Tomaszowi Wierzbickiemu” -> „Tomasz Wierzbicki”).
    `zalezny`: kontekst (np. „adwokatowi”, „radcę prawnego”) mówi, że forma jest zależna, więc stosuje też
    reguły niejednoznaczne: męskie -a/-ego (Jana Nowaka -> Jan Nowak, Cezarego -> Cezary)."""
    t = jedna_linia(s)
    if not t:
        return None
    o = _odmiana()
    zawsze, zal = o.get("zawsze") or [], o.get("zalezny") or []
    zenskie = o.get("imie_zenskie_zalezne") or []
    meskie_imie = o.get("imie_meskie_zalezne") or []
    meskie = set(o.get("imiona_meskie") or [])
    wyj = o.get("wyjatki") or {}
    slowa = t.split(" ")
    if len(slowa) < 2:
        return t
    pierwsze = slowa[0]
    if pierwsze.endswith(("ego", "emu", "owi")):  # imię w formie zależnej (Ignacego, Jerzemu, Janowi)
        zalezny = True
    if wyj.get(pierwsze, pierwsze) != pierwsze:   # imię z listy form zależnych („Marka” -> „Marek”): forma zależna
        zalezny = True
    if any(w.endswith(("skiego", "ckiego", "dzkiego", "skiemu", "ckiemu", "dzkiemu")) for w in slowa[1:]):
        zalezny = True  # „Piotra Malinowskiego”: forma zależna mężczyzny
    if zalezny and all(w.endswith(("ska", "cka", "dzka")) for w in slowa[1:2]):  # „Anna Kowalska”: już mianownik
        return t
    # imię: wyjątki, końcówki zawsze-bezpieczne, żeńskie zależne (Annie, Teresie), męskie zależne (Cezarego, Jana)
    imie = wyj.get(pierwsze) or _do_mianownika(pierwsze, zawsze)
    nazwisko_zenskie_zal = any(w.endswith(("skiej", "ckiej", "dzkiej", "ską", "cką", "dzką")) for w in slowa[1:])
    if nazwisko_zenskie_zal:  # „Laury Michalskiej”, „Annę Kowalską”: forma zależna kobiety, także -y/-i w imieniu
        zenskie = zenskie + (o.get("imie_zenskie_dopelniacz") or [])
    kobieta = (pierwsze.endswith("ę") or nazwisko_zenskie_zal
               or (imie == pierwsze and any(pierwsze.endswith(k) for k, _ in zenskie)))
    if kobieta and imie == pierwsze:
        imie = _do_mianownika(pierwsze, zenskie)
    if not kobieta and imie == pierwsze and zalezny:
        kandydat = _do_mianownika(pierwsze, meskie_imie)
        if kandydat == pierwsze and re.search(r"[^aeiouyąęó]a$", pierwsze):
            kandydat = pierwsze[:-1]
            if kandydat not in meskie and _oboczności(kandydat) in meskie:  # Franciszka -> Franciszek
                kandydat = _oboczności(kandydat)
        imie = kandydat if kandydat in meskie or kandydat != pierwsze and not pierwsze.endswith("a") else (
            kandydat if kandydat in meskie else imie)
    meski = imie in meskie or (pierwsze.endswith(("owi", "ego", "emu")) and not kobieta)
    if pierwsze.endswith("owi") or pierwsze.endswith("emu"):
        zalezny = True
    # „-a” w nazwisku obcinamy tylko, gdy imię też było w formie zależnej (Jana Nowaka -> Jan Nowak);
    # „Jan Kępa”, „Jerzy Sowa” po „radcy prawnego” to już mianownik (Z48)
    imie_zalezne = imie != pierwsze or pierwsze.endswith(("ego", "emu", "owi"))
    wynik = [imie]
    for w in slowa[1:]:
        czlony = []
        for c in w.split("-"):
            nowy = wyj.get(c) or _do_mianownika(c, zawsze)
            if nowy == c and nowy.endswith("owi"):
                nowy = c
            if nowy != c and c.endswith("owi") and not kobieta:
                nowy = _oboczności(nowy)
            elif nowy == c and zalezny and meski and not kobieta and imie_zalezne and re.search(r"[^aeiouyąęó]a$", c):
                nowy = _oboczności(c[:-1])
            elif nowy == c and zalezny and meski and not kobieta and imie_zalezne and c.endswith("ia"):
                nowy = _oboczności(c[:-1])
            czlony.append(nowy)
        wynik.append("-".join(czlony))
    return " ".join(wynik)


def mianownik_zalezny(s: str) -> str | None:
    return mianownik(s, zalezny=True)


NORMALIZATORY: dict[str, Callable[[str], object]] = {
    "data_iso": data_iso, "kwota": kwota, "cyfry": cyfry, "rachunek": rachunek, "bzp": bzp, "ted": ted,
    "jedna_linia": jedna_linia, "bez_cudzyslowow": bez_cudzyslowow, "bez_kropki": bez_kropki,
    "calkowita": calkowita, "email": email, "bez_tytulu_zawodowego": bez_tytulu_zawodowego,
    "osoba": osoba, "mianownik": mianownik, "mianownik_zalezny": mianownik_zalezny, "tytulowe": tytulowe, "rachunek_pl": rachunek_pl,
    "rachunek_znany": rachunek_znany, "krs": krs, "regon": regon,
    "rachunek_drugi": rachunek_drugi, "rachunek_znany_w_tekscie": rachunek_znany_w_tekscie,
    "rachunek_inny_niz_znany": rachunek_inny_niz_znany, "forma_prawna": forma_prawna,
}


def zastosuj(wartosc: object, nazwy: list[str]) -> object:
    for n in nazwy:
        if wartosc is None:
            return None
        if n not in NORMALIZATORY:
            raise ValueError(f"nieznany normalizator: {n} (dostępne: {', '.join(sorted(NORMALIZATORY))})")
        wartosc = NORMALIZATORY[n](str(wartosc))
    return wartosc
