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
RE_DOK = re.compile(r"^dok\d+$", re.I)


def rozbierz(numer):
    """'82_1129' -> ('82', '1129'). Zwraca (None, None) gdy format nie pasuje."""
    m = RE_ZLECENIE.match((numer or "").strip())
    return (m.group(1), m.group(2)) if m else (None, None)


def domyslny_ordref(numer) -> str:
    nn, xxxx = rozbierz(numer)
    return "%s_%s_BLACHY" % (nn, xxxx) if nn else ""


def _czy_roboczy(nazwa) -> bool:
    """ROBOCZY_..., WGRANIE_ROBOCZY_... tak; TMPROBOCZY_... nie."""
    n = nazwa.upper()
    return "ROBOCZY_" in n and not n.startswith("TMPROBOCZY_")


def _wykazy(folder: Path) -> list:
    out = []
    for p in folder.glob("*.xls*"):
        if p.name.startswith("~$"):
            continue
        out.append(p)
    # najpierw robocze, potem najnowsze
    out.sort(key=lambda p: (not _czy_roboczy(p.name), -p.stat().st_mtime))
    return out


def _podfoldery(folder: Path) -> list:
    """Podfoldery jednego poziomu, w ktorych bywa wykaz (np. DXF_37_1731-REWIZJA).
    Bez smietnikow, folderow z rysunkami (dokNN) i sprawdzania w bazie."""
    try:
        dzieci = sorted((p for p in folder.iterdir() if p.is_dir()),
                        key=lambda p: -p.stat().st_mtime)
    except OSError:
        return []
    return [p for p in dzieci
            if p.name.lower() not in POMIJANE
            and not RE_DOK.match(p.name)
            and not p.name.upper().startswith("PROJEKT-")]


def _opis_wykazu(x: Path, folder: Path) -> dict:
    try:
        wzgl = str(x.relative_to(folder))
    except ValueError:
        wzgl = x.name
    return {"sciezka": str(x), "nazwa": wzgl, "roboczy": _czy_roboczy(x.name)}


def wykazy_w_folderze(folder: Path) -> list:
    """Wykazy z folderu i jego podfolderow (jeden poziom). Najpierw robocze -
    z folderu, potem z podfolderow - a za nimi cala reszta."""
    out = [_opis_wykazu(x, folder) for x in _wykazy(folder)]
    for pod in _podfoldery(folder):
        out.extend(_opis_wykazu(x, folder) for x in _wykazy(pod))
    out.sort(key=lambda w: not w["roboczy"])      # sort stabilny - kolejnosc zostaje
    return out


def folder_zlecenia(numer, korzenie_technologia):
    """Szybkie: folder zlecenia w Technologii albo None. Bez skanu DXF."""
    nn, xxxx = rozbierz(numer)
    if not nn:
        return None
    zl = "%s_%s" % (nn, xxxx)
    for k in korzenie_technologia:
        kp = sciezka(k)
        if not kp.is_dir():
            continue
        for p in sorted(kp.glob("%s*" % zl)):
            if p.is_dir():
                return p
    return None


def podpowiedz_folderu(numer, korzenie_technologia) -> dict:
    """Do pola 'Folder zlecenia': propozycja + podfoldery do klikniecia."""
    f = folder_zlecenia(numer, korzenie_technologia)
    return {"folder": str(f) if f else None,
            "podfoldery": [str(p) for p in _podfoldery(f)] if f else []}


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


def propozycje(numer, korzenie_technologia, korzenie_dxf, glebokosc=3,
                folder=None) -> dict:
    """{'zlecenie', 'folder', 'wykazy': [...], 'foldery_dxf': [...], 'ordref'}

    folder - wpisany przez czlowieka (np. podfolder rewizji); ma pierwszenstwo
    przed znalezionym w Technologii: z niego bierzemy wykazy i jego foldery DXF
    stawiamy na liscie najwyzej."""
    nn, xxxx = rozbierz(numer)
    out = {"zlecenie": numer, "nn": nn, "xxxx": xxxx, "folder": None,
           "folder_reczny": False,
           "wykazy": [], "foldery_dxf": [], "ordref": domyslny_ordref(numer),
           "uwagi": []}
    folder = (folder or "").strip()
    if folder:
        fp = sciezka(folder)
        if fp.is_dir():
            out["folder"] = str(fp)
            # podpowiedziany folder zlecenia to nie wybor czlowieka
            auto = folder_zlecenia(numer, korzenie_technologia)
            out["folder_reczny"] = not (auto and str(auto).lower() == str(fp).lower())
        else:
            out["uwagi"].append("folder %s nie istnieje" % folder)
    if not nn and not out["folder"]:
        out["uwagi"].append("numer zlecenia w formacie NN_XXXX, np. 82_1129")
        return out

    # folder zlecenia w Technologii
    if not out["folder"]:
        f = folder_zlecenia(numer, korzenie_technologia)
        if f:
            out["folder"] = str(f)
        else:
            out["uwagi"].append("nie znalazlem folderu zlecenia %s_%s w Technologii"
                                % (nn, xxxx))
    if out["folder"]:
        out["wykazy"] = wykazy_w_folderze(sciezka(out["folder"]))
        if not out["wykazy"]:
            out["uwagi"].append("w folderze %s nie ma plikow .xls*" % out["folder"])

    widziane = set()
    if out["folder_reczny"]:
        for d in sorted(_foldery_dxf(sciezka(out["folder"]), glebokosc),
                        key=lambda d: -d["plikow"]):
            widziane.add(d["sciezka"])
            out["foldery_dxf"].append(d)
    reczne = len(out["foldery_dxf"])
    if not nn:
        return out
    zl = "%s_%s" % (nn, xxxx)

    # foldery z DXF
    rok = datetime.now().year
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

    # najpierw foldery spod folderu wpisanego recznie, reszta wg liczby plikow
    out["foldery_dxf"][reczne:] = sorted(out["foldery_dxf"][reczne:],
                                         key=lambda d: -d["plikow"])
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


def historia_wgran(plik_rejestru, numer, refy=()) -> list:
    """Wczesniejsze wgrania, ktore dotyczyly tych samych elementow.

    Wpis z lista 'refy' pasuje, gdy ma choc jeden wspolny element (lapie tez
    inny numer zlecenia i inny OrdRef). Starsze wpisy bez 'refy' - po numerze.
    Najnowsze pierwsze, bez samej listy refy (bywa dluga)."""
    refy = set(refy)
    out = []
    for d in czytaj_rejestr(plik_rejestru):
        if d.get("refy"):
            wspolnych = len(refy & set(d["refy"]))
            if not wspolnych:
                continue
        elif numer and d.get("zlecenie") == numer:
            wspolnych = None
        else:
            continue
        w = {k: v for k, v in d.items() if k != "refy"}
        w["wspolnych"] = wspolnych
        out.append(w)
    out.sort(key=lambda d: d.get("czas", ""), reverse=True)
    return out
