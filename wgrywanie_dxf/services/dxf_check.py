# -*- coding: utf-8 -*-
"""Kontrola plikow DXF przed wgraniem do LANTEKA.

Co sprawdzamy (tanio -> drogo):
  1. czy dla kazdej referencji z wykazu jest plik (dopasowanie bez wielkosci liter),
  2. czy plik sie otwiera i ma jakiekolwiek encje,
  3. gabaryt z $EXTMIN/$EXTMAX (metoda operatora: skrajne extents, INT),
  4. ile jest linii giecia (kolor 6 / warstwa GIECIE) - WYLACZNIE INFORMACYJNIE.

UWAGA (sprawdzone 18.09.2026 na 82_1129): produkcyjne DXF pobrane z bazy NIE MAJA
zadnych oznaczen giecia - wszystko siedzi na warstwie '0'/'L'/'51' w kolorze 7,
takze dla pozycji _G_ i _GS_. Linie giecia rysujemy tylko przy P/L albo gieciu pod
skosem. Dlatego 'brak linii giecia' NIE jest bledem i nie moze blokowac wgrania.

Gabaryt czytamy z naglowka DXF tekstowo (szybko, bez parsowania calego pliku);
pelne otwarcie przez ezdxf robimy tylko dla plikow w zakresie wgrania.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .wspolne import sciezka

POMIJANE = {"archiwum", "_png", "_kontrola_wymiarow", "__pycache__", "prototyp3",
            "_galeria", "backup", "old", "stare"}


@dataclass
class PlikDXF:
    sciezka: str
    nazwa: str                     # stem pliku, tak jak na dysku
    rozmiar: int = 0
    otwarty: bool | None = None
    blad: str = ""
    encji: int = 0
    szer: float | None = None
    wys: float | None = None
    linii_giecia: int = 0
    warstwy: list = field(default_factory=list)


def _pomijany(p: Path, korzen: Path) -> bool:
    return any(cz.lower() in POMIJANE for cz in p.relative_to(korzen).parts[:-1])


def zbierz(folder, podfoldery=False) -> dict:
    """{nazwa_male_litery: [Path, ...]} - lista, bo ta sama nazwa moze byc w kilku
    podfolderach (wtedy trzeba zapytac czlowieka, ktory plik wgrywamy)."""
    k = sciezka(folder)
    if not k.is_dir():
        raise ValueError("to nie jest folder: %s" % k)
    it = k.rglob("*") if podfoldery else k.glob("*")
    out = {}
    for p in it:
        if p.suffix.lower() != ".dxf" or not p.is_file():
            continue
        if podfoldery and _pomijany(p, k):
            continue
        out.setdefault(p.stem.lower(), []).append(p)
    return out


_RE_EXT = re.compile(rb"\$EXT(MIN|MAX)\s+9?\s*\n?\s*10\n(-?[\d.eE+]+)\s*\n\s*20\n"
                     rb"(-?[\d.eE+]+)\s*\n\s*30\n(-?[\d.eE+]+)", re.S)


def gabaryt_z_naglowka(p: Path):
    """(szer, wys) z $EXTMIN/$EXTMAX - bez parsowania calego pliku. None gdy brak."""
    try:
        with open(p, "rb") as fh:
            glowa = fh.read(65536)
    except OSError:
        return None
    ext = {}
    for m in _RE_EXT.finditer(glowa):
        try:
            ext[m.group(1).decode()] = (float(m.group(2)), float(m.group(3)))
        except ValueError:
            return None
    if "MIN" in ext and "MAX" in ext:
        return (ext["MAX"][0] - ext["MIN"][0], ext["MAX"][1] - ext["MIN"][1])
    return None


def zbadaj(p, pelny=True) -> PlikDXF:
    """Pelny=False: tylko rozmiar + gabaryt z naglowka (szybkie, na duze foldery)."""
    p = Path(p)
    w = PlikDXF(sciezka=str(p), nazwa=p.stem)
    try:
        w.rozmiar = p.stat().st_size
    except OSError as e:
        w.otwarty, w.blad = False, str(e)
        return w

    g = gabaryt_z_naglowka(p)
    if g:
        w.szer, w.wys = round(g[0], 2), round(g[1], 2)
    if not pelny:
        return w

    try:
        import ezdxf
        d = ezdxf.readfile(str(p))
        msp = d.modelspace()
        warstwy = set()
        for e in msp:
            w.encji += 1
            lay = str(getattr(e.dxf, "layer", ""))
            warstwy.add(lay)
            # linia giecia: kolor 6 (magenta) albo warstwa GIECIE - idiom EKSTRAKTOR_DXF
            if getattr(e.dxf, "color", None) == 6 or lay.upper().startswith("GIECIE"):
                w.linii_giecia += 1
        w.warstwy = sorted(warstwy)[:12]
        w.otwarty = True
        if w.szer is None:                      # brak extents w naglowku - liczymy sami
            try:
                from ezdxf import bbox
                b = bbox.extents(msp, fast=False)
                if b.has_data:
                    w.szer = round(b.size.x, 2)
                    w.wys = round(b.size.y, 2)
            except Exception:
                pass
    except Exception as e:
        w.otwarty = False
        w.blad = "%s: %s" % (type(e).__name__, e)
    return w


def dopasuj(referencje, mapa) -> dict:
    """referencja -> dict(plik, stan, uwaga).

    stan: 'ok' | 'inna_wielkosc_liter' | 'kilka' | 'brak'
    """
    out = {}
    for ref in referencje:
        if not ref:
            continue
        klucz = ref.lower()
        trafione = mapa.get(klucz, [])
        if not trafione:
            out[ref] = {"plik": None, "stan": "brak", "uwaga": ""}
            continue
        wybrany = trafione[0]          # wygrywa folder wskazany jako PIERWSZY
        if len(trafione) > 1:
            rozmiary = set()
            for x in trafione:
                try:
                    rozmiary.add(x.stat().st_size)
                except OSError:
                    rozmiary.add(-1)
            te_same = len(rozmiary) == 1
            out[ref] = {
                "plik": wybrany,
                "stan": "kopie" if te_same else "kilka_roznych",
                "uwaga": "ta sama nazwa w %d folderach%s; biore '%s'"
                         % (len(trafione),
                            "" if te_same else " i pliki ROZNIA SIE rozmiarem",
                            wybrany.parent)}
        elif wybrany.stem != ref:
            out[ref] = {"plik": wybrany, "stan": "inna_wielkosc_liter",
                        "uwaga": "plik na dysku: '%s', referencja: '%s'" % (wybrany.stem, ref)}
        else:
            out[ref] = {"plik": wybrany, "stan": "ok", "uwaga": ""}
    return out


def sieroty(mapa, referencje) -> list:
    """Pliki DXF w folderze, ktorych nie ma w wykazie - nie wgrywamy ich, ale mowimy."""
    chciane = {r.lower() for r in referencje if r}
    return sorted(str(v[0].name) for k, v in mapa.items() if k not in chciane)
