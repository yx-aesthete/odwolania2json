"""Zbiór kontrolny 3 (jawny, do strojenia): same pełnomocnictwa w nowych szablonach z rodziny UZP.

Dane fikcyjne (prefiks 999, poprawne sumy kontrolne, domeny .example). Korzysta z pomocników
z tests/kontrolny/generuj.py.
    CHROME=... python tests/kontrolny3/generuj3.py
"""
from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path

TU = Path(__file__).resolve().parent
sys.path.insert(0, str(TU.parent / "kontrolny"))
import generuj as g  # noqa: E402

R = random.Random(3333)

# Osoby: mianownik, dopełniacz, celownik, biernik (formy wpisane ręcznie, bez automatu).
OSOBY = {
    "Adam Nowak": ("Adama Nowaka", "Adamowi Nowakowi", "Adama Nowaka"),
    "Beata Kowalczyk": ("Beaty Kowalczyk", "Beacie Kowalczyk", "Beatę Kowalczyk"),
    "Cezary Zając": ("Cezarego Zająca", "Cezaremu Zającowi", "Cezarego Zająca"),
    "Dominika Wróblewska": ("Dominiki Wróblewskiej", "Dominice Wróblewskiej", "Dominikę Wróblewską"),
    "Edward Kozioł": ("Edwarda Kozioła", "Edwardowi Koziołowi", "Edwarda Kozioła"),
    "Filomena Brzęczyszczyk": ("Filomeny Brzęczyszczyk", "Filomenie Brzęczyszczyk", "Filomenę Brzęczyszczyk"),
    "Grzegorz Mazurek": ("Grzegorza Mazurka", "Grzegorzowi Mazurkowi", "Grzegorza Mazurka"),
    "Halina Sienkiewicz-Wolska": ("Haliny Sienkiewicz-Wolskiej", "Halinie Sienkiewicz-Wolskiej", "Halinę Sienkiewicz-Wolską"),
    "Ignacy Wiśniewski": ("Ignacego Wiśniewskiego", "Ignacemu Wiśniewskiemu", "Ignacego Wiśniewskiego"),
    "Joanna Lis": ("Joanny Lis", "Joannie Lis", "Joannę Lis"),
    "Kamil Dąbek": ("Kamila Dąbka", "Kamilowi Dąbkowi", "Kamila Dąbka"),
    "Laura Michalska": ("Laury Michalskiej", "Laurze Michalskiej", "Laurę Michalską"),
    "Łukasz Pawlik": ("Łukasza Pawlika", "Łukaszowi Pawlikowi", "Łukasza Pawlika"),
    "Marta Gołąb": ("Marty Gołąb", "Marcie Gołąb", "Martę Gołąb"),
    "Norbert Kuźma": ("Norberta Kuźmy", "Norbertowi Kuźmie", "Norberta Kuźmę"),
    "Olga Szczepańska": ("Olgi Szczepańskiej", "Oldze Szczepańskiej", "Olgę Szczepańską"),
    "Przemysław Wilk": ("Przemysława Wilka", "Przemysławowi Wilkowi", "Przemysława Wilka"),
    "Renata Duda": ("Renaty Dudy", "Renacie Dudzie", "Renatę Dudę"),
    "Stanisław Kot": ("Stanisława Kota", "Stanisławowi Kotu", "Stanisława Kota"),
    "Teresa Bąk": ("Teresy Bąk", "Teresie Bąk", "Teresę Bąk"),
    "Wojciech Jeleń": ("Wojciecha Jelenia", "Wojciechowi Jeleniowi", "Wojciecha Jelenia"),
    "Zofia Grabowska": ("Zofii Grabowskiej", "Zofii Grabowskiej", "Zofię Grabowską"),
    "Jerzy Pietrzyk": ("Jerzego Pietrzyka", "Jerzemu Pietrzykowi", "Jerzego Pietrzyka"),
    "Agata Kuś": ("Agaty Kuś", "Agacie Kuś", "Agatę Kuś"),
}
DOP, CEL, BIER = 0, 1, 2
TYTUL = {"r. pr.": ("radcy prawnego", "radcy prawnemu", "radcę prawnego"),
         "adw.": ("adwokata", "adwokatowi", "adwokata"),
         "r. pr.*": ("radczyni prawnej", "radczyni prawnej", "radczynię prawną"),
         "adw.*": ("adwokat", "adwokat", "adwokat"),
         "": ("Pana", "Panu", "Pana"), "*": ("Pani", "Pani", "Panią")}
