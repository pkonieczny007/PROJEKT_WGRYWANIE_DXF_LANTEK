# -*- coding: utf-8 -*-
"""Generator XML dla importera LANTEKA (PowerSync = XmlImporter.exe).

Format odtworzony z 361 realnych plikow C:\\Lantek\\importxml\\SheetParts_*.xml
i z makra 'Lantek XLS2XML - Aggregate_v7.xlsm'.

Kolejnosc polecen (jak w makrze):
    SALEORDERS            - raz na poczatku pliku (tylko gdy zakladamy zamowienie)
    dla kazdego elementu:
        PRODUCTS
        PRODUCT OPERATIONS    - opcjonalnie (patrz nizej)
        IMPORTGEO
        SALEORDERLINES

MARSZRUTA - najwazniejsza rzecz w tym pliku
---------------------------------------------------------------------------
LANTEK nadaje marszrute SAM, regula ruty, ktora czyta pole UData8 produktu
(szablony w MMNN_PPOO_00000100, np. L+G: UData8 LIKE '*_G_*' AND Thickness<=15).
Lantek Expert wpisuje tam PELNA REFERENCJE - dlatego u niego marszruta wchodzi.

Makro XLS2XML wysyla UData1..UData8 PUSTE (351 z 353 plikow), wiec zadna regula
nie pasuje i element dostaje rute domyslna L = samo wypalanie. Stad "marszruta
wchodzi tylko Laser".

Dlatego TEN generator wpisuje UData8 = PrdRef.

Jawne PRODUCT OPERATIONS sa domyslnie WYLACZONE: sprawdzone na bazie, ze przy
elemencie z geometria nie utrzymuja sie (import geometrii przebudowuje marszrute).
Z 400 elementow wgranych importem, majacych geometrie i 2 operacje, 399 mialo
druga operacje dopisana recznie w Expercie.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .wspolne import MAX_REF, liczba_txt

KODOWANIE = "windows-1250"
NL = "\r\n"

# FldType: 20 = tekst, 100 = liczba, 120 = data
T_TXT, T_LICZ = "20", "100"


class BladXML(ValueError):
    pass


@dataclass
class ElementXML:
    ref: str                     # PrdRef / ArtRef / Product
    material: str                # MatRef
    grubosc: float | None        # Height
    ilosc: float                 # Quantity w linii zamowienia
    dxf: str | None = None       # sciezka pliku DXF widziana przez LANTEKA
    nazwa: str = ""              # PrdName (zwykle puste, jak w makrze)
    operacje: list = field(default_factory=list)   # [(OOrder, PrevOpr, Wrk, Opr, etykieta)]
    priorytet: int = 0
    bez_linii: bool = False      # juz jest w zamowieniu - tylko aktualizacja elementu


def _esc(v) -> str:
    """Makro nie escapuje nic - my musimy, inaczej '&' w opisie psuje caly plik."""
    s = "" if v is None else str(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _pole(ref, wartosc, typ=T_TXT) -> str:
    return '    <FIELD FldRef="%s" FldValue="%s" FldType="%s"/>' % (ref, _esc(wartosc), typ)


def _polecenie(tabela, pola) -> list:
    return ['<COMMAND Name="Import" TblRef="%s">' % tabela] + pola + ["</COMMAND>"]


def sprawdz_element(e: ElementXML):
    """Twarde warunki LANTEKA - lepiej wywalic sie tutaj niz wgrac smieci."""
    if not e.ref:
        raise BladXML("element bez referencji")
    if len(e.ref) > MAX_REF:
        raise BladXML("referencja %d znakow (limit %d): %s" % (len(e.ref), MAX_REF, e.ref))
    if not e.material:
        raise BladXML("%s: brak materialu (MatRef)" % e.ref)
    if not e.grubosc:
        raise BladXML("%s: grubosc 0 lub pusta" % e.ref)
    for tekst in (e.ref, e.material, e.nazwa):
        try:
            str(tekst).encode(KODOWANIE)
        except UnicodeEncodeError as err:
            raise BladXML("%s: znak spoza %s (%s)" % (e.ref, KODOWANIE, err))


def polecenia_elementu(e: ElementXML, ordref=None, linia=None, udata8=True) -> list:
    """Wszystkie COMMAND-y dla jednego elementu, w kolejnosci jak w makrze."""
    sprawdz_element(e)
    linie = []

    # --- PRODUCTS. UData8 = referencja -> LANTEK dopasuje rute (marszruta!)
    pola = [_pole("PrdRef", e.ref), _pole("PrdName", e.nazwa),
            _pole("MatRef", e.material), _pole("Height", liczba_txt(e.grubosc), T_LICZ),
            _pole("Priority", e.priorytet, T_LICZ)]
    for i in range(1, 9):
        wartosc = e.ref if (i == 8 and udata8) else ""
        pola.append(_pole("UData%d" % i, wartosc))
    linie += _polecenie("PRODUCTS", pola)

    # --- PRODUCT OPERATIONS (opcjonalne; patrz naglowek pliku)
    for oo, prev, wrk, opr, _etyk in e.operacje:
        linie += _polecenie("PRODUCT OPERATIONS", [
            _pole("PrdRef", e.ref), _pole("OOrder", oo, T_LICZ),
            _pole("PrevOpr", prev, T_LICZ), _pole("WrkRef", wrk), _pole("OprRef", opr)])

    # --- IMPORTGEO. Length/Width CELOWO nie wysylamy - wlaczyloby geometrie PARA
    if e.dxf:
        linie += _polecenie("IMPORTGEO", [
            _pole("Product", e.ref), _pole("GeometryType", "DXF"),
            _pole("GeometryPath", e.dxf)])

    # --- SALEORDERLINES
    if ordref and linia is not None:
        linie += _polecenie("SALEORDERLINES", [
            _pole("OrdRef", ordref), _pole("ArtRef", e.ref),
            _pole("LineNum", int(linia)), _pole("Quantity", liczba_txt(e.ilosc))])
    return linie


def zbuduj(elementy, ordref=None, zaloz_zamowienie=False, pierwsza_linia=1,
           udata8=True) -> str:
    """Caly plik XML jako tekst (bez deklaracji, CRLF - dokladnie jak makro)."""
    if ordref and len(ordref) > MAX_REF:
        raise BladXML("OrdRef %d znakow (limit %d): %s" % (len(ordref), MAX_REF, ordref))
    linie = ["<DATAEX>"]
    if ordref and zaloz_zamowienie:
        linie += _polecenie("SALEORDERS", [_pole("OrdRef", ordref)])
    nr = int(pierwsza_linia)
    for e in elementy:
        z_linia = bool(ordref) and not e.bez_linii
        linie += polecenia_elementu(e, ordref=ordref,
                                    linia=(nr if z_linia else None), udata8=udata8)
        if z_linia:
            nr += 1
    linie.append("</DATAEX>")
    return NL.join(linie) + NL


def zapisz(elementy, sciezka_pliku, **kw) -> Path:
    """LANTEK czyta windows-1250. Znak spoza tego kodowania psuje caly import."""
    tresc = zbuduj(elementy, **kw)
    p = Path(str(sciezka_pliku).replace("\\", "/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(tresc.encode(KODOWANIE))
    return p


def podsumowanie(elementy, ordref=None, zaloz_zamowienie=False) -> dict:
    return {
        "elementow": len(elementy),
        "z_geometria": sum(1 for e in elementy if e.dxf),
        "operacji": sum(len(e.operacje) for e in elementy),
        "linii_zamowienia": sum(1 for e in elementy if not e.bez_linii) if ordref else 0,
        "bez_linii": sum(1 for e in elementy if e.bez_linii) if ordref else 0,
        "zaklada_zamowienie": bool(ordref and zaloz_zamowienie),
    }


# ---------------------------------------------------------------------------
# WYMUSZENIE MARSZRUTY - drugi przebieg, po imporcie glownym
#
# Ustalone na korpusie 551 plikow i 809 logow importera:
#   * importer SORTUJE polecenia po tabeli (PRODUCTS -> PRODUCT OPERATIONS ->
#     IMPORTGEO -> ...), wiec kolejnosc w pliku niczego nie zmienia: geometria
#     zawsze wchodzi PO operacjach i przebudowuje marszrute;
#   * PRODUCT OPERATIONS to upsert po (PrdRef, OOrder) - import NIE kasuje
#     operacji, ktorych nie wymienia, wiec krotsza marszruta zostawia smieci;
#   * utarty wzorzec podmiany marszruty to DELETE wszystkich operacji produktu,
#     a potem ponowny import (937 usuniec w 65 logach, zero bledow).
#
# Uzywamy tego TYLKO gdy regula ruty LANTEKA nie nadaje gietarki, a technologia
# elementu tego wymaga (kody SG, WS, GSO przy grubosci > 15 - realne luki
# w regulach). Zawsze jako osobny plik i osobny przebieg importu.
# ---------------------------------------------------------------------------

def polecenie_kasuj_operacje(ref) -> list:
    return ['<COMMAND Name="DELETE" TblRef="PRODUCT OPERATIONS">',
            "    <CONDITIONS><CONDITION>",
            '        <FIELD FldRef="PrdRef" /><EQUAL />',
            '        <CONSTANT Value="%s" FldType="20" />' % _esc(ref),
            "    </CONDITION></CONDITIONS>",
            "</COMMAND>"]


def zbuduj_marszrute(pary) -> str:
    """pary: [(referencja, [(OOrder, PrevOpr, WrkRef, OprRef, etykieta), ...])].

    Dla kazdego elementu: DELETE calej marszruty + Import operacji od nowa.
    """
    linie = ["<DATAEX>"]
    for ref, operacje in pary:
        if not operacje:
            continue
        linie += polecenie_kasuj_operacje(ref)
        for oo, prev, wrk, opr, _e in operacje:
            linie += _polecenie("PRODUCT OPERATIONS", [
                _pole("PrdRef", ref), _pole("OOrder", oo, T_LICZ),
                _pole("PrevOpr", prev, T_LICZ), _pole("WrkRef", wrk), _pole("OprRef", opr)])
    linie.append("</DATAEX>")
    return NL.join(linie) + NL


def zapisz_marszrute(pary, sciezka_pliku) -> Path:
    p = Path(str(sciezka_pliku).replace("\\", "/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(zbuduj_marszrute(pary).encode(KODOWANIE))
    return p
