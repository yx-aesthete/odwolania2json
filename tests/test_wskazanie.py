from odwolania2json.wskazanie import wskaz

SPEC = [{"lista": "Z", "pole_nazwy": "nazwa", "pole": "p",
         "regex": r"post[eę]powani\w*\s+(?:przygotowuje\s+i\s+)?(?:przeprowadza|prowadzi)\s+(?P<v>[A-ZŁ][^,.;\n]{3,100})"}]


def test_wskazanie_zdaniem_w_tresci():
    d = {"Z": [{"nazwa": "Powiat Testowy", "p": 0}, {"nazwa": "Gmina Miasto Testów", "p": 0}]}
    w = wskaz(d, "Zgodnie z porozumieniem postępowanie przygotowuje i przeprowadza Gmina Miasto Testów, działająca …", SPEC)
    assert [z["p"] for z in w["Z"]] == [0, 1] and d["Z"][1]["p"] == 0   # bez mutacji wejścia


def test_wskazanie_bez_trafienia_albo_jeden_element_bez_zmian():
    d = {"Z": [{"nazwa": "Powiat Testowy", "p": 1}, {"nazwa": "Gmina Miasto Testów", "p": 0}]}
    assert wskaz(d, "Brak takiego zdania.", SPEC) == d
    jeden = {"Z": [{"nazwa": "Gmina Miasto Testów", "p": None}]}
    assert wskaz(jeden, "postępowanie przeprowadza Gmina Miasto Testów", SPEC) == jeden