KOBIETY = {n for n in OSOBY if n.split()[0].endswith("a")}


def forma(osoba, tytul, przypadek):
    klucz = tytul + ("*" if osoba in KOBIETY else "")
    klucz = klucz if klucz in TYTUL else tytul
    return f"{TYTUL[klucz][przypadek]} {OSOBY[osoba][przypadek]}"


def firma(nazwa, adres, krs=True):
    return {**g.firma(R, nazwa, adres, z_krs=krs), "typ": "osoba_prawna"}


def jdg(osoba, nazwa, adres):
    return {**g.firma(R, nazwa, adres, z_krs=False), "typ": "osoba_fizyczna", "imie_nazwisko": osoba}


def zam():
    nazwy = ["Gmina Zielone Wzgórza", "Szpital Powiatowy w Lipnie Dolnym", "Zarząd Dróg Miejskich w Kamieniu Nowym",
             "Uniwersytet Przyrodniczy w Sosnowicach", "Wodociągi Doliny Wisły sp. z o.o."]
    tyt = ["Budowa kanalizacji sanitarnej w miejscowości Brzezie", "Dostawa sprzętu medycznego dla oddziału OIOM",
           "Utrzymanie zieleni miejskiej w latach 2027–2028", "Dostawa odczynników laboratoryjnych",
           "Modernizacja stacji uzdatniania wody"]
    i = R.randrange(len(nazwy))
    return nazwy[i], tyt[R.randrange(len(tyt))], f"ZP.{R.randrange(100, 999)}.{R.randrange(1, 60)}.2026"


# ---------- szablony ----------

def t_ustanawia(c):
    """Spółka „ustanawia pełnomocnikami” (biernik), lista numerowana, podpisy: imię i nazwisko, pod spodem funkcja."""
    m = c["moc"][0]
    zn, tyt, nr = c["zam"]
    lista = "".join(f"<li>{forma(p['n'], p['t'], BIER)}" + (f", PESEL {p['pesel']}" if p.get("pesel") else "") + "</li>" for p in c["pel"])
    podp = "".join(f"<p class=podpis>…………………………<br>{o}<br><span class=mala>{f}</span></p>" for o, f in c["podp"][0])
    return g.html(f"<p class=prawo>{c['miejsce']}</p><p class='srodek tyt'>PEŁNOMOCNICTWO</p>"
                  f"<p>{m['nazwa']} z siedzibą w {m['adres'].split(', ')[-1][7:]}, adres: {m['adres']}, wpisana do Krajowego Rejestru Sądowego "
                  f"pod numerem KRS {m['krs']}, NIP {m['nip']}, REGON {m['regon']}, niniejszym ustanawia pełnomocnikami:</p><ol>{lista}</ol>"
                  f"<p>do reprezentowania spółki przed Krajową Izbą Odwoławczą w sprawie odwołania w postępowaniu „{tyt}” ({nr}), "
                  f"prowadzonym przez {zn}. Każdy z pełnomocników działa samodzielnie.</p>{podp}")


