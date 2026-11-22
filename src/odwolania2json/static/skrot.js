// Wspólne narzędzia i karta „Sprawa w skrócie” (prostym językiem, z odsyłaczami do pól w dokumentach).
"use strict";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const odmiana = (n, a, b, c) => n === 1 ? a : (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) ? b : c;
const NAZWY_KLAS = {odwolanie: "odwołanie", pelnomocnictwo: "pełnomocnictwo", przelew: "przelew"};
const nazwaKlasy = (k) => NAZWY_KLAS[k] || String(k || "").replace(/_/g, " ");
const zwarte = (s) => String(s ?? "").replace(/[\s\-–—]/g, "").toLowerCase();

const IKONA_OK = `<svg class="ok" aria-hidden="true" width="16" height="16" viewBox="0 0 16 16"><path d="M2.5 8.5 6.5 12.5 13.5 3.5" fill="none" stroke="currentColor" stroke-width="2"/></svg>`;
const IKONA_UWAGA = `<svg class="uwaga" aria-hidden="true" width="18" height="16" viewBox="0 0 18 16"><path d="M9 1 17 15H1Z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M9 6v4M9 12v1" stroke="currentColor" stroke-width="2"/></svg>`;

function data(d) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(d || ""));
  return m ? `${m[3]}.${m[2]}.${m[1]}` : String(d || "");
}

function kwota(k) {
  const n = Number(k);
  return Number.isFinite(n) ? n.toLocaleString("pl-PL", {minimumFractionDigits: 2, maximumFractionDigits: 2}) + " zł" : String(k);
}

