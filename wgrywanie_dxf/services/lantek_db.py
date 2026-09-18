# -*- coding: utf-8 -*-
"""Dostep do bazy LANTEK/INTEGRA - WYLACZNIE SELECT.

Zbudowane na wzor \\\\Qnap-energo\\baza\\.data\\python\\integra-zakupy-wgraj\\integra_db.py
(tamtego NIE zmieniamy). Zapis do INTEGRY idzie wylacznie przez XmlImporter.exe.

PULAPKA: literal SQL bez prefiksu N gubi polskie znaki i zapytanie po cichu zwraca
0 wierszy. Dlatego KAZDE zapytanie idzie przez parametry pyodbc (bind jako NVARCHAR).
pyodbc ma limit ~2100 parametrow - dzielimy na paczki po 500.
"""
from __future__ import annotations

T_PRODUKTY = "PPRR_PPRR_00000100"      # produkty (PrdRef, DIS_MatRef, DIS_Thickness)
T_OPERACJE = "MMNN_PPOO_00000200"      # marszruta produktu (PrdRef, OOrder, WrkRef, OprRef)
T_BOM = "PPRR_PPRR_00000600"           # sklad zlozen
T_ZAM_NAGL = "SSAA_SSOO_00000100"      # naglowki zamowien sprzedazy
T_ZAM_LINIE = "SSAA_SSOO_00000200"     # linie zamowien sprzedazy

_CHUNK = 500


class BrakBazy(RuntimeError):
    """Baza niedostepna - kontrola idzie dalej, ale bez czesci bazodanowej."""


def polacz(cfg):
    import pyodbc
    cs = ("DRIVER={%s};SERVER=%s;DATABASE=%s;UID=%s;PWD=%s;"
          % (cfg["driver"], cfg["server"], cfg["database"],
             cfg["username"], cfg["password"]))
    try:
        return pyodbc.connect(cs, timeout=cfg.get("timeout", 15))
    except Exception as e:
        raise BrakBazy("%s: %s" % (type(e).__name__, e))


def _paczki(seq, n=_CHUNK):
    seq = [x for x in seq if x]
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _slowniki(cur):
    kol = [d[0] for d in cur.description]
    return [dict(zip(kol, r)) for r in cur.fetchall()]


# ------------------------------------------------------------------ produkty

def produkty_po_ref(cn, refy) -> dict:
    """{PrdRef: {...}} - czy element juz jest w kartotece i z jakim materialem."""
    out = {}
    cur = cn.cursor()
    for cz in _paczki(refy):
        ph = ",".join("?" * len(cz))
        cur.execute(
            "SELECT PrdRef, PrdName, DIS_MatRef, DIS_Thickness, DIS_PClass, Assembly, "
            "       DIS_Length, DIS_Width, CrtDate, LastDate, CrtUser, LastUser "
            "FROM %s WHERE PrdRef IN (%s)" % (T_PRODUKTY, ph), *cz)
        for d in _slowniki(cur):
            out[d["PrdRef"]] = d
    return out


# ----------------------------------------------------------------- marszruta

def operacje_po_ref(cn, refy) -> dict:
    """{PrdRef: [ (OOrder, PrevOpr, WrkRef, OprRef) ... ]} - marszruta w bazie."""
    out = {}
    cur = cn.cursor()
    for cz in _paczki(refy):
        ph = ",".join("?" * len(cz))
        cur.execute(
            "SELECT PrdRef, OOrder, PrevOpr, WrkRef, OprRef "
            "FROM %s WHERE PrdRef IN (%s) ORDER BY PrdRef, OOrder" % (T_OPERACJE, ph), *cz)
        for d in _slowniki(cur):
            out.setdefault(d["PrdRef"], []).append(
                (int(d["OOrder"] or 0), int(d["PrevOpr"] or 0),
                 (d["WrkRef"] or "").strip(), (d["OprRef"] or "").strip()))
    return out