def t_formularz(c):
    """Formularz z etykietami w osobnych liniach (Firma / Siedziba / Numer KRS / NIP), pełnomocnik w mianowniku."""
    m = c["moc"][0]
    zn, tyt, nr = c["zam"]
    pel = "".join(f"<p>Imię i nazwisko pełnomocnika: {p['n']}<br>"
                  + (f"PESEL: {p['pesel']}<br>" if p.get("pesel") else "")
                  + f"Tytuł zawodowy: {'radca prawny' if p['t'] == 'r. pr.' else 'adwokat' if p['t'] == 'adw.' else '—'}</p>" for p in c["pel"])
    podp = "".join(f"<p>Podpis osoby uprawnionej do reprezentacji: {o} ({f})</p>" for o, f in c["podp"][0])
    krs = f"Numer KRS: {m['krs']}<br>" if m.get("krs") else ""
    return g.html(f"<p class='srodek tyt'>PEŁNOMOCNICTWO DO REPREZENTACJI PRZED KIO</p>"
                  f"<h3>Dane mocodawcy</h3><p>Firma: {m['nazwa']}<br>Siedziba: {m['adres']}<br>{krs}NIP: {m['nip']}<br>REGON: {m['regon']}</p>"
                  f"<h3>Dane pełnomocnika</h3>{pel}"
                  f"<h3>Zakres</h3><p>Wniesienie odwołania i reprezentacja w postępowaniu odwoławczym dotyczącym zamówienia „{tyt}”, "
                  f"nr {nr}, Zamawiający: {zn}.</p><p>Miejsce i data: {c['miejsce']}</p>{podp}")


def t_jdg_celownik(c):
    """Osoba fizyczna (JDG) „udzielam pełnomocnictwa Panu/adwokatowi …” (celownik), PESEL mocodawcy w treści."""
    m = c["moc"][0]
    zn, tyt, nr = c["zam"]
    komu = ", ".join(forma(p["n"], p["t"], CEL) + (f" (PESEL: {p['pesel']})" if p.get("pesel") else "") for p in c["pel"])
    return g.html(f"<p class=prawo>{c['miejsce']}</p><p class='srodek tyt'>Pełnomocnictwo szczególne</p>"
                  f"<p>Ja, {m['imie_nazwisko']}, przedsiębiorca wpisany do CEIDG, prowadzący działalność gospodarczą pod firmą "
                  f"„{m['nazwa']}”, {m['adres']}, NIP: {m['nip']}, REGON: {m['regon']}, udzielam pełnomocnictwa {komu} "
                  f"do działania w moim imieniu przed Krajową Izbą Odwoławczą w sprawie dotyczącej postępowania „{tyt}” "
                  f"(znak: {nr}, zamawiający: {zn}).</p><p class=podpis>…………………………<br>({m['imie_nazwisko']})</p>")


def t_konsorcjum(c):
    """Konsorcjum: Lider i Partner, „ustanawiają wspólnego pełnomocnika” (biernik), podpisy „W imieniu X: imię nazwisko – funkcja”."""
    zn, tyt, nr = c["zam"]
    czl = "".join(f"<p>{'Lider' if i == 0 else 'Partner'} konsorcjum: <b>{m['nazwa']}</b>, {m['adres']}, KRS {m['krs']}, NIP {m['nip']}</p>"
                  for i, m in enumerate(c["moc"]))
    kto = " oraz ".join(forma(p["n"], p["t"], BIER) for p in c["pel"])
    podp = "".join(f"<p class=podpis>W imieniu {m['nazwa']}:<br>" + "<br>".join(f"{o} – {f}" for o, f in os_) + "</p>"
                   for m, os_ in zip(c["moc"], c["podp"]))
    return g.html(f"<p>{c['miejsce']}</p><p class='srodek tyt'>PEŁNOMOCNICTWO</p><p>Wykonawcy wspólnie ubiegający się o udzielenie zamówienia:</p>{czl}"
                  f"<p>ustanawiają {kto} wspólnym pełnomocnikiem, uprawnionym do wniesienia odwołania i reprezentowania "
                  f"wykonawców przed Krajową Izbą Odwoławczą w postępowaniu „{tyt}” (nr {nr}) prowadzonym przez {zn}.</p>{podp}")


