# -*- coding: utf-8 -*-
"""Czytanie wykazu roboczego (pierwsza zakladka) -> lista pozycji BLACHA.

Zasady (z /wykaz-roboczy i EKSTRAKTOR_DXF V3):
  * kolumny szukamy PO NAGLOWKU, nie po literze; przy duplikacie wygrywa
    kolumna NAJBARDZIEJ Z LEWEJ (rozbicie 'Bezeichnung' kopiuje naglowek w prawo),
  * wiersz naglowka = wiersz z najwieksza liczba wypelnionych komorek (skan 15),
  * zakres = ZAKUPY zawiera 'blach' (case-insensitive),
  * NAZWA/ZAKUPY bywaja FORMULAMI - czytamy data_only=True (cache Excela);
    gdy cache pusty, mowimy o tym GLOSNO zamiast wgrywac puste referencje.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

from .wspolne import do_liczby, norm_naglowek, rozbierz_referencje, sciezka

MAPOWANIE = json.loads((Path(__file__).resolve().parent.parent / "mapowanie.json")
                       .read_text(encoding="utf-8"))
ALIASY = MAPOWANIE["kolumny"]


@dataclass
class Pozycja:
    wiersz: int
    ref: str = ""                 # referencja = nazwa produktu w LANTEKU
    zeinr: str = ""
    posn: str = ""
    ilosc: float | None = None    # z kolumny ilosci
    ilosc_ref: int | None = None  # z czlonu 'Nst' referencji
    grubosc_kol: float | None = None   # kolumna grubosc_poprawiona (bywa jej brak)
    gatunek_kol: str = ""              # kolumna gatunek_poprawiony (bywa jej brak)
    grubosc_ref: float | None = None   # 1. czlon referencji
    gatunek_ref: str = ""              # 2. czlon referencji
    zrodlo: str = "referencja"         # ktore zrodlo obowiazuje: referencja | kolumny
    kod_kolumna: str = ""         # kolumna 'Giecie'
    kod_ref: str | None = None    # technologia odczytana z referencji
    sprawdzenie: str = ""
    propozycja: str = ""
    indeks: str = ""
    bezeichnung: str = ""
    uwagi: list = field(default_factory=list)

    @property
    def kod(self) -> str:
        """Do marszruty bierzemy kod Z REFERENCJI - to ona idzie do LANTEKA."""
        zrodlo = self.kod_ref if self.kod_ref is not None else self.kod_kolumna
        return (zrodlo or "").strip().upper()

    @property
    def grubosc(self):
        """Obowiazujaca grubosc. Domyslnie z referencji; gdy jej brak - z kolumny."""
        if self.zrodlo == "kolumny":
            return self.grubosc_kol if self.grubosc_kol is not None else self.grubosc_ref
        return self.grubosc_ref if self.grubosc_ref is not None else self.grubosc_kol

    @property
    def gatunek(self) -> str:
        """Obowiazujacy gatunek. Domyslnie z referencji; gdy jej brak - z kolumny."""
        if self.zrodlo == "kolumny":
            return self.gatunek_kol or self.gatunek_ref or ""
        return self.gatunek_ref or self.gatunek_kol or ""

    @property
    def rozjazd_grubosci(self) -> bool:
        return (self.grubosc_kol is not None and self.grubosc_ref is not None
                and abs(float(self.grubosc_kol) - float(self.grubosc_ref)) > 0.001)

    @property
    def rozjazd_gatunku(self) -> bool:
        a = (self.gatunek_kol or "").replace(" ", "").upper()
        b = (self.gatunek_ref or "").replace(" ", "").upper()
        return bool(a and b and a != b)


@dataclass
class Wykaz:
    plik: str
    zakladka: str
    wiersz_naglowka: int
    naglowki: dict                 # indeks kolumny -> tekst
    kolumny: dict                  # rola -> indeks
    kandydaci_nazwy: dict          # naglowek -> indeks
    pozycje: list                  # Pozycja (tylko BLACHA)
    wierszy: int
    blacha: int
    kolumna_nazwy: str = ""
    kolumna_ilosci: str = ""
    formuly_puste: int = 0         # ile referencji puste mimo formuly


def _mapa_naglowkow(hdr):
    poz = {}
    for i, h in enumerate(hdr):
        k = norm_naglowek(h)
        if k:
            poz.setdefault(k, i)           # LEWA wygrywa
    return poz


def _znajdz(poz, aliasy):
    """Pierwszy alias z listy, ktory ma trafienie; w razie kilku - lewa kolumna."""
    for a in aliasy:
        ka = norm_naglowek(a)
        traf = [i for k, i in poz.items() if k == ka]
        if not traf:
            traf = [i for k, i in poz.items() if k.startswith(ka)]
        if traf:
            return min(traf)
    return None


def _wiersz_naglowka(ws, limit=15):
    najlepszy, ile_najlepszy = 1, -1
    for nr, row in enumerate(ws.iter_rows(min_row=1, max_row=limit, values_only=True), start=1):
        ile = sum(1 for c in row if c not in (None, ""))
        if ile > ile_najlepszy:
            najlepszy, ile_najlepszy = nr, ile
    return najlepszy


def _txt(v) -> str:
    return "" if v is None else str(v).strip()


def wczytaj(plik, kolumna_nazwy: str | None = None, kolumna_ilosci: str | None = None,
            zrodlo: str = "referencja") -> Wykaz:
    """kolumna_nazwy / kolumna_ilosci: tekst naglowka wskazany przez uzytkownika
    (None = wybor automatyczny wg mapowania).

    zrodlo: skad brac grubosc i gatunek - 'referencja' (domyslnie) albo 'kolumny'.
    Referencja niesie oba czlony zawsze i to ona idzie do LANTEKA; kolumny
    kontrolne istnieja tylko w wykazach zrobionych przez /wykaz-roboczy.
    """
    p = sciezka(plik)
    wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    nr_hdr = _wiersz_naglowka(ws)
    rows = ws.iter_rows(min_row=nr_hdr, values_only=True)
    hdr = next(rows)
    poz = _mapa_naglowkow(hdr)
    naglowki = {i: _txt(h) for i, h in enumerate(hdr) if h is not None}

    kol = {rola: _znajdz(poz, al) for rola, al in ALIASY.items()}

    # kandydaci na kolumne referencji: kazda kolumna, ktorej naglowek zaczyna sie od 'nazwa'
    kandydaci = {naglowki[i]: i for k, i in poz.items()
                 if k.startswith("nazwa") and i in naglowki}
    if kolumna_nazwy and kolumna_nazwy in kandydaci:
        kol["nazwa"] = kandydaci[kolumna_nazwy]
    if kolumna_ilosci:
        for i, h in naglowki.items():
            if h == kolumna_ilosci:
                kol["ilosc"] = i
                break

    brak = [r for r in ("zakupy", "nazwa") if kol.get(r) is None]
    if brak:
        wb.close()
        raise ValueError("w wykazie brak kolumn: %s (pierwsza zakladka '%s', "
                         "wiersz naglowka %d)" % (", ".join(brak), ws.title, nr_hdr))
    i_zak, i_naz = kol["zakupy"], kol["nazwa"]

    def g(r, rola):
        i = kol.get(rola)
        return r[i] if i is not None and i < len(r) else None

    pozycje, n = [], 0
    for nr, r in enumerate(rows, start=nr_hdr + 1):
        n += 1
        z = _txt(r[i_zak] if i_zak < len(r) else None).lower()
        if "blach" not in z:
            continue
        ref = _txt(r[i_naz] if i_naz < len(r) else None)
        rozb = rozbierz_referencje(ref)
        pozycje.append(Pozycja(
            wiersz=nr, ref=ref,
            zeinr=_txt(g(r, "zeinr")) or (rozb["zeinr"] or ""),
            posn=_txt(g(r, "posn")) or (rozb["posn"] or ""),
            ilosc=do_liczby(g(r, "ilosc")),
            ilosc_ref=rozb["ilosc"],
            grubosc_kol=do_liczby(g(r, "grubosc")),
            gatunek_kol=_txt(g(r, "gatunek")),
            grubosc_ref=rozb["grubosc"],
            gatunek_ref=rozb["gatunek"] or "",
            zrodlo=zrodlo,
            kod_kolumna=_txt(g(r, "giecie")),
            kod_ref=rozb["technologia"],
            sprawdzenie=_txt(g(r, "sprawdzenie")),
            propozycja=_txt(g(r, "propozycja")),
            indeks=_txt(g(r, "index")),
            bezeichnung=_txt(g(r, "bezeichnung")),
        ))
    wb.close()

    w = Wykaz(plik=str(p), zakladka=ws.title, wiersz_naglowka=nr_hdr, naglowki=naglowki,
              kolumny=kol, kandydaci_nazwy=kandydaci, pozycje=pozycje,
              wierszy=n, blacha=len(pozycje),
              kolumna_nazwy=naglowki.get(i_naz, ""),
              kolumna_ilosci=naglowki.get(kol.get("ilosc"), ""))

    # czy puste referencje biora sie z nieprzeliczonej formuly?
    if any(not x.ref for x in pozycje):
        w.formuly_puste = _policz_formuly(p, nr_hdr, i_naz,
                                          {x.wiersz for x in pozycje if not x.ref})
    return w


def _policz_formuly(p, nr_hdr, i_naz, wiersze) -> int:
    """openpyxl nie liczy formul; jesli w komorce siedzi '=' a cache jest pusty,
    to znaczy ze wykaz nie zostal przeliczony/zapisany w Excelu."""
    try:
        wb = openpyxl.load_workbook(str(p), read_only=True, data_only=False)
        ws = wb.worksheets[0]
        ile = 0
        for nr, r in enumerate(ws.iter_rows(min_row=nr_hdr + 1, values_only=True),
                               start=nr_hdr + 1):
            if nr in wiersze and i_naz < len(r) and isinstance(r[i_naz], str) \
                    and r[i_naz].startswith("="):
                ile += 1
        wb.close()
        return ile
    except Exception:
        return 0


def kandydaci_nazwy_wg_dxf(plik, nazwy_dxf) -> list:
    """Ile referencji z kazdej kolumny 'Nazwa*' trafia w pliki DXF - podpowiedz dla UI."""
    p = sciezka(plik)
    wb = openpyxl.load_workbook(str(p), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    nr_hdr = _wiersz_naglowka(ws)
    rows = ws.iter_rows(min_row=nr_hdr, values_only=True)
    hdr = next(rows)
    poz = _mapa_naglowkow(hdr)
    naglowki = {i: _txt(h) for i, h in enumerate(hdr) if h is not None}
    i_zak = _znajdz(poz, ALIASY["zakupy"])
    kand = {i: naglowki[i] for k, i in poz.items() if k.startswith("nazwa") and i in naglowki}
    licz = {i: 0 for i in kand}
    wypelnione = {i: 0 for i in kand}
    male = {str(n).lower() for n in nazwy_dxf}
    for r in rows:
        if i_zak is None or i_zak >= len(r):
            continue
        if "blach" not in _txt(r[i_zak]).lower():
            continue
        for i in kand:
            if i < len(r):
                v = _txt(r[i])
                if v:
                    wypelnione[i] += 1
                    if v.lower() in male:
                        licz[i] += 1
    wb.close()
    return sorted(({"kolumna": kand[i], "indeks": i, "trafien": licz[i],
                    "wypelnionych": wypelnione[i]} for i in kand),
                  key=lambda d: (-d["trafien"], -d["wypelnionych"]))
