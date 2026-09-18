# -*- coding: utf-8 -*-
"""Kod technologii -> lancuch operacji (marszruta) dla LANTEKA.

Marszruta w XML to lancuch COMMAND-ow PRODUCT OPERATIONS:
    OOrder = 1, 2, 3...   PrevOpr = poprzedni OOrder (pierwsza ma 0)

Kod technologii bierzemy Z REFERENCJI (czlon po czlonie ilosci) - bo to
referencja idzie do LANTEKA. Kolumna 'Giecie' wykazu jest zrodlem tego czlonu
(jest skladnikiem formuly nazwy), wiec sluzy do kontroli krzyzowej.

Nazwy centrow i operacji oraz przypisanie liter -> mapowanie.json
(zmiana nie wymaga zmiany kodu).
"""
from __future__ import annotations

import json
from pathlib import Path

MAPOWANIE = json.loads((Path(__file__).resolve().parent.parent / "mapowanie.json")
                       .read_text(encoding="utf-8"))
LASER = MAPOWANIE["laser"]
OPERACJE = MAPOWANIE["operacje"]
TECHNOLOGIA = MAPOWANIE["technologia"]

KOLEJNOSC = ("giecie", "spawanie", "ocynk")     # po wypalaniu


class NieznanyKod(ValueError):
    pass


def znany(kod) -> bool:
    return (kod or "").strip().upper() in TECHNOLOGIA


def legenda() -> dict:
    return {k: v.get("opis", "") for k, v in TECHNOLOGIA.items()}


def operacje(kod, dokladaj_spawanie=False, dokladaj_ocynk=False) -> list:
    """[(OOrder, PrevOpr, WrkRef, OprRef, etykieta)] - zawsze zaczyna od wypalania.

    Spawanie i ocynk dokladamy TYLKO gdy uzytkownik wlaczy opcje - domyslnie
    wgrywamy to, co robia obecne importy z 2026: wypalanie + giecie.
    """
    k = (kod or "").strip().upper()
    if k not in TECHNOLOGIA:
        raise NieznanyKod("nieznany kod technologii: %r" % kod)
    reg = TECHNOLOGIA[k]
    chce = {"giecie": bool(reg.get("giecie")),
            "spawanie": bool(reg.get("spawanie")) and dokladaj_spawanie,
            "ocynk": bool(reg.get("ocynk")) and dokladaj_ocynk}

    out = [(1, 0, LASER["wrk"], LASER["opr"], "wypalanie")]
    for nazwa in KOLEJNOSC:
        if not chce[nazwa]:
            continue
        o = OPERACJE[nazwa]
        nr = len(out) + 1
        out.append((nr, nr - 1, o["wrk"], o["opr"], nazwa))
    return out


def opis(kod, dokladaj_spawanie=False, dokladaj_ocynk=False) -> str:
    """'2D Cut -> Giecie' - do raportu i do porownania z tym, co jest w bazie."""
    return " -> ".join(o[3] for o in operacje(kod, dokladaj_spawanie, dokladaj_ocynk))


def gnie(kod) -> bool:
    reg = TECHNOLOGIA.get((kod or "").strip().upper())
    return bool(reg and reg.get("giecie"))


if __name__ == "__main__":
    for k in sorted(TECHNOLOGIA):
        print("%-5s %-34s | +S/+O: %s" % (repr(k), opis(k), opis(k, True, True)))
