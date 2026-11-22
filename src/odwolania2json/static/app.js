// Podgląd sprawy, kierunek B „Dokument obok danych”: strona PDF z zaznaczonym cytatem obok listy pól.
"use strict";

const ETYKIETY = {
  OdwolanieKIO: "Odwołanie", Odwolujacy: "Odwołujący", Zamawiajacy: "Zamawiający", ZamowieniePubliczne: "Zamówienie publiczne",
  mocodawca: "Mocodawca", pelnomocnicy: "Pełnomocnicy", przelew_bankowy: "Przelew", pelnomocnik: "Pełnomocnik",
  data: "Data pisma", miejscowosc: "Miejscowość", czynnosc_dzien: "Dzień czynności",
  czynnosc_powod_id: "Powód (identyfikator)", czynnosc_opis: "Opis czynności",
  nazwa: "Nazwa", krs: "KRS", nip: "NIP", regon: "REGON", pesel: "PESEL", typ: "Typ podmiotu",
  "przez-pelnomocnika": "Przez pełnomocnika", imie_nazwisko: "Imię i nazwisko", mail: "E-mail",
  prowadzacy_postepowanie: "Prowadzący postępowanie", numer_bzp: "Numer BZP", numer_ted: "Numer TED",
  numer_postepowania: "Numer postępowania", tytul: "Tytuł",
  data_operacji: "Data operacji", kwota: "Kwota", na_rachunek: "Na rachunek", z_rachunku: "Z rachunku",
  numer_transakcji: "Numer transakcji", podpisujacy: "Podpisujący",
};
const BLOKI = {Odwolujacy: "Odwołujący", Zamawiajacy: "Zamawiający", mocodawca: "Mocodawca", pelnomocnicy: "Pełnomocnicy"};
const STRZALKA = (d) => `<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="${d}" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>`;
const etykieta = (k) => ETYKIETY[k] ?? k;
const klucze = (sciezka) => sciezka.replace(/\[\d+\]/g, "").split(".");

let stan = {klasy: [], przyklad: false, sprawa: null, aktywny: 0, pole: null, strona: 1, surowy: false, blad: null, wysylanie: false, ostatnie: null};
let odpytywanie = null;

// ---------- dane ----------

function splaszcz(obj, prefiks = "", wynik = []) {
  if (Array.isArray(obj)) obj.forEach((v, i) => splaszcz(v, `${prefiks}[${i}]`, wynik));
  else if (obj && typeof obj === "object") Object.entries(obj).forEach(([k, v]) => splaszcz(v, prefiks ? `${prefiks}.${k}` : k, wynik));
  else wynik.push([prefiks, obj]);
  return wynik;
}

function dowody(p) {
  const mapa = {};
  (p.audyt?.pola || []).forEach((d, i) => { mapa[d.pole] = {d, poz: p.polozenia?.[i] || null}; });
  return mapa;
}

function grupy(p) {
  const wynik = [];
  for (const [sciezka, wartosc] of splaszcz(p.json || {})) {
    const klucz = sciezka.match(/^[^.]+/)[0];
    let g = wynik.find((x) => x.klucz === klucz);
    if (!g) wynik.push(g = {klucz, nazwa: etykieta(klucz.replace(/\[\d+\]/, "")), pola: []});
    g.pola.push({sciezka, wartosc, reszta: sciezka.slice(klucz.length + 1)});
  }
  return wynik;
}

function nazwaPola(reszta, sciezka) {
  const k = klucze(reszta || sciezka);
  const ost = etykieta(k[k.length - 1]);
  return k.length > 1 && ETYKIETY[k[k.length - 2]] ? `${ETYKIETY[k[k.length - 2]]}: ${ost.toLowerCase()}` : ost;
}

// „NIP · Odwołujący”: nazwa pola i blok, z którego pochodzi (na obrazie strony)
function podpisPola(sciezka) {
  const klucz = sciezka.match(/^[^.]+/)[0];
  const reszta = sciezka.slice(klucz.length + 1);
  return reszta ? `${nazwaPola(reszta, sciezka)} · ${etykieta(klucz.replace(/\[\d+\]/, ""))}` : nazwaPola("", sciezka);
}

