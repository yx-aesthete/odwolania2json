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


def data_iso(s: str) -> str | None:
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


def kwota(s: str) -> float | None:
    m = re.search(r"\d[\d\s. ]*(?:,\d{1,2}|\.\d{2})?", s)
    if not m:
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


def rachunek(s: str) -> str | None:
    """IBAN/NRB -> same cyfry bez PL (format referencji UZP)."""
    m = re.search(r"(?:PL)?\s*\d{2}(?:\s*\d){24}", s.upper())
    return re.sub(r"\D", "", m.group(0)) if m else None


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


def jedna_linia(s: str) -> str | None:
    t = re.sub(r"-\n(?=[a-ząćęłńóśźż])", "", s)  # dzielenie wyrazów na końcu linii
    t = re.sub(r"\s+", " ", t).strip()
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
    m = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", s)
    return m.group(0).lower() if m else None


def bez_tytulu_zawodowego(s: str) -> str | None:
    t = re.sub(r"\b(?:r\.\s?pr\.|radc\w+\s+prawn\w+|adw\.|adwokat\w*|apl\.\s?(?:adw|radc)\.?|aplikant\w*|mec\.|dr|prof\.)\s*", "",
               s, flags=re.I)
    t = re.sub(r"\(.*?\)", "", t)
    return jedna_linia(t.strip(" ,;"))


NORMALIZATORY: dict[str, Callable[[str], object]] = {
    "data_iso": data_iso, "kwota": kwota, "cyfry": cyfry, "rachunek": rachunek, "bzp": bzp, "ted": ted,
    "jedna_linia": jedna_linia, "bez_cudzyslowow": bez_cudzyslowow, "bez_kropki": bez_kropki,
    "calkowita": calkowita, "email": email, "bez_tytulu_zawodowego": bez_tytulu_zawodowego,
}


def zastosuj(wartosc: object, nazwy: list[str]) -> object:
    for n in nazwy:
        if wartosc is None:
            return None
        if n not in NORMALIZATORY:
            raise ValueError(f"nieznany normalizator: {n} (dostępne: {', '.join(sorted(NORMALIZATORY))})")
        wartosc = NORMALIZATORY[n](str(wartosc))
    return wartosc