def t_podpis_el(c):
    """Pełnomocnictwo z podpisem elektronicznym: „Dokument podpisany przez: …”, pełnomocnik po „Pan/Pani” w bierniku."""
    m = c["moc"][0]
    zn, tyt, nr = c["zam"]
    kto = "; ".join(forma(p["n"], "", BIER) + (f", PESEL {p['pesel']}" if p.get("pesel") else "") for p in c["pel"])
    pod = "".join(f"<p class=mala>Dokument podpisany kwalifikowanym podpisem elektronicznym przez: {o.upper()}<br>Data: {c['miejsce'].split(', ')[-1]}<br>Funkcja: {f}</p>"
                  for o, f in c["podp"][0])
    krs = f", KRS {m['krs']}" if m.get("krs") else ""
    return g.html(f"<p class='srodek tyt'>PEŁNOMOCNICTWO</p><p>{c['miejsce']}</p>"
                  f"<p>Mocodawca: {m['nazwa']}, {m['adres']}{krs}, NIP {m['nip']}.</p>"
                  f"<p>Mocodawca upoważnia {kto} do złożenia odwołania do Prezesa KIO oraz do udziału w posiedzeniach i rozprawach "
                  f"w sprawie zamówienia „{tyt}” (oznaczenie {nr}), Zamawiający: {zn}.</p>{pod}")


def t_paragrafy(c):
    """Układ z § i dopełniaczem: „§ 2. Udziela się pełnomocnictwa … w osobie …” (dopełniacz po „w osobie” nie, po „dla”: dopełniacz)."""
    m = c["moc"][0]
    zn, tyt, nr = c["zam"]
    dla = ", ".join(forma(p["n"], p["t"], DOP) + (f" (PESEL {p['pesel']})" if p.get("pesel") else "") for p in c["pel"])
    podp = "".join(f"<p class=podpis>{f}<br>…………………………<br>{o}</p>" for o, f in c["podp"][0])
    krs = f"KRS: {m['krs']}; " if m.get("krs") else ""
    return g.html(f"<p class='srodek tyt'>PEŁNOMOCNICTWO</p><p class=srodek>{c['miejsce']}</p>"
                  f"<p>§ 1. Mocodawca: {m['nazwa']} ({m['adres']}; {krs}NIP: {m['nip']}).</p>"
                  f"<p>§ 2. Pełnomocnictwo udziela się dla {dla}.</p>"
                  f"<p>§ 3. Pełnomocnictwo obejmuje wniesienie odwołania w postępowaniu „{tyt}” ({nr}) prowadzonym przez {zn} "
                  f"oraz reprezentację przed Krajową Izbą Odwoławczą.</p>{podp}")


