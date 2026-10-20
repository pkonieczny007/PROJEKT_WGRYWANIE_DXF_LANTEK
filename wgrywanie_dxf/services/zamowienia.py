# -*- coding: utf-8 -*-
"""Lista zamowien sprzedazy z LANTEKA trzymana w pamieci (TYLKO SELECT).

Ten sam sposob co w PROJEKT_FORMATKA+CZASY_PALENIA: cala lista naglowkow
SSAA_SSOO_00000100 jednym zapytaniem (kilkaset wierszy, ~0,2 s), odswiezana
przy starcie aplikacji i przy pierwszej akcji uzytkownika (wpisanie numeru,
"Zaproponuj"). Dzieki temu formularz od razu mowi, czy zamowienie juz jest.
"""
from __future__ import annotations

import threading
from datetime import datetime

from . import lantek_db as db

STAN = {0: "nieuruchomione", 1: "uruchamiane", 2: "uruchomione",
        3: "zakonczone", 4: "zamkniete"}
SWIEZOSC_S = 60          # starsza lista jest pobierana od nowa

_cache = {"lista": [], "czas": None, "blad": None}
_lock = threading.Lock()


def _pobierz(cfg_db) -> list:
    cn = db.polacz(cfg_db)
    try:
        cur = cn.cursor()
        cur.execute(
            "SELECT h.OrdRef, h.ManState, h.CrtDate, h.LastDate, "
            "       (SELECT COUNT(*) FROM %s l WHERE l.OrdRef = h.OrdRef) AS Linii, "
            "       (SELECT MAX(CAST(l.LineNum AS INT)) FROM %s l "
            "         WHERE l.OrdRef = h.OrdRef) AS MaxLinia "
            "FROM %s h ORDER BY h.CrtDate DESC, h.OrdRef"
            % (db.T_ZAM_LINIE, db.T_ZAM_LINIE, db.T_ZAM_NAGL))
        out = []
        for d in db._slowniki(cur):
            out.append({
                "ordref": (d["OrdRef"] or "").strip(),
                "stan": STAN.get(d["ManState"], str(d["ManState"])),
                "utworzone": d["CrtDate"].strftime("%d.%m.%Y") if d["CrtDate"] else "",
                "zmienione": d["LastDate"].strftime("%d.%m.%Y %H:%M") if d["LastDate"] else "",
                "linii": int(d["Linii"] or 0),
                "max_linia": int(d["MaxLinia"] or 0),
            })
        return out
    finally:
        cn.close()


def odswiez(cfg_db, wymus=False) -> dict:
    """Pobiera liste od nowa, gdy jest starsza niz SWIEZOSC_S (albo wymus=True).
    Brak bazy nie przerywa pracy - zostaje poprzednia lista i komunikat bledu."""
    with _lock:
        czas = _cache["czas"]
        if not wymus and czas and (datetime.now() - czas).total_seconds() < SWIEZOSC_S:
            return _cache
        try:
            _cache.update(lista=_pobierz(cfg_db), czas=datetime.now(), blad=None)
        except Exception as e:
            _cache["blad"] = "%s: %s" % (type(e).__name__, e)
    return _cache


def szukaj(numer) -> list:
    """Zamowienia, ktorych OrdRef zawiera numer zlecenia (np. 37_1731)."""
    n = (numer or "").strip().upper()
    if not n:
        return []
    return [z for z in _cache["lista"] if n in z["ordref"].upper()]


def info(numer) -> dict:
    """Do szablonu i API: pasujace zamowienia + kiedy lista byla pobrana."""
    return {
        "zamowienia": szukaj(numer),
        "pobrano": _cache["czas"].strftime("%H:%M:%S") if _cache["czas"] else None,
        "blad": _cache["blad"],
    }
