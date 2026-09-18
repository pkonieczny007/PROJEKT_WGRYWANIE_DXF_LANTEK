# -*- coding: utf-8 -*-
"""Konfiguracja aplikacji. Wszystko sciezkowe idzie przez .env, zeby dalo sie
uruchomic lokalnie i na serwerze bez zmiany kodu."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def _p(zmienna, domyslnie):
    return os.getenv(zmienna, domyslnie)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-wgrywanie-dxf")
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024

    # --- LANTEK / PowerSync (XmlImporter.exe wgrywa XML do bazy SQL) -------
    XMLIMPORTER_EXE = _p("XMLIMPORTER_EXE", r"C:\Lantek\System\Common\XmlImporter.exe")
    XMLIMPORTER_USER = _p("XMLIMPORTER_USER", "SYSADM")
    XMLIMPORTER_PASS = _p("XMLIMPORTER_PASS", "")
    LANTEK_DXF_DIR = _p("LANTEK_DXF_DIR", r"C:\Lantek\importxml\DXF")
    # Czy kopiowac pliki DXF do podfolderu per zlecenie (DXF\82_1129\...).
    # Porzadkuje katalog, ale UWAGA: wszystkie 14 962 historyczne importy
    # wskazywaly pliki PLASKO w DXF\. Podfolder jest bezpieczny tylko dlatego,
    # ze GeometryPath niesie pelna sciezke. Gdyby import zglosil
    # "Cannot find geometry file" - ustaw tu 0 i powtorz.
    DXF_PODFOLDER = _p("DXF_PODFOLDER", "1") not in ("0", "", "false", "False")
    IMPORTER_LOG_DIR = _p("IMPORTER_LOG_DIR", r"C:\Lantek\importxml\Importer log")
    IMPORT_TIMEOUT_S = int(_p("IMPORT_TIMEOUT_S", "600"))

    # --- baza (TYLKO SELECT) ----------------------------------------------
    DB = {
        "driver": _p("INTEGRA_DB_DRIVER", "ODBC Driver 17 for SQL Server"),
        "server": _p("INTEGRA_DB_SERVER", r"192.168.13.5\LANTEKSQL2019"),
        "database": _p("INTEGRA_DB_NAME", "Energosolver_DB_0_9"),
        "username": _p("INTEGRA_DB_USER", "sa"),
        "password": _p("INTEGRA_DB_PASS", ""),
        "timeout": int(_p("INTEGRA_DB_TIMEOUT", "15")),
    }

    # --- wyniki -------------------------------------------------------------
    DATA_DIR = Path(_p("DATA_DIR", str(ROOT / "data")))
    REJESTR = DATA_DIR / "rejestr_wgran.jsonl"

    # --- gdzie szukac wykazu i DXF po numerze zlecenia (propozycje) ---------
    # UWAGA: sciezki UNC zapisujemy UKOSNIKAMI W PRZOD. Wersja z backslashami
    # ("\\\\SERWER\\udzial") gubi jeden znak przy przepisywaniu pliku przez
    # powloke i Path widzi wtedy '\SERWER' - katalog od korzenia, ktorego nie ma.
    KORZENIE_TECHNOLOGIA = [
        "//QNAP-ENERGO/Technologia/2026",
        "//QNAP-ENERGO/Technologia/2025",
    ]
    KORZENIE_DXF = [
        # {zl} = 82_1129, {nn} = 82, {rok} = 2026
        "//QNAP-ENERGO/Technologia/{rok}/{zl}",
        "//QNAP-ENERGO/tmp/TMP_DXF_z_bazy_do_zmiany_nazwy_{rok}/{zl}_zmiana",
        "C:/Python_CLaude/EKSTRAKTOR_DXF/EKSTRAKTOR_DXF-home-V3/wyniki/{zl}",
    ]
    POMIJANE_FOLDERY = {"archiwum", "_png", "_kontrola_wymiarow", "__pycache__",
                        "prototyp3", "_galeria", "backup"}
    GLEBOKOSC_SKANU = 3