// Wartość pola po ścieżce „Odwolujacy[0].pelnomocnik.mail”
function wartoscSciezki(obj, sciezka) {
  return sciezka.split(/\.|\[|\]/).filter(Boolean).reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

// Pierwszy gotowy plik, którego JSON ma daną ścieżkę z wartością
function znajdz(pliki, sciezka) {
  for (const p of pliki) {
    if (p.stan !== "gotowe" || !p.json) continue;
    const v = wartoscSciezki(p.json, sciezka);
    if (v !== undefined && v !== null && v !== "") return {nr: p.nr, pole: sciezka, v};
  }
  return null;
}

function odsylacz(ref, tekst = "pokaż w dokumencie") {
  return ref ? `<button type="button" class="odsylacz" data-nr="${ref.nr}" data-pole="${esc(ref.pole)}">${esc(tekst)}</button>` : "";
}

function pozycja(etykieta, tresc) {
  return `<div><dt>${esc(etykieta)}</dt><dd>${tresc}</dd></div>`;
}

function kontroleSprawy(pliki, f) {
  const wynik = [];
  const ok = (t) => wynik.push(`<li>${IKONA_OK}<span>${t}</span></li>`);
  const uwaga = (t) => wynik.push(`<li>${IKONA_UWAGA}<span><b>Do sprawdzenia:</b> ${t}</span></li>`);
  if (f.nipOdw && f.nipMoc) {
    zwarte(f.nipOdw.v) === zwarte(f.nipMoc.v) ? ok("Pełnomocnictwo udzielił odwołujący (ten sam NIP w obu pismach).")
      : uwaga(`NIP mocodawcy w pełnomocnictwie (${esc(f.nipMoc.v)}) różni się od NIP odwołującego (${esc(f.nipOdw.v)}).`);
  }
  if (f.pelnOdw && f.pelnomocnicy.length) {
    const jest = f.pelnomocnicy.some((n) => zwarte(n) === zwarte(f.pelnOdw.v));
    jest ? ok(`Pełnomocnik z odwołania (${esc(f.pelnOdw.v)}) jest wymieniony w pełnomocnictwie.`)
      : uwaga(`pełnomocnika z odwołania (${esc(f.pelnOdw.v)}) nie ma w pełnomocnictwie.`);
  }
  if (f.przezPeln && Number(f.przezPeln.v) === 1 && !f.jestPelnomocnictwo) uwaga("odwołanie złożył pełnomocnik, a w sprawie nie ma pełnomocnictwa.");
  if (f.odw && !f.kwota) uwaga("w sprawie nie ma potwierdzenia przelewu wpisu.");
  if (f.kwota && f.numer && f.tytulPrzelewu) {
    zwarte(f.tytulPrzelewu.v).includes(zwarte(f.numer.v)) ? ok(`Tytuł przelewu wskazuje to postępowanie (${esc(f.numer.v)}).`)
      : uwaga(`tytuł przelewu nie zawiera numeru postępowania ${esc(f.numer.v)}.`);
  }
  return wynik;
}

function kartaSkrotu(pliki) {
  const gotowe = pliki.filter((p) => p.stan === "gotowe");
  if (!gotowe.length) return "";
  const f = {
    odw: znajdz(pliki, "Odwolujacy[0].nazwa"), nipOdw: znajdz(pliki, "Odwolujacy[0].nip"), krsOdw: znajdz(pliki, "Odwolujacy[0].krs"),
    zam: znajdz(pliki, "Zamawiajacy[0].nazwa"), numer: znajdz(pliki, "ZamowieniePubliczne.numer_postepowania"),
    tytul: znajdz(pliki, "ZamowieniePubliczne.tytul"), czynnosc: znajdz(pliki, "OdwolanieKIO.czynnosc_opis"),
    dzien: znajdz(pliki, "OdwolanieKIO.czynnosc_dzien"), dataOdw: znajdz(pliki, "OdwolanieKIO.data"),
    miejsc: znajdz(pliki, "OdwolanieKIO.miejscowosc"),
    kwota: znajdz(pliki, "przelew_bankowy.kwota"), dataPrz: znajdz(pliki, "przelew_bankowy.data_operacji"),
    tytulPrzelewu: znajdz(pliki, "przelew_bankowy.tytul"),
    pelnOdw: znajdz(pliki, "Odwolujacy[0].pelnomocnik.imie_nazwisko"), kancelaria: znajdz(pliki, "Odwolujacy[0].pelnomocnik.nazwa"),
    przezPeln: znajdz(pliki, "Odwolujacy[0].przez-pelnomocnika"), pelnPel: znajdz(pliki, "pelnomocnicy[0].imie_nazwisko"),
    nipMoc: znajdz(pliki, "mocodawca[0].data.nip"),
  };
  f.pelnomocnicy = gotowe.flatMap((p) => (p.json?.pelnomocnicy || []).map((x) => x?.imie_nazwisko).filter(Boolean));
  f.jestPelnomocnictwo = gotowe.some((p) => Array.isArray(p.json?.pelnomocnicy) || Array.isArray(p.json?.mocodawca));
  const czeka = pliki.some((p) => p.stan === "oczekuje" || p.stan === "przetwarzanie");
  const brak = `<span class="opis">${czeka ? "czeka na przetworzenie plików" : "nie odczytano"}</span>`;

  const odw = f.odw ? `<span class="duzy">${esc(f.odw.v)}</span><span class="dod">${[f.nipOdw && `NIP ${esc(f.nipOdw.v)}`, f.krsOdw && `KRS ${esc(f.krsOdw.v)}`].filter(Boolean).join(", ")}</span>${odsylacz(f.odw)}` : brak;
  const zam = f.zam ? `<span class="duzy">${esc(f.zam.v)}</span>${f.numer ? `<span class="dod">postępowanie ${esc(f.numer.v)}</span>` : ""}${odsylacz(f.zam)}` : brak;
  const czego = f.czynnosc || f.tytul
    ? `${f.czynnosc ? `<span class="duzy">${esc(f.czynnosc.v)}</span>` : ""}${f.dzien ? `<span class="dod">czynność zamawiającego z ${esc(data(f.dzien.v))}</span>` : ""}${f.tytul ? `<span class="dod">zamówienie: „${esc(f.tytul.v)}”</span>` : ""}${odsylacz(f.czynnosc || f.tytul)}`
    : brak;
  const wpis = f.kwota
    ? `<span class="duzy">${esc(kwota(f.kwota.v))}</span><span class="dod">opłacono przelewem${f.dataPrz ? ` ${esc(data(f.dataPrz.v))}` : ""}</span>${odsylacz(f.kwota)}`
    : `<span class="duzy obcy-tekst">nie opłacono?</span><span class="dod">w sprawie nie ma potwierdzenia przelewu</span>`;
  const kto = f.pelnOdw || f.pelnPel;
  const pelnomocnik = kto
    ? `<span class="duzy">${esc(kto.v)}</span>${f.kancelaria ? `<span class="dod">${esc(f.kancelaria.v)}</span>` : ""}<span class="dod">pełnomocnictwo w sprawie: ${f.jestPelnomocnictwo ? "jest" : "<b>brak</b>"}</span>${odsylacz(kto)}`
    : (f.przezPeln && Number(f.przezPeln.v) === 0 ? "odwołujący działa sam, bez pełnomocnika" : brak);

  const rozpoznane = gotowe.filter((p) => p.klasa);
  const obce = gotowe.filter((p) => !p.klasa);
  const bledy = pliki.filter((p) => p.stan === "blad");
  const wTrakcie = pliki.filter((p) => p.stan === "oczekuje" || p.stan === "przetwarzanie");
  const dokumenty = `<span class="duzy">${pliki.length} ${odmiana(pliki.length, "plik", "pliki", "plików")}</span>
    <span class="dod">${rozpoznane.length ? esc(rozpoznane.map((p) => nazwaKlasy(p.klasa)).join(", ")) : "żaden nie rozpoznany"}</span>
    ${obce.length ? `<span class="dod obcy-tekst">nierozpoznane (wynik <span class="mono">{}</span>): ${esc(obce.map((p) => p.plik).join(", "))}</span>` : ""}
    ${bledy.length ? `<span class="dod blad-tekst">błąd: ${esc(bledy.map((p) => p.plik).join(", "))}</span>` : ""}
    ${wTrakcie.length ? `<span class="dod">w trakcie: ${wTrakcie.length}</span>` : ""}`;

  const kontrole = kontroleSprawy(pliki, f);
  const naglowek = f.odw && f.kwota
    ? `Odwołanie ${esc(f.odw.v)}${f.dataOdw ? ` z ${esc(data(f.dataOdw.v))}` : ""}${f.miejsc ? ` (${esc(f.miejsc.v)})` : ""}, wpis ${esc(kwota(f.kwota.v))} opłacony.`
    : `Dane odczytane z ${rozpoznane.length} ${odmiana(rozpoznane.length, "pisma", "pism", "pism")}.`;
  return `<div class="skrot-naglowek"><h2 id="skrot-h">Sprawa w skrócie</h2><span class="opis">${naglowek}</span></div>
    <dl>${pozycja("Odwołujący", odw)}${pozycja("Zamawiający", zam)}${pozycja("Czego dotyczy", czego)}
    ${pozycja("Wpis od odwołania", wpis)}${pozycja("Pełnomocnik", pelnomocnik)}${pozycja("Dokumenty w sprawie", dokumenty)}</dl>
    ${kontrole.length ? `<ul class="kontrole" aria-label="Zgodność dokumentów">${kontrole.join("")}</ul>` : ""}`;
}