function opisPrzeksztalcenia(d, json) {
  const m = d.metoda || "";
  if (m.startsWith("slownik")) {
    const opis = json?.OdwolanieKIO?.czynnosc_opis;
    return opis && !d.pole.endsWith("czynnosc_opis") ? `ze słownika UZP: ${d.wartosc} = ${opis}` : "ze słownika UZP";
  }
  if (m.startsWith("jesli") || m.startsWith("stala")) return "wartość ustalona regułą";
  if (m.startsWith("llm")) return "uzupełnił model (fragment sprawdzony w tekście pisma)";
  if (d.cytat && !zwarte(d.cytat).includes(zwarte(d.wartosc))) {
    if (/^\d{4}-\d{2}-\d{2}$/.test(String(d.wartosc))) return "data zapisana w formacie RRRR-MM-DD";
    if (typeof d.wartosc === "number") return "kwota zapisana jako liczba";
    return "zapisane inaczej niż w piśmie";
  }
  return null;
}

function cytatZZaznaczeniem(d) {
  const cytat = d.cytat, s = String(d.wartosc ?? "");
  const i = s && !/^(slownik|jesli|stala)/.test(d.metoda || "") ? cytat.indexOf(s) : -1;
  if (i < 0) return esc(cytat);
  return esc(cytat.slice(0, i)) + "<mark>" + esc(s) + "</mark>" + esc(cytat.slice(i + s.length));
}

const aktywnyPlik = () => stan.sprawa?.pliki[stan.aktywny];
const api = (sciezka) => `api/sprawa/${encodeURIComponent(stan.sprawa.id)}${sciezka}`;

// ---------- nagłówek, karty plików, podsumowanie ----------

function opisStanuPliku(p) {
  if (p.stan === "oczekuje") return `<span class="typ">czeka w kolejce</span>`;
  if (p.stan === "przetwarzanie") return `<span class="typ">przetwarzanie ${Math.round(p.czas_s)} s z ok. ${p.szacunek_s} s</span>`;
  if (p.stan === "blad") return `<span class="typ blad">błąd</span>`;
  if (!p.klasa) return `<span class="typ obcy">nie dopasowano typu</span>`;
  return `<span class="typ">${esc(nazwaKlasy(p.klasa))}</span>`;
}

function rysujNaglowek() {
  const s = stan.sprawa, lista = $("#lista"), akcje = $("#akcje-sprawy");
  $("#etykieta-wgraj").textContent = s ? "Nowa sprawa" : "Wgraj PDF-y sprawy";
  // ekran startowy ma duży blok wgrywania: przycisk w pasku dopiero przy otwartej sprawie (jako „Nowa sprawa”)
  $("#przycisk-wgraj").style.display = s ? "" : "none";
  if (!s) { lista.hidden = true; akcje.innerHTML = ""; $("#stan-sprawy").textContent = "Dokumenty sprawy odwoławczej KIO na JSON w formacie UZP"; return; }
  const n = s.pliki.length, rozp = s.pliki.filter((p) => p.klasa).length;
  const wToku = s.pliki.filter((p) => p.stan === "oczekuje" || p.stan === "przetwarzanie").length;
  $("#stan-sprawy").textContent = `sprawa: ${n} ${odmiana(n, "plik", "pliki", "plików")}, ${rozp} ${odmiana(rozp, "rozpoznany", "rozpoznane", "rozpoznanych")}${wToku ? `, w trakcie: ${wToku}` : ""}`;
  akcje.innerHTML = (s.gotowa ? `<a class="btn glowny" href="${api("/zip")}" download>Pobierz JSON sprawy (ZIP)</a>`
    : `<span class="btn glowny" aria-disabled="true">Pobierz JSON sprawy (ZIP)</span>`)
    + ` <button type="button" class="btn tekstowy" id="zamknij">Zamknij sprawę</button>`;
  $("#zamknij").addEventListener("click", zamknijSprawe);
  lista.hidden = false;
  lista.innerHTML = s.pliki.map((p, i) => `<button type="button" data-i="${i}" class="${p.stan === "gotowe" && !p.klasa ? "obcy" : ""}"${i === stan.aktywny ? ` aria-current="true"` : ""}>${esc(p.plik)} ${opisStanuPliku(p)}</button>`).join("");
}