def sprawy():
    P = lambda n, t="r. pr.", pesel=False: {"n": n, "t": t, "pesel": g.pesel(R, R.randrange(1960, 1998), R.randrange(1, 13), R.randrange(1, 28)) if pesel else None}  # noqa: E731
    L = []

    def dodaj(szablon, plik, moc, podp, pel, miejsce):
        L.append(dict(id=f"caseP{len(L) + 1:02d}", szablon=szablon, plik=plik, moc=moc, podp=podp, pel=pel, miejsce=miejsce, zam=zam()))

    dodaj(t_ustanawia, "pelnomocnictwo", [firma("Rolmex Maszyny Rolnicze sp. z o.o.", "ul. Polna 12, 87-800 Włocławek")],
          [[("Adam Nowak", "Prezes Zarządu"), ("Beata Kowalczyk", "Członek Zarządu")]],
          [P("Cezary Zając"), P("Dominika Wróblewska")], "Włocławek, dnia 3 grudnia 2026 r.")
    dodaj(t_ustanawia, "pelnomocnictwo_A", [firma("Instalbud Kraków S.A.", "ul. Zakopiańska 105, 30-418 Kraków")],
          [[("Edward Kozioł", "Wiceprezes Zarządu")]], [P("Filomena Brzęczyszczyk", "adw.", pesel=True)], "Kraków, 4.12.2026 r.")
    dodaj(t_ustanawia, "skan_001", [firma("Elektro-Serwis Pomorze sp. z o.o. sp.k.", "ul. Kartuska 300, 80-125 Gdańsk")],
          [[("Grzegorz Mazurek", "Prezes Zarządu Komplementariusza")]], [P("Halina Sienkiewicz-Wolska"), P("Ignacy Wiśniewski", "adw.")],
          "Gdańsk, 5 grudnia 2026 r.")
    dodaj(t_formularz, "formularz pelnomocnictwa", [firma("Biotest Laboratoria sp. z o.o.", "ul. Chemiczna 8, 35-959 Rzeszów")],
          [[("Joanna Lis", "Prezes Zarządu")]], [P("Kamil Dąbek", pesel=True)], "Rzeszów, 07.12.2026")
    dodaj(t_formularz, "dok_2", [jdg("Łukasz Pawlik", "PAWLIK-TRANS Łukasz Pawlik", "ul. Długa 3, 21-500 Biała Podlaska")],
          [[("Łukasz Pawlik", "właściciel")]], [P("Marta Gołąb", "adw.")], "Biała Podlaska, 08.12.2026")
    dodaj(t_formularz, "pelnomocnictwo", [firma("Norbud Konstrukcje Stalowe S.A.", "ul. Hutnicza 2, 41-800 Zabrze")],
          [[("Norbert Kuźma", "Prokurent"), ("Olga Szczepańska", "Członek Zarządu")]],
          [P("Przemysław Wilk"), P("Renata Duda", pesel=True)], "Zabrze, 09.12.2026")
    dodaj(t_jdg_celownik, "pelnomocnictwo", [jdg("Stanisław Kot", "KOT-BUD Usługi Remontowe Stanisław Kot", "ul. Wiejska 14, 64-920 Piła")],
          [[("Stanisław Kot", "")]], [P("Teresa Bąk", "adw.")], "Piła, 10 grudnia 2026 r.")
    dodaj(t_jdg_celownik, "zalacznik_3", [jdg("Agata Kuś", "Kuś Catering Agata Kuś", "ul. Smaczna 7, 26-600 Radom")],
          [[("Agata Kuś", "")]], [P("Wojciech Jeleń", "r. pr."), P("Jerzy Pietrzyk", "", pesel=True)], "Radom, 11.12.2026 r.")
    dodaj(t_jdg_celownik, "pelnomocnictwo", [jdg("Ignacy Wiśniewski", "IW Projekt Ignacy Wiśniewski", "ul. Ogrodowa 1, 10-001 Olsztyn")],
          [[("Ignacy Wiśniewski", "")]], [P("Zofia Grabowska", "r. pr.")], "Olsztyn, 12 grudnia 2026 r.")
    dodaj(t_konsorcjum, "pelnomocnictwo konsorcjum", [firma("Termoinstal Śląsk sp. z o.o.", "ul. Górnicza 9, 40-001 Katowice"),
                                                       firma("Ekoenergia Partner S.A.", "ul. Słoneczna 4, 43-300 Bielsko-Biała")],
          [[("Adam Nowak", "Prezes Zarządu")], [("Laura Michalska", "Prezes Zarządu"), ("Kamil Dąbek", "Członek Zarządu")]],
          [P("Beata Kowalczyk")], "Katowice, 13.12.2026 r.")
    dodaj(t_konsorcjum, "pelnomocnictwo", [firma("Drogpol Lubuskie sp. z o.o.", "ul. Kostrzyńska 50, 66-400 Gorzów Wielkopolski"),
                                           firma("Asfalt-Mix sp. j.", "ul. Przemysłowa 3, 66-300 Międzyrzecz")],
          [[("Grzegorz Mazurek", "Prezes Zarządu")], [("Teresa Bąk", "Wspólnik"), ("Stanisław Kot", "Wspólnik")]],
          [P("Edward Kozioł", "adw."), P("Olga Szczepańska", "r. pr.")], "Gorzów Wielkopolski, 14 grudnia 2026 r.")
    dodaj(t_konsorcjum, "dokument", [firma("Medi-Tech Polska sp. z o.o.", "ul. Szpitalna 1, 60-001 Poznań"),
                                     firma("Pharmadis S.A.", "ul. Apteczna 2, 61-001 Poznań"),
                                     firma("Sterylis sp. z o.o.", "ul. Czysta 3, 62-001 Swarzędz")],
          [[("Renata Duda", "Prezes Zarządu")], [("Przemysław Wilk", "Prokurent")], [("Joanna Lis", "Prezes Zarządu")]],
          [P("Norbert Kuźma", "r. pr.")], "Poznań, 15.12.2026")
    dodaj(t_podpis_el, "pelnomocnictwo", [firma("Infocom Systemy Informatyczne S.A.", "al. Niepodległości 18, 02-653 Warszawa")],
          [[("Wojciech Jeleń", "Prezes Zarządu")]], [P("Marta Gołąb", pesel=True)], "Warszawa, 16 grudnia 2026 r.")
    dodaj(t_podpis_el, "pelnomocnictwo_nr_2", [firma("Agroserwis Mazury sp. z o.o.", "ul. Rolnicza 5, 11-500 Giżycko")],
          [[("Zofia Grabowska", "Prezes Zarządu"), ("Jerzy Pietrzyk", "Wiceprezes Zarządu")]],
          [P("Łukasz Pawlik"), P("Halina Sienkiewicz-Wolska")], "Giżycko, 17 grudnia 2026 r.")
    dodaj(t_podpis_el, "plik", [jdg("Cezary Zając", "Zając Geodezja Cezary Zając", "ul. Miernicza 2, 76-200 Słupsk")],
          [[("Cezary Zając", "przedsiębiorca")]], [P("Agata Kuś")], "Słupsk, 18 grudnia 2026 r.")
    dodaj(t_paragrafy, "pelnomocnictwo", [firma("Ochrona Plus Security sp. z o.o.", "ul. Strażnicza 7, 90-001 Łódź")],
          [[("Dominika Wróblewska", "Prezes Zarządu")]], [P("Kamil Dąbek", "adw."), P("Laura Michalska", "adw.")], "Łódź, 19.12.2026 r.")
    dodaj(t_paragrafy, "pelnomocnictwo_B", [firma("Hydro-Kop Studnie sp. z o.o.", "ul. Wodna 11, 97-300 Piotrków Trybunalski")],
          [[("Filomena Brzęczyszczyk", "Prezes Zarządu")]], [P("Adam Nowak", "r. pr.", pesel=True)], "Piotrków Trybunalski, 20 grudnia 2026 r.")
    dodaj(t_paragrafy, "pelnomocnictwo", [jdg("Teresa Bąk", "BĄK-MEBLE Teresa Bąk", "ul. Stolarska 4, 33-100 Tarnów")],
          [[("Teresa Bąk", "właścicielka")]], [P("Grzegorz Mazurek", "r. pr.")], "Tarnów, 21.12.2026 r.")
    return L


def gold(c):
    return {
        "mocodawca": [{
            "data": {"imie_nazwisko": m.get("imie_nazwisko") if m["typ"] == "osoba_fizyczna" else None,
                     "krs": m.get("krs"), "nazwa": m["nazwa"], "nip": m["nip"], "typ": m["typ"]},
            "podpisujacy": [{"imie_nazwisko": o} for o, _ in os_],
        } for m, os_ in zip(c["moc"], c["podp"])],
        "pelnomocnicy": [{"imie_nazwisko": p["n"], "pesel": p.get("pesel")} for p in c["pel"]],
    }


def main():
    for d in ("input", "oczekiwane"):
        shutil.rmtree(TU / d, ignore_errors=True)
    for c in sprawy():
        g.do_pdf(c["szablon"](c), TU / "input" / c["id"] / f"{c['plik']}.pdf")
        g.zapisz_json(gold(c), TU / "oczekiwane" / c["id"] / f"{c['plik']}.json")
        print(c["id"], c["szablon"].__name__, c["plik"])


if __name__ == "__main__":
    main()
