# -*- coding: utf-8 -*-
"""PowerSync = XmlImporter.exe - jedyny tor zapisu do bazy LANTEKA.

Przeniesione z dzialajacego serwisu zakupow (PROJEKT_ETAPY, modules/zakupy/routes.py),
wydzielone tak, zeby dalo sie testowac bez Flaska.

    XmlImporter.exe -dff XMLImporter -src <xml> -user SYSADM -pass "" -hide 0

Importer nie konczy sie sam - po znalezieniu logu ubijamy proces.
Log powstaje w 'C:\\Lantek\\importxml\\Importer log' pod nazwa
    <nazwa_xml>_<data godzina>_log.html      (albo _logERR.html gdy sa bledy)
i jest przenoszony do folderu przebiegu, zeby zostal przy raporcie.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WynikImportu:
    uruchomiony: bool = False
    polecenie: list = field(default_factory=list)
    log: str | None = None
    polecen: int | None = None
    ok: int | None = None
    ostrzezen: int | None = None
    bledow: int | None = None
    komunikaty: list = field(default_factory=list)
    blad: str = ""
    czas_s: float = 0.0

    @property
    def udany(self) -> bool:
        return self.uruchomiony and self.bledow == 0

    def podsumowanie(self) -> str:
        if not self.uruchomiony:
            return "nie uruchomiono: %s" % self.blad
        if self.bledow is None:
            return "uruchomiono, ale nie znaleziono logu w zadanym czasie"
        return ("polecen %s, ok %s, ostrzezen %s, BLEDOW %s"
                % (self.polecen, self.ok, self.ostrzezen, self.bledow))


def _czekaj_na_stabilny(p: Path, prob=2, odstep=0.5, limit=60):
    """Log jest pisany w trakcie - czekamy az rozmiar przestanie rosnac
    i az XmlImporter zwolni plik."""
    start = time.time()
    while time.time() - start < limit and p.stat().st_size == 0:
        time.sleep(odstep)
    poprzedni, stabilnie = p.stat().st_size, 0
    while stabilnie < prob and time.time() - start < limit:
        time.sleep(odstep)
        teraz = p.stat().st_size
        stabilnie = stabilnie + 1 if teraz == poprzedni else 0
        poprzedni = teraz
    while time.time() - start < limit:
        try:                                   # proba przemianowania = test blokady
            tmp = p.with_suffix(p.suffix + ".tmp")
            p.rename(tmp)
            tmp.rename(p)
            return True
        except (PermissionError, OSError):
            time.sleep(odstep)
    return False


_RE_PODSUM = re.compile(
    r"Total commands:\s*(\d+).*?Commands Ok:\s*(\d+).*?"
    r"Commands with warning:\s*(\d+).*?Commands with error:\s*(\d+)", re.S | re.I)


def czytaj_log(p: Path) -> dict:
    """Podsumowanie + komunikaty bledow z logu HTML importera."""
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"blad": str(e)}
    plaski = re.sub(r"<[^>]*>", " ", txt)
    plaski = re.sub(r"\s+", " ", plaski)
    m = _RE_PODSUM.search(plaski)
    out = {}
    if m:
        out.update(polecen=int(m.group(1)), ok=int(m.group(2)),
                   ostrzezen=int(m.group(3)), bledow=int(m.group(4)))
    # komunikaty istotne; 'already exists ... update is executed' jest normalne
    kom = []
    for wzor in (r"Cannot find geometry file:\s*(\S+)",
                 r"Cannot find field reference '([^']+)'",
                 r"(Error[^.]{0,120}\.)"):
        for t in re.findall(wzor, plaski):
            kom.append(t.strip())
    out["komunikaty"] = sorted(set(kom))[:30]
    return out


def wgraj(xml: Path, exe, katalog_logow, folder_wyniku, user="SYSADM", haslo="",
          limit_s=600) -> WynikImportu:
    """Uruchamia importer i czeka na log. NIC nie wgrywa poza tym jednym plikiem."""
    w = WynikImportu()
    xml = Path(str(xml).replace("\\", "/"))
    exe_p = Path(str(exe).replace("\\", "/"))
    logi = Path(str(katalog_logow).replace("\\", "/"))
    cel = Path(str(folder_wyniku).replace("\\", "/"))

    if not xml.is_file():
        w.blad = "brak pliku XML: %s" % xml
        return w
    if not exe_p.is_file():
        w.blad = "brak XmlImporter.exe: %s" % exe_p
        return w

    w.polecenie = [str(exe_p), "-dff", "XMLImporter", "-src", str(xml),
                   "-user", user, "-pass", haslo, "-hide", "0"]
    start = time.time()
    znane = {p.name for p in logi.glob("%s_*.html" % xml.stem)} if logi.is_dir() else set()
    try:
        proc = subprocess.Popen(w.polecenie, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        w.uruchomiony = True
    except Exception as e:
        w.blad = "%s: %s" % (type(e).__name__, e)
        return w

    znaleziony = None
    while time.time() - start < limit_s:
        nowe = [p for p in logi.glob("%s_*.html" % xml.stem) if p.name not in znane]
        if nowe:
            znaleziony = max(nowe, key=lambda p: p.stat().st_mtime)
            break
        time.sleep(1)

    if znaleziony:
        _czekaj_na_stabilny(znaleziony)
        dane = czytaj_log(znaleziony)
        w.polecen, w.ok = dane.get("polecen"), dane.get("ok")
        w.ostrzezen, w.bledow = dane.get("ostrzezen"), dane.get("bledow")
        w.komunikaty = dane.get("komunikaty", [])
        try:
            cel.mkdir(parents=True, exist_ok=True)
            w.log = str(shutil.move(str(znaleziony), str(cel / znaleziony.name)))
        except Exception as e:
            w.log = str(znaleziony)
            w.komunikaty.append("nie udalo sie przeniesc logu: %s" % e)
        # obok logu importer zostawia ErrorCmd.xml z poleceniami, ktore padly
        for err in logi.glob("%s_*ErrorCmd.xml" % xml.stem):
            try:
                shutil.move(str(err), str(cel / err.name))
            except Exception:
                pass
    else:
        w.blad = "nie znaleziono logu importera w %d s" % limit_s

    if proc.poll() is None:
        proc.kill()
    w.czas_s = round(time.time() - start, 1)
    return w


def kopiuj_dxf(pary, katalog_docelowy) -> dict:
    """pary: [(referencja, sciezka_zrodlowa)]. Plik ladauje pod nazwa REFERENCJI,
    bo tak wskazuje GeometryPath w XML. Zwraca {referencja: sciezka_docelowa}."""
    cel = Path(str(katalog_docelowy).replace("\\", "/"))
    cel.mkdir(parents=True, exist_ok=True)
    out = {}
    for ref, zrodlo in pary:
        if not zrodlo:
            continue
        docelowy = cel / ("%s.dxf" % ref)
        shutil.copy2(str(zrodlo), str(docelowy))
        out[ref] = str(docelowy).replace("/", "\\")
    return out