function rysujSkrot() {
  const el = $("#skrot");
  const html = stan.sprawa ? kartaSkrotu(stan.sprawa.pliki) : "";
  el.hidden = !html;
  if (el.dataset.html !== html) { el.innerHTML = html; el.dataset.html = html; }
}

// ---------- podgląd strony ----------

function procent(r) {
  return `left:${(r[0] * 100).toFixed(3)}%;top:${(r[1] * 100).toFixed(3)}%;width:${((r[2] - r[0]) * 100).toFixed(3)}%;height:${((r[3] - r[1]) * 100).toFixed(3)}%`;
}

function podgladStrony(p, mapa) {
  const stron = Math.max(1, p.strony || 1), s = Math.min(stan.strona, stron);
  const ocr = (p.audyt?.strony_ocr || p.strony_skan || []).includes(s);
  const wybrany = stan.pole && mapa[stan.pole];
  let ramki = "";
  for (const [sciezka, {d, poz}] of Object.entries(mapa)) {
    if (!poz || poz.strona !== s) continue;
    if (sciezka === stan.pole) continue;
    const r = (poz.wartosc.length ? poz.wartosc : poz.cytat)[0];
    ramki += `<button type="button" class="ramka-pola" tabindex="-1" aria-hidden="true" data-pole="${esc(sciezka)}" title="${esc(podpisPola(sciezka))}" style="${procent(r)}"></button>`;
  }
  if (wybrany?.poz && wybrany.poz.strona === s) {
    const poz = wybrany.poz;
    ramki += poz.cytat.map((r) => `<div class="ramka-cytatu" style="${procent(r)}"></div>`).join("");
    ramki += poz.wartosc.map((r) => `<div class="ramka-wartosci" style="${procent(r)}"></div>`).join("");
    const r0 = (poz.wartosc.length ? poz.wartosc : poz.cytat)[0];
    ramki += `<div class="etykieta-ramki" id="cel" style="left:${(r0[0] * 100).toFixed(3)}%;top:${(r0[1] * 100).toFixed(3)}%">${esc(podpisPola(stan.pole))}</div>`;
  }
  let uwaga = "";
  if (wybrany && !wybrany.poz && wybrany.d.cytat) {
    uwaga = `<p class="uwaga-podgladu" role="note">${ocr ? "Ta strona jest skanem (tekst z OCR), więc nie da się wskazać miejsca na obrazie." : "Nie udało się wskazać miejsca cytatu na obrazie strony."} Cytat ze strony ${wybrany.d.strona ?? "?"}: <q>${esc(wybrany.d.cytat)}</q></p>`;
  }
  return `<section class="podglad" aria-label="Strona ${s} dokumentu">
    <div class="podglad-pasek">
      <button type="button" data-strona="${s - 1}" aria-label="Poprzednia strona"${s <= 1 ? " disabled" : ""}>${STRZALKA("M8 2 4 6l4 4")}</button>
      <b>Strona ${s} z ${stron}</b>
      <button type="button" data-strona="${s + 1}" aria-label="Następna strona"${s >= stron ? " disabled" : ""}>${STRZALKA("M4 2l4 4-4 4")}</button>
      <span>${ocr ? "skan, tekst z OCR" : `obraz strony z pliku PDF${Object.keys(mapa).length ? " · podkreślone = odczytane pola" : ""}`}</span>
    </div>${uwaga}
    <div class="kartka" id="kartka" tabindex="0" aria-label="Obraz strony ${s}">
      <div class="strona-pdf"><img id="obraz" src="${api(`/plik/${p.nr}/strona/${s}.png`)}" alt="Strona ${s} pliku ${esc(p.plik)}">${ramki}</div>
    </div></section>`;
}

// ---------- panel pól ----------