def marszruta_txt(wiersze) -> str:
    return " -> ".join(o[3] for o in sorted(wiersze))


# --------------------------------------------- slowniki: materialy i centra

def _kolumny(cn, tabela) -> list:
    cur = cn.cursor()
    cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_NAME = ? ORDER BY ORDINAL_POSITION", tabela)
    return [r[0] for r in cur.fetchall()]


def tabela_istnieje(cn, tabela) -> bool:
    cur = cn.cursor()
    cur.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?", tabela)
    return bool(cur.fetchone()[0])


def materialy(cn) -> set:
    """Zbior MatRef znanych LANTEKOWI. Nazwa tabeli materialow z XmlImporterConfig."""
    for tab, kol in (("DIS_MMTT_MMTT_00000100", "MatRef"),
                     ("DIS_MMTT_MMTT_00000100", "DIS_MatRef")):
        try:
            if not tabela_istnieje(cn, tab):
                continue
            if kol not in _kolumny(cn, tab):
                continue
            cur = cn.cursor()
            cur.execute("SELECT DISTINCT %s FROM %s" % (kol, tab))
            return {(r[0] or "").strip() for r in cur.fetchall() if r[0]}
        except Exception:
            continue
    return set()


def centra_i_operacje(cn) -> dict:
    """{'centra': {...}, 'operacje': {...}} - z istniejacych marszrut produktow.

    To jest zrodlo pewne: skoro te wartosci siedza w marszrutach, LANTEK je zna.
    """
    cur = cn.cursor()
    cur.execute("SELECT DISTINCT WrkRef, OprRef FROM %s" % T_OPERACJE)
    centra, operacje, pary = set(), set(), set()
    for w, o in cur.fetchall():
        w = (w or "").strip()
        o = (o or "").strip()
        if w:
            centra.add(w)
        if o:
            operacje.add(o)
        if w and o:
            pary.add((w, o))
    return {"centra": centra, "operacje": operacje, "pary": pary}


# --------------------------------------------------- zamowienie sprzedazy

def zamowienie(cn, ordref):
    cur = cn.cursor()
    cur.execute("SELECT OrdRef, CusRef, CDate, DDate, OState FROM %s WHERE OrdRef = ?"
                % T_ZAM_NAGL, ordref)
    d = _slowniki(cur)
    return d[0] if d else None


def linie_zamowienia(cn, ordref) -> list:
    cur = cn.cursor()
    cur.execute("SELECT LineNum, PrdRef, PrdName, Quantity FROM %s WHERE OrdRef = ? "
                "ORDER BY LineNum" % T_ZAM_LINIE, ordref)
    return _slowniki(cur)


def max_linia(cn, ordref) -> int:
    """Numeracje linii kontynuujemy po max(LineNum) - nigdy od 1."""
    cur = cn.cursor()
    cur.execute("SELECT MAX(CAST(LineNum AS INT)) FROM %s WHERE OrdRef = ?"
                % T_ZAM_LINIE, ordref)
    v = cur.fetchone()[0]
    return int(v or 0)


def zamowienia_wg_wzorca(cn, wzorzec) -> list:
    cur = cn.cursor()
    cur.execute("SELECT OrdRef, CDate, OState FROM %s WHERE OrdRef LIKE ? "
                "ORDER BY CDate DESC" % T_ZAM_NAGL, wzorzec)
    return _slowniki(cur)


# ------------------------------------------------------------------- test

def self_test(cfg):
    cn = polacz(cfg)
    cur = cn.cursor()
    cur.execute("SELECT COUNT(*) FROM %s" % T_PRODUKTY)
    print("produktow        :", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM %s" % T_OPERACJE)
    print("wierszy marszrut :", cur.fetchone()[0])
    co = centra_i_operacje(cn)
    print("centra robocze   :", sorted(co["centra"]))
    print("operacje         :", sorted(co["operacje"]))
    m = materialy(cn)
    print("materialow       :", len(m), sorted(list(m))[:15])
    return cn
