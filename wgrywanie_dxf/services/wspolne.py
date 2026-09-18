# -*- coding: utf-8 -*-
"""Drobiazgi uzywane wszedzie: normalizacja naglowkow, sciezek, liczb."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

MAX_REF = 40          # nvarchar(40) w LANTEKU - PrdRef i OrdRef
_OGONKI = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def bez_ogonkow(s) -> str:
    s = "" if s is None else str(s)
    s = s.translate(_OGONKI)
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def norm_naglowek(s) -> str:
    """'Bezeichnung.......' -> 'bezeichnung'; 'ILOŚĆ DO WYKONANIA' -> 'iloscdowykonania'."""
    return re.sub(r"[^a-z0-9]", "", bez_ogonkow(s).lower())


def norm_path(p) -> str:
    """UNC z backslashami potrafi sypnac FileNotFoundError - forward slash dziala zawsze."""
    return str(p).replace("\\", "/")


def sciezka(p) -> Path:
    return Path(norm_path(p))


def do_liczby(v):
    """'012,00' -> 12.0, '1,5' -> 1.5, 12 -> 12.0, '' -> None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    if not s:
        return None
    if "," in s and "." in s:            # format niemiecki 2.232,000
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def liczba_txt(v) -> str:
    """Do XML: 12.0 -> '12', 1.5 -> '1.5'. Lantek chce kropki."""
    f = do_liczby(v)
    if f is None:
        return ""
    return str(int(f)) if float(f).is_integer() else ("%g" % f)


# Czlon ilosci MUSI miec litere ('2st', '13s', '6sz', '1szt', '188st').
# Sam ciag cyfr NIE jest iloscia - inaczej numer rysunku bez prefiksu SL
# (4_S235_500173_p1_188st_G_9468_) zostaje wziety za ilosc, a technologia
# wychodzi 'p1'. Blad znaleziony 18.09.2026 na 41 pozycjach z bazy.
_RE_ILOSC = re.compile(r"^(\d+)(szt|sz|st|s|t)$", re.I)


def rozbierz_referencje(ref: str) -> dict:
    """Czlony referencji: {grubosc}_{gatunek}_{Zeinr}_p{Posn}_{N}st_{TECHNOLOGIA}_{zlec}_{index}

    Technologie czytamy WZGLEDEM CZLONU ILOSCI (nigdy 'sztywno szosty') - bywa
    dodatkowy czlon wariantu, np. 2_VER_SL10348893_p1_A_1st_GS_8241D_.

    GRUBOSC = czlon 1, GATUNEK = czlon 2. Referencja niesie je ZAWSZE, takze
    w wykazach bez kolumn kontrolnych (grubosc_poprawiona / gatunek_poprawiony) -
    i to ona idzie do LANTEKA, wiec jest zrodlem prawdy.
    """
    out = {"czesci": [], "ilosc": None, "technologia": None, "posn": None,
           "zeinr": None, "i_ilosc": None, "grubosc": None, "gatunek": None}
    if not ref:
        return out
    cz = str(ref).split("_")
    out["czesci"] = cz
    if cz:
        out["grubosc"] = do_liczby(cz[0])            # '1,5' -> 1.5, '012' -> 12.0
    if len(cz) > 1:
        out["gatunek"] = cz[1].strip()
    for i, c in enumerate(cz):
        m = _RE_ILOSC.match(c.strip())
        if m and i >= 2:                   # czlon ilosci nie stoi na poczatku
            out["i_ilosc"] = i
            out["ilosc"] = int(m.group(1))
            out["technologia"] = (cz[i + 1].strip().upper() if i + 1 < len(cz) else "")
            break
    for c in cz:
        s = c.strip()
        if re.fullmatch(r"p\d+[A-Za-z]?", s):
            out["posn"] = s[1:]
            break
    if len(cz) > 2:
        out["zeinr"] = cz[2].strip()
    return out


def cp1250_ok(s) -> str | None:
    """Zwraca komunikat o bledzie albo None. XML idzie w windows-1250."""
    try:
        str(s).encode("cp1250")
        return None
    except UnicodeEncodeError as e:
        return str(e)