function wierszPola(p, pole, mapa) {
  const {sciezka, wartosc, reszta} = pole;
  const dow = mapa[sciezka], d = dow?.d, wybrany = stan.pole === sciezka;
  const pusty = wartosc === null || wartosc === "";
  const wart = pusty ? `<span class="wart null">brak w dokumencie</span>` : `<span class="wart">${esc(wartosc)}</span>`;
  const strona = d?.strona ? `<span class="s">s. ${d.strona}</span>` : "";
  let szczegoly = "";
  if (wybrany && d?.cytat) {
    const blok = BLOKI[sciezka.match(/^[^[.]+/)[0]];
    szczegoly = `<div class="cytat"><p>Cytat, s. ${d.strona ?? "?"}${blok ? `, wiersz w bloku „${esc(blok)}:”` : ""}${dow.poz ? "" : " (bez zaznaczenia na stronie)"}</p><q>${cytatZZaznaczeniem(d)}</q></div>`;
  } else if (wybrany && !pusty) {
    szczegoly = `<div class="cytat"><p>Bez cytatu: wartość nie pochodzi wprost z tekstu.</p></div>`;
  }
  const przeksz = d && !pusty ? opisPrzeksztalcenia(d, p.json) : null;
  return `<li><button type="button" class="pole" data-pole="${esc(sciezka)}" aria-pressed="${wybrany}"${pusty ? ` aria-disabled="true"` : ""}>
      <span class="linia"><span class="et">${esc(nazwaPola(reszta, sciezka))}</span>${wart}${strona}</span>
      <span class="sciezka">${esc(reszta || sciezka)}</span></button>${szczegoly}
      ${/^llm/.test(d?.metoda || "") && !pusty ? `<p class="przeksz"><b>uzupełnił model</b>: fragment sprawdzony w tekście pisma</p>`
        : przeksz ? `<p class="przeksz"><b>przekształcone:</b> ${esc(przeksz)}</p>` : ""}</li>`;
}

function przyciskiPliku(p) {
  const json = JSON.stringify(p.json || {}, null, 2);
  return {
    przyciski: `<a class="btn glowny" href="${api(`/plik/${p.nr}.json`)}" download="${esc(p.json_nazwa)}">Pobierz ${esc(p.json_nazwa)}</a>
      <button type="button" class="btn tekstowy" id="surowy" aria-expanded="${stan.surowy}" aria-controls="json-surowy">${stan.surowy ? "Ukryj" : "Pokaż"} surowy JSON</button>`,
    surowy: `<pre class="surowy" id="json-surowy"${stan.surowy ? "" : " hidden"}>${esc(json)}</pre>`,
  };
}

function panelRozpoznany(p, mapa) {
  const wszystkie = splaszcz(p.json || {});
  const puste = wszystkie.filter(([, v]) => v === null || v === "");
  const zCytatem = wszystkie.filter(([s]) => mapa[s]?.d?.cytat).length;
  const naStronie = Object.values(mapa).filter((x) => x.poz).length;
  const ocr = p.audyt?.strony_ocr || [];
  const klasa = stan.klasy.find((k) => k.nazwa === p.klasa);
  const {przyciski, surowy} = przyciskiPliku(p);
  const info = `${zCytatem} z ${wszystkie.length} pól ma cytat${naStronie ? `, ${naStronie} zaznaczamy na stronie` : ""}.`
    + (puste.length ? ` Puste: ${esc(puste.map(([s]) => etykieta(klucze(s).pop()).toLowerCase()).join(", "))}.` : "")
    + (ocr.length ? ` Strony ze skanu (OCR): ${ocr.join(", ")}.` : "")
    + " Wybierz pole, żeby zobaczyć je na stronie.";
  return `<section class="panel" aria-labelledby="pola-h">
    <div class="panel-naglowek"><div><p>Rozpoznany typ · ${p.strony} ${odmiana(p.strony, "strona", "strony", "stron")}</p>
      <h1 id="pola-h">${esc(klasa?.opis || nazwaKlasy(p.klasa))}</h1></div>${przyciski}</div>
    ${surowy}<p class="info">${info}</p>
    ${grupy(p).map((g) => `<div class="grupa"><h2>${esc(g.nazwa)} <span class="mono">${esc(g.klucz)}</span></h2>
      <ul class="pola">${g.pola.map((pole) => wierszPola(p, pole, mapa)).join("")}</ul></div>`).join("")}
  </section>`;
}

function panelObcy(p) {
  const kl = p.audyt?.klasyfikacja || {};
  const NARZEDNIK = {odwolanie: "odwołaniem", pelnomocnictwo: "pełnomocnictwem", przelew: "potwierdzeniem przelewu"};
  const nazwy = (stan.klasy.length ? stan.klasy.map((k) => k.nazwa) : Object.keys(NARZEDNIK)).map((k) => NARZEDNIK[k] || nazwaKlasy(k));
  const powod = (k) => {
    const ujemne = (kl.trafienia?.[k] || []).filter((t) => t.startsWith("tytul_ujemne"));
    if (ujemne.length) return "wykluczone przez tytuł pisma";
    const pkt = kl.punkty?.[k];
    return pkt > 0 ? `${pkt} pkt, za mało do rozpoznania` : "brak cech tego pisma";
  };
  const {surowy} = przyciskiPliku(p);
  return `<section class="panel" aria-labelledby="obcy-h">
    <div class="ramka-stanu obcy"><p class="obcy-tekst">Nie dopasowano typu</p>
      <h1 id="obcy-h">To pismo nie jest ${esc(nazwy.join(", ").replace(/, ([^,]*)$/, " ani $1"))}. Format UZP wymaga wtedy pustego wyniku.</h1>
      <p><span class="kod">{}</span> <a class="btn" href="${api(`/plik/${p.nr}.json`)}" download="${esc(p.json_nazwa)}">Pobierz ${esc(p.json_nazwa)}</a></p></div>
    ${surowy}<p class="info">Rozpoznanie</p>
    <ol class="rozpoznanie">${Object.keys(kl.punkty || {}).map((k) => `<li><span><b>${esc(nazwaKlasy(k))}</b></span><span>${esc(powod(k))}</span></li>`).join("")}</ol>
    <p class="info">Rodzaje pism opisuje konfiguracja (pliki YAML w <span class="mono">config/klasy</span>), nie kod.</p>
  </section>`;
}

function panelBledu(p) {
  return `<section class="panel" aria-labelledby="blad-h"><div class="ramka-stanu blad"><p class="blad-tekst">Błąd pliku</p>
    <h1 id="blad-h">${esc(p.plik)}</h1><p>${esc(p.blad || "Nie udało się przetworzyć pliku")}. Pozostałe pliki sprawy działają.</p></div></section>`;
}

function panelPostepu(s) {
  const p = aktywnyPlik();
  const pozycje = s.pliki.map((x) => {
    const proc = x.stan === "gotowe" || x.stan === "blad" ? 100 : x.stan === "przetwarzanie" ? Math.min(95, Math.round(100 * x.czas_s / x.szacunek_s)) : 0;
    const skan = x.strony_skan?.length ? `, ${x.strony_skan.length} ze skanu (OCR ok. 12 s na stronę)` : "";
    const opis = {oczekuje: "czeka w kolejce", przetwarzanie: `${Math.round(x.czas_s)} s z ok. ${x.szacunek_s} s`, gotowe: "gotowe", blad: "błąd"}[x.stan];
    return `<li><span class="n">${esc(x.plik)}</span><span>${x.strony} ${odmiana(x.strony, "strona", "strony", "stron")}${skan}</span>
      <span>${opis}</span><progress max="100" value="${proc}" aria-label="Postęp ${esc(x.plik)}">${proc}%</progress></li>`;
  }).join("");
  return `<section class="panel postep" aria-labelledby="postep-h"><h1 id="postep-h">Przetwarzam ${esc(p.plik)}</h1>
    <p role="status">${p.stan === "oczekuje" ? "Plik czeka na swoją kolej." : "Odczyt tekstu, rozpoznanie typu i odczyt pól."} Gotowe pliki można już oglądać.</p>
    <ol>${pozycje}</ol></section>`;
}

// ---------- ekran startowy ----------

function ekranStartowy() {
  const nazwy = stan.klasy.length ? stan.klasy.map((k) => k.opis || k.nazwa) : ["odwołanie", "pełnomocnictwo", "potwierdzenie przelewu"];
  return `<section class="start" aria-labelledby="start-h">
    <h1 id="start-h">Wgraj PDF-y jednej sprawy odwoławczej</h1>
    <p>Aplikacja rozpozna rodzaj każdego pisma, odczyta dane w formacie UZP i pokaże każde pole na stronie dokumentu. Skany też (odczyt trwa ok. 12 s na stronę).</p>
    <div class="upusc" id="upusc"><p>Przeciągnij tu pliki PDF albo</p>
      <label class="btn glowny">Wybierz pliki z dysku<input id="pliki-start" class="sr" type="file" multiple accept=".pdf,application/pdf"></label></div>
    ${stan.przyklad ? `<p><button type="button" class="btn" id="przyklad">Pokaż na przykładowej sprawie (4 pliki)</button></p>` : ""}
    <p class="opis">Obsługiwane rodzaje pism: ${esc(nazwy.join(", "))}. Inne pisma dostają pusty wynik <span class="mono">{}</span>, zgodnie z formatem UZP.</p>
  </section>`;
}

// ---------- rysowanie ----------

function rysujMain() {
  const main = $("#main"), s = stan.sprawa;
  $("#komunikat").innerHTML = stan.blad ? `<section class="blad-zapytania" aria-labelledby="blad-zap"><h2 id="blad-zap" tabindex="-1">Nie udało się przetworzyć plików</h2><p>${esc(stan.blad)}</p>
    ${stan.ostatnie ? `<button type="button" class="btn glowny" id="ponow">Spróbuj ponownie</button>` : ""}</section>` : "";
  if (stan.blad && stan.ostatnie) $("#ponow").addEventListener("click", () => wyslij(stan.ostatnie));
  if (!s) {
    main.innerHTML = stan.wysylanie ? `<section class="start"><p role="status">Wysyłam pliki…</p></section>` : ekranStartowy();
    podepnijStart();
    return;
  }
  const p = aktywnyPlik();
  const mapa = p.stan === "gotowe" ? dowody(p) : {};
  let panel;
  if (p.stan === "oczekuje" || p.stan === "przetwarzanie") panel = panelPostepu(s);
  else if (p.stan === "blad") panel = panelBledu(p);
  else if (!p.klasa) panel = panelObcy(p);
  else panel = panelRozpoznany(p, mapa);
  const pokazStrone = p.strony > 0 && p.stan !== "oczekuje" && p.stan !== "przetwarzanie";
  // Z33: komunikaty serwera (dzienny limit modelu, długi skan czytany do strony N)
  const uwagi = (p.uwagi || []).map(u => `<p class="uwaga-podgladu" role="note">${esc(u)}</p>`).join("")
    + (s.gotowa && s.zapis ? `<p class="uwaga-podgladu" role="status">Zapisano do ${esc(s.zapis.katalog)} (${s.zapis.pliki} plików).</p>` : "");
  main.innerHTML = `${uwagi}<div class="stol">${pokazStrone ? podgladStrony(p, mapa) : ""}${panel}</div>`;
  przewinDoCelu();
}

function przewinDoCelu() {
  const img = $("#obraz"), cel = $("#cel"), kartka = $("#kartka");
  if (!img || !cel || !kartka) return;
  const przewin = () => { kartka.scrollTop = Math.max(0, cel.offsetTop - kartka.clientHeight / 3); };
  img.complete ? przewin() : img.addEventListener("load", przewin, {once: true});
}

// Stan w adresie (#sprawa=…&plik=…&pole=…): odświeżenie strony nie gubi sprawy, a link wskazuje pole
let adresStartowy = location.hash;  // czytany przy starcie, zanim pierwsze rysowanie nadpisze adres

function zapiszAdres() {
  if (adresStartowy) return;
  const s = stan.sprawa;
  const h = s ? `#sprawa=${encodeURIComponent(s.id)}&plik=${stan.aktywny}${stan.pole ? `&pole=${encodeURIComponent(stan.pole)}` : ""}${stan.strona > 1 ? `&strona=${stan.strona}` : ""}` : "";
  if (location.hash !== h) history.replaceState(null, "", h || location.pathname + location.search);
}

async function wczytajZAdresu() {
  const h = new URLSearchParams(adresStartowy.slice(1));
  adresStartowy = "";
  if (!h.get("sprawa")) return;
  try {
    const sprawa = await zapytanie(`api/sprawa/${encodeURIComponent(h.get("sprawa"))}`);
    const nr = Math.min(Math.max(0, +h.get("plik") || 0), sprawa.pliki.length - 1);
    stan = {...stan, sprawa, aktywny: nr, pole: h.get("pole"), strona: +h.get("strona") || 1};
    const p = sprawa.pliki[nr], dow = stan.pole && p.stan === "gotowe" ? dowody(p)[stan.pole] : null;
    if (dow && !h.get("strona")) stan.strona = dow.poz?.strona || dow.d.strona || 1;
    rysuj();
    odpytuj();
  } catch (e) {
    stan = {...stan, blad: e.message};
    rysuj();
  }
}

function rysuj() {
  zapiszAdres();
  rysujNaglowek();
  rysujSkrot();
  rysujMain();
}

// zDokumentu: wybór z obrazu strony albo z podsumowania (bez przełączania zaznaczenia, z przewinięciem listy pól)
function wybierzPole(sciezka, nr = stan.aktywny, zDokumentu = false) {
  const p = stan.sprawa?.pliki[nr];
  if (!p || p.stan !== "gotowe") return;
  const odznacz = !zDokumentu && stan.pole === sciezka && nr === stan.aktywny;
  if (nr !== stan.aktywny) stan.surowy = false;
  stan.aktywny = nr;
  stan.pole = odznacz ? null : sciezka;
  const dow = dowody(p)[sciezka];
  if (stan.pole && dow) stan.strona = dow.poz?.strona || dow.d.strona || stan.strona;
  rysuj();
  const przycisk = document.querySelector(`.pole[data-pole="${CSS.escape(sciezka)}"]`);
  if (przycisk) { przycisk.focus({preventScroll: true}); if (zDokumentu) przycisk.scrollIntoView({block: "center"}); }
}

function wybierzPlik(i) {
  stan.aktywny = i; stan.pole = null; stan.strona = 1; stan.surowy = false;
  rysuj();
}

// ---------- komunikacja z serwerem ----------

async function zapytanie(url, opcje) {
  const r = await fetch(url, opcje);
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch (_) { /* odpowiedź bez JSON */ }
    throw new Error(detail);
  }
  return r.json();
}

