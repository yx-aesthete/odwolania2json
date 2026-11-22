"""Powód czynności (1–12) rozpoznany z różnych sformułowań pierwszego zarzutu (słownik w config/klasy/odwolanie.yaml)."""
from pathlib import Path

import pytest
import yaml

from odwolania2json.silnik import Silnik

SPEC = yaml.safe_load((Path(__file__).resolve().parents[1] / "config/klasy/odwolanie.yaml").read_text(encoding="utf-8"))
PRZYPADKI = {
 1: ["odrzuceniu oferty Odwołującego", "odrzucenie oferty złożonej przez Odwołującego", "uznaniu oferty Odwołującego za odrzuconą", "odrzuceniu oferty jako niezgodnej z warunkami zamówienia"],
 2: ["wyborze oferty wykonawcy X jako najkorzystniejszej", "wyborze najkorzystniejszej oferty", "dokonaniu wyboru oferty firmy X", "uznaniu oferty X za najkorzystniejszą"],
 3: ["wykluczeniu Odwołującego z postępowania", "wykluczenie Odwołującego z udziału w postępowaniu"],
 4: ["ustaleniu treści SWZ w sposób naruszający konkurencję", "opublikowaniu ogłoszenia o zamówieniu i SWZ", "określeniu w SWZ warunków udziału", "sformułowaniu postanowień specyfikacji warunków zamówienia"],
 5: ["modyfikacji treści SWZ", "zmianie treści SWZ dokonanej w dniu", "zmianie specyfikacji warunków zamówienia"],
 6: ["udzieleniu odpowiedzi na pytania wykonawców", "wyjaśnieniach treści SWZ", "udzieleniu wyjaśnień treści SWZ"],
 7: ["zaniechaniu odrzucenia oferty wykonawcy X", "zaniechanie odrzucenia oferty firmy X", "nieodrzuceniu oferty wykonawcy X"],
 8: ["zaniechaniu wykluczenia wykonawcy X", "zaniechanie wykluczenia z postępowania wykonawcy X", "niewykluczeniu wykonawcy X"],
 9: ["unieważnieniu postępowania", "unieważnieniu postępowania o udzielenie zamówienia na podstawie art. 255"],
 10: ["zaniechaniu unieważnienia postępowania", "zaniechanie unieważnienia postępowania mimo wady"],
 11: ["opisie przedmiotu zamówienia w sposób utrudniający konkurencję", "dokonaniu opisu przedmiotu zamówienia", "określeniu w OPZ parametrów"],
 12: ["ustaleniu projektowanych postanowień umowy", "treści wzoru umowy stanowiącego załącznik do SWZ", "kształtowaniu istotnych postanowień umowy"],
}


@pytest.mark.parametrize("kod,fraza", [(k, f) for k, fs in PRZYPADKI.items() for f in fs])
def test_powod(kod, fraza):
    t = ("Działając w imieniu Alfa sp. z o.o. wnoszę odwołanie od czynności i zaniechań Zamawiającego, polegających na:\n"
         f"1) {fraza}, o czym Zamawiający poinformował w dniu 3 marca 2026 r.;\n2) zaniechaniu udostępnienia protokołu.")
    w = Silnik(SPEC).ekstrahuj(t).dane["OdwolanieKIO"]
    assert w["czynnosc_powod_id"] == kod
    assert w["czynnosc_dzien"] == "2026-03-03"
