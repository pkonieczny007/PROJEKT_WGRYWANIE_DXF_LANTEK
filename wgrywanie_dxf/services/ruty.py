# -*- coding: utf-8 -*-
"""Ruty LANTEKA - jak naprawde nadawana jest marszruta.

USTALONE 18.09.2026 na bazie produkcyjnej:

  Tabela MMNN_PPOO_00000100 to SZABLONY RUT z warunkami automatycznego
  przypisania (kolumna DIS_Rules, XML <CONDITIONS>). Warunki czytaja pole
  UData8 produktu i jego grubosc, np.:

      L      (domyslna)  Thickness <= 15 AND UData8 NOT LIKE *S* AND NOT LIKE *G*
      L+G                UData8 LIKE *_G_*   AND Thickness <= 15
      P+G                UData8 LIKE *_G_*   AND Thickness >  15
      L+G+S              UData8 LIKE *GS*    AND Thickness <= 15
      L+S                UData8 LIKE *_S_*   AND Thickness <= 15
      L+SO               UData8 LIKE *_SO_*  AND Thickness <= 15
      L+G+O              UData8 LIKE *_GO_*  AND Thickness <= 15

  Operacje kazdego szablonu leza w MMNN_PPOO_00000200 z niepustym RouRef
  (np. RouRef='L+G' -> 2D Cut + Giecie).

  Lantek Expert wpisuje do UData8 PELNA REFERENCJE produktu - dlatego ruta
  dopasowuje sie sama. W bazie: 20363 produktow z ruta L+G, 27397 z L.

  Makro XLS2XML wysyla UData1..UData8 PUSTE (351 z 353 plikow w
  C:\\Lantek\\importxml). Dlatego zaden warunek nie pasuje i element dostaje
  rute domyslna L = samo wypalanie. To jest przyczyna "marszruta wchodzi
  tylko Laser".

Wniosek dla generatora XML: wysylamy UData8 = PrdRef.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass
class Ruta:
    ref: str                 # RouRef, np. 'L+G'
    domyslna: bool
    klasa: int | None        # DIS_PClass: 2 = blacha, 1 = element, 56 = profil
    warunki_xml: str
    operacje: list           # [(OOrder, WrkRef, OprRef)]

    def opis(self) -> str:
        return " -> ".join(o[2] for o in sorted(self.operacje))


# ---------------------------------------------------------- czytanie regul

_POROWNANIA = {"LIKE": "like", "NOTLIKE": "notlike", "EQUAL": "eq", "NOTEQUAL": "ne",
               "GREATERTHAN": "gt", "GREATEROREQUAL": "ge",
               "SMALLERTHAN": "lt", "SMALLEROREQUAL": "le"}


def parsuj_warunki(xml_txt):
    """DIS_Rules -> [(pole, operator, wartosc, laczenie_z_poprzednim)].

    Zwraca [] gdy regul brak (ruta przypisywana recznie).
    """
    if not xml_txt or not xml_txt.strip():
        return []
    try:
        root = ET.fromstring(xml_txt)
    except ET.ParseError:
        return []
    out, spojnik = [], None
    for el in root:
        if el.tag in ("AND", "OR"):
            spojnik = el.tag
            continue
        if el.tag != "CONDITION":
            continue
        pola = el.findall("./EXPRESSION/FIELD")
        stale = el.findall("./EXPRESSION/CONSTANT")
        op = None
        for dziecko in el:
            if dziecko.tag in _POROWNANIA:
                op = _POROWNANIA[dziecko.tag]
        if not pola or op is None:
            continue
        wartosc = stale[0].get("Value") if stale else ""
        out.append((pola[0].get("FldRef"), op, wartosc, spojnik))
        spojnik = None
    return out


def _like(tekst, wzorzec) -> bool:
    """Wzorzec LANTEKA uzywa '*' jako dowolny ciag. Bez rozrozniania wielkosci liter."""
    rx = "^" + ".*".join(re.escape(cz) for cz in wzorzec.split("*")) + "$"
    return re.match(rx, tekst or "", re.I) is not None


def _liczba(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def warunek_spelniony(pole, op, wartosc, dane) -> bool | None:
    """dane: {'UData8': ..., 'Thickness': ...}. None = nie umiemy ocenic."""
    if pole not in dane:
        return None
    wart_pola = dane[pole]
    if op in ("like", "notlike"):
        wynik = _like(str(wart_pola or ""), str(wartosc))
        return wynik if op == "like" else not wynik
    a, b = _liczba(wart_pola), _liczba(wartosc)
    if a is None or b is None:
        if op == "eq":
            return str(wart_pola) == str(wartosc)
        if op == "ne":
            return str(wart_pola) != str(wartosc)
        return None
    return {"gt": a > b, "ge": a >= b, "lt": a < b, "le": a <= b,
            "eq": a == b, "ne": a != b}[op]


def pasuje(ruta: Ruta, dane) -> bool | None:
    """Czy ruta pasuje do produktu. None = regula uzywa pola, ktorego nie znamy.

    LANTEK laczy warunki spojnikami AND/OR; u nas w praktyce wystepuje samo AND.
    """
    warunki = parsuj_warunki(ruta.warunki_xml)
    if not warunki:
        return False
    wynik = None
    for pole, op, wartosc, spojnik in warunki:
        w = warunek_spelniony(pole, op, wartosc, dane)
        if w is None:
            return None
        if wynik is None:
            wynik = w
        elif spojnik == "OR":
            wynik = wynik or w
        else:
            wynik = wynik and w
    return wynik


def przewidz(ruty, ref, grubosc, klasa=2):
    """Ktora rute LANTEK najpewniej nada. Zwraca (Ruta|None, lista_pasujacych, opis).

    UWAGA: to jest PRZEWIDYWANIE, nie gwarancja - LANTEK ma wlasna kolejnosc
    rozstrzygania remisow. Zawsze weryfikujemy rute PO imporcie.
    """
    dane = {"UData8": ref or "", "Thickness": grubosc,
            "UData1": "", "UData2": "", "UData3": "", "UData4": "",
            "UData5": "", "UData6": "", "UData7": ""}
    kandydaci = []
    for r in ruty:
        if klasa is not None and r.klasa is not None and r.klasa != klasa:
            continue
        if pasuje(r, dane):
            kandydaci.append(r)
    if len(kandydaci) == 1:
        return kandydaci[0], kandydaci, "regula dopasowala jedna rute"
    if kandydaci:
        return kandydaci[0], kandydaci, "pasuje %d rut - LANTEK rozstrzygnie sam" % len(kandydaci)
    dom = [r for r in ruty if r.domyslna and (klasa is None or r.klasa in (None, klasa))]
    if dom:
        return dom[0], [], "zadna regula nie pasuje - wejdzie ruta domyslna"
    return None, [], "brak pasujacej i brak domyslnej"


def wczytaj_z_bazy(cn) -> list:
    """Szablony rut + ich operacje. Tylko SELECT."""
    cur = cn.cursor()
    cur.execute("SELECT RouRef, RouDflt, DIS_PClass, DIS_Rules FROM MMNN_PPOO_00000100 "
                "WHERE PrdRef = '' OR PrdRef IS NULL")
    surowe = cur.fetchall()
    cur.execute("SELECT RouRef, OOrder, WrkRef, OprRef FROM MMNN_PPOO_00000200 "
                "WHERE RouRef <> '' ORDER BY RouRef, OOrder")
    ops = {}
    for rr, oo, wrk, opr in cur.fetchall():
        ops.setdefault(rr, []).append((int(oo or 0), (wrk or "").strip(), (opr or "").strip()))
    out = []
    for rr, dflt, klasa, reguly in surowe:
        rr = (rr or "").strip()
        if not rr:
            continue
        out.append(Ruta(ref=rr, domyslna=bool(dflt), klasa=int(klasa) if klasa is not None else None,
                        warunki_xml=reguly or "", operacje=ops.get(rr, [])))
    return out