function nowaSprawa(sprawa) {
  stan = {...stan, sprawa, aktywny: 0, pole: null, strona: 1, surowy: false, blad: null, wysylanie: false};
  rysuj();
  odpytuj();
}

async function wyslij(pliki) {
  if (!pliki?.length) return;
  const lista = [...pliki];
  stan = {...stan, wysylanie: true, blad: null, ostatnie: lista, sprawa: null};
  rysuj();
  const fd = new FormData();
  lista.forEach((p) => fd.append("pliki", p));
  try {
    nowaSprawa(await zapytanie("api/sprawa", {method: "POST", body: fd}));
  } catch (e) {
    stan = {...stan, wysylanie: false, blad: e.message || "Błąd połączenia z serwerem"};
    rysuj();
    $("#blad-zap")?.focus();
  }
}

async function uruchomPrzyklad() {
  stan = {...stan, wysylanie: true, blad: null, ostatnie: null, sprawa: null};
  rysuj();
  try { nowaSprawa(await zapytanie("api/sprawa/przyklad", {method: "POST"})); }
  catch (e) { stan = {...stan, wysylanie: false, blad: e.message}; rysuj(); }
}

function podpis(s) { return s.pliki.map((p) => `${p.stan}:${p.klasa}`).join("|"); }

function odpytuj() {
  clearTimeout(odpytywanie);
  if (!stan.sprawa || stan.sprawa.gotowa) return;
  odpytywanie = setTimeout(async () => {
    const id = stan.sprawa?.id;
    try {
      const nowa = await zapytanie(`api/sprawa/${encodeURIComponent(id)}`);
      if (stan.sprawa?.id !== id) return;
      const zmiana = podpis(nowa) !== podpis(stan.sprawa);
      const p = nowa.pliki[stan.aktywny];
      stan = {...stan, sprawa: nowa};
      rysujNaglowek();
      rysujSkrot();
      if (zmiana || p.stan === "oczekuje" || p.stan === "przetwarzanie") rysujMain();
    } catch (e) {
      stan = {...stan, blad: e.message};
      rysujMain();
      return;
    }
    odpytuj();
  }, 1000);
}

