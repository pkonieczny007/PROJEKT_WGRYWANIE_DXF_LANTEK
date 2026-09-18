# -*- coding: utf-8 -*-
"""Propozycje po numerze zlecenia + rejestr wgran.

Folder DXF wybiera czlowiek - my tylko podpowiadamy, gdzie zwykle lezy.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .wspolne import sciezka

RE_ZLECENIE = re.compile(r"^(\d{1,3})[_\-. ](\d{4})$")
POMIJANE = {"archiwum", "_png", "_kontrola_wymiarow", "__pycache__", "prototyp3",
            "_galeria", "backup", "old"}


def rozbierz(numer):
    """'82_1129' -> ('82', '1129'). Zwraca (None, None) gdy format nie pasuje."""
    m = RE_ZLECENIE.match((numer or "").strip())
    return (m.group(1), m.group(2)) if m else (None, None)


def domyslny_ordref(numer) -> str:
    nn, xxxx = rozbierz(numer)
    return "%s_%s_BLACHY" % (nn, xxxx) if nn else ""


def _wykazy(folder: Path) -> list:
    out = []
    for p in folder.glob("*.xls*"):
        if p.name.startswith("~$"):
            continue
        out.append(p)
    # najpierw ROBOCZY_, potem najnowsze
    out.sort(key=lambda p: (not p.name.upper().startswith("ROBOCZY_"),
                            p.name.upper().startswith("TMPROBOCZY_"),
                            -p.stat().st_mtime))
    return out


def _foldery_dxf(korzen: Path, glebokosc=3) -> list:
    """Kazdy podfolder z plikami .dxf + licznik. Bez schodzenia w smietniki."""
    out = []
    if not korzen.is_dir():
        return out

    def idz(f: Path, poziom):
        try:
            dzieci = list(f.iterdir())
        except OSError:
            return
        ile = sum(1 for p in dzieci if p.is_file() and p.suffix.lower() == ".dxf")
        if ile:
            out.append({"sciezka": str(f), "plikow": ile})
        if poziom < glebokosc:
            for p in dzieci:
                if p.is_dir() and p.name.lower() not in POMIJANE:
                    idz(p, poziom + 1)

    idz(korzen, 0)
    return out


def propozycje(numer, korzenie_technologia, korzenie_dxf, glebokosc=3) -> dict:
    """{'zlecenie', 'folder', 'wykazy': [...], 'foldery_dxf': [...], 'ordref'}"""
    nn, xxxx = rozbierz(numer)
    out = {"zlecenie": numer, "nn": nn, "xxxx": xxxx, "folder": None,
           "wykazy": [], "foldery_dxf": [], "ordref": domyslny_ordref(numer),
           "uwagi": []}
    if not nn:
        out["uwagi"].append("numer zlecenia w formacie NN_XXXX, np. 82_1129")
        return out
    zl = "%s_%s" % (nn, xxxx)

    # folder zlecenia w Technologii
    for k in korzenie_technologia:
        kp = sciezka(k)
        if not kp.is_dir():
            continue
        for p in kp.glob("%s*" % zl):
            if p.is_dir():
                out["folder"] = str(p)
                out["wykazy"] = [{"sciezka": str(x), "nazwa": x.name,
                                  "roboczy": x.name.upper().startswith("ROBOCZY_")}
                                 for x in _wykazy(p)]
                break
        if out["folder"]:
            break
    if not out["folder"]:
        out["uwagi"].append("nie znalazlem folderu zlecenia %s w Technologii" % zl)

    # foldery z DXF
    rok = datetime.now().year
    widziane = set()
    for wzor in korzenie_dxf:
        k = sciezka(wzor.replace("{zl}", zl).replace("{nn}", nn).replace("{rok}", str(rok)))
        if not k.is_dir():
            # wariant: korzen zawiera folder zaczynajacy sie od numeru zlecenia
            rodzic = k.parent
            if rodzic.is_dir():
                for p in rodzic.glob("%s*" % zl):
                    if p.is_dir():
                        for d in _foldery_dxf(p, glebokosc):
                            if d["sciezka"] not in widziane:
                                widziane.add(d["sciezka"])
                                out["foldery_dxf"].append(d)
            continue
        for d in _foldery_dxf(k, glebokosc):
            if d["sciezka"] not in widziane:
                widziane.add(d["sciezka"])
                out["foldery_dxf"].append(d)

    out["foldery_dxf"].sort(key=lambda d: -d["plikow"])
    if not out["foldery_dxf"]:
        out["uwagi"].append("nie znalazlem folderow z plikami DXF - wskaz reczne")
    return out


def folder_przebiegu(katalog_danych, numer) -> Path:
    stempel = datetime.now().strftime("%Y%m%d_%H%M%S")
    p = sciezka(katalog_danych) / ("%s_%s" % ((numer or "bez_numeru").replace(" ", "_"), stempel))
    p.mkdir(parents=True, exist_ok=True)
    return p


def zapisz_rejestr(plik_rejestru, wpis):
    """Append-only dziennik wgran - druga linia obrony przed powtorka."""
    p = sciezka(plik_rejestru)
    p.parent.mkdir(parents=True, exist_ok=True)
    wpis = dict(wpis)
    wpis["czas"] = datetime.now().isoformat(timespec="seconds")
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(wpis, ensure_ascii=False) + "\n")


def czytaj_rejestr(plik_rejestru, numer=None) -> list:
    p = sciezka(plik_rejestru)
    if not p.is_file():
        return []
    out = []
    for linia in p.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(linia)
        except ValueError:
            continue
        if numer is None or d.get("zlecenie") == numer:
            out.append(d)
    return out