async function zamknijSprawe() {
  const id = stan.sprawa?.id;
  stan = {...stan, sprawa: null, pole: null, aktywny: 0, blad: null};
  rysuj();
  if (id) fetch(`api/sprawa/${encodeURIComponent(id)}`, {method: "DELETE"}).catch(() => {});
  $("#main").focus();
}

// ---------- zdarzenia ----------

function podepnijStart() {
  const input = $("#pliki-start"), strefa = $("#upusc");
  if (input) input.addEventListener("change", (e) => wyslij(e.target.files));
  $("#przyklad")?.addEventListener("click", uruchomPrzyklad);
  if (!strefa) return;
  ["dragenter", "dragover"].forEach((t) => strefa.addEventListener(t, (e) => { e.preventDefault(); strefa.classList.add("nad"); }));
  ["dragleave", "drop"].forEach((t) => strefa.addEventListener(t, () => strefa.classList.remove("nad")));
  strefa.addEventListener("drop", (e) => { e.preventDefault(); wyslij([...e.dataTransfer.files].filter((f) => /\.pdf$/i.test(f.name))); });
}

document.addEventListener("click", (e) => {
  const t = e.target.closest("button, a");
  if (!t) return;
  if (t.matches("#lista button[data-i]")) wybierzPlik(+t.dataset.i);
  else if (t.matches(".pole") && t.getAttribute("aria-disabled") !== "true") wybierzPole(t.dataset.pole);
  else if (t.matches(".ramka-pola")) wybierzPole(t.dataset.pole, stan.aktywny, true);
  else if (t.matches(".odsylacz")) { wybierzPole(t.dataset.pole, +t.dataset.nr, true); }
  else if (t.matches("[data-strona]")) { stan.strona = +t.dataset.strona; zapiszAdres(); rysujMain(); $(`[data-strona]:not(:disabled)`)?.focus(); }
  else if (t.id === "surowy") { stan.surowy = !stan.surowy; rysujMain(); $("#surowy").focus(); }
});

document.addEventListener("keydown", (e) => {
  const t = e.target;
  if (t.matches?.(".pole") && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
    const wszystkie = [...document.querySelectorAll(".pole")];
    const i = wszystkie.indexOf(t) + (e.key === "ArrowDown" ? 1 : -1);
    if (wszystkie[i]) { e.preventDefault(); wszystkie[i].focus(); }
  } else if (t.matches?.("#lista button") && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
    const n = stan.sprawa.pliki.length, i = (stan.aktywny + (e.key === "ArrowRight" ? 1 : -1) + n) % n;
    e.preventDefault();
    wybierzPlik(i);
    $(`#lista button[data-i="${i}"]`).focus();
  }
});

$("#pliki").addEventListener("change", (e) => { wyslij(e.target.files); e.target.value = ""; });
fetch("api/klasy").then((r) => r.json()).then((k) => { stan.klasy = k; if (!stan.sprawa) rysujMain(); }).catch(() => {});
fetch("api/przyklad").then((r) => r.json()).then((p) => { stan.przyklad = p.dostepny; if (!stan.sprawa) rysujMain(); }).catch(() => {});
rysuj();
wczytajZAdresu();
