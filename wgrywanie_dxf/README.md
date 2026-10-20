# Wgrywanie DXF do LANTEKA (Sheet Parts)

Aplikacja Flask: wskazujesz **wykaz roboczy** i **folder(y) z plikami DXF**, ona sprawdza
komplet, składa XML i wgrywa do LANTEKA przez **PowerSync** (`XmlImporter.exe`).
Zastępuje ręczne makro `Lantek XLS2XML - Aggregate_v7.xlsm`.

Prototyp — zbudowany 18.09.2026. Do bazy pisze wyłącznie krok „Wgraj", i tylko po
zaznaczeniu potwierdzenia.

## Dlaczego powstała — i dlaczego marszruta wchodziła sama „Laser"

To jest najważniejsze ustalenie tego projektu, potwierdzone na bazie produkcyjnej
i eksperymentem na żywym elemencie:

**LANTEK nadaje marszrutę sam, regułą ruty, która czyta pole `UData8` produktu.**
Szablony rut leżą w `MMNN_PPOO_00000100`, a warunki w kolumnie `DIS_Rules`:

| ruta | warunek | operacje |
|---|---|---|
| `L` (domyślna) | grubość ≤ 15, `UData8` bez `S` i bez `G` | 2D Cut |
| `L+G` | `UData8` zawiera `_G_`, grubość ≤ 15 | 2D Cut → Giecie |
| `P+G` | `UData8` zawiera `_G_`, grubość > 15 | 2D Cut → Giecie |
| `L+G+S` | `UData8` zawiera `GS`, grubość ≤ 15 | 2D Cut → Giecie |
| `L+S`, `L+SO`, `P`, `P+S` | odpowiednio `_S_`, `_SO_` | 2D Cut |

Lantek Expert wpisuje do `UData8` **pełną referencję elementu** — dlatego u niego
marszruta wchodzi poprawnie (w bazie 20 363 elementy z rutą `L+G`).

Makro XLS2XML wysyłało `UData1`…`UData8` **puste** (351 z 353 plików w
`C:\Lantek\importxml`). Bez tego pola żaden warunek nie pasuje i element dostaje rutę
domyślną `L`, czyli **sam laser**.

Druga, niezależna pułapka: **jawne `PRODUCT OPERATIONS` nie utrzymują się** przy
elemencie, który dostaje geometrię. Importer sortuje polecenia po tabelach, więc
`IMPORTGEO` zawsze wykonuje się po operacjach i przebudowuje marszrutę. Z 400 elementów
wgranych importem, mających geometrię i pełną marszrutę, **399 miało gięcie dopisane
ręcznie** w Lantek Expert.

**Dlatego ta aplikacja wysyła `UData8 = PrdRef` i nie wpisuje operacji na siłę.**
Potwierdzone 18.09.2026: element `10_S235_test-giecie_GS_` → ruta `L+G` →
marszruta `2D Cut → Giecie`, mimo że ma geometrię.

## Uruchomienie

```bash
cp .env.example .env          # uzupełnij hasło do bazy, jeśli jest wymagane
pip install -r requirements.txt
python app.py                 # http://127.0.0.1:5059/dxf/
```

Aplikacja musi widzieć `C:\Lantek\System\Common\XmlImporter.exe` oraz katalog
`C:\Lantek\importxml\DXF`, czyli działa na maszynie z LANTEKIEM. Wszystkie ścieżki
siedzą w `.env` / `config.py`, więc da się ją przenieść na serwer.

## Przebieg pracy

1. **Zlecenie** — wpisujesz `NN_XXXX` (np. `82_1129`). Od razu (bez skanu) pojawia się
   folder zlecenia w Technologii z podfolderami do kliknięcia oraz zamówienia sprzedaży
   z LANTEKA dla tego numeru. Folder zlecenia można zmienić na dowolny — np. podfolder
   rewizji `37_1731\DXF_37_1731-REWIZJA`; wtedy wykazy bierzemy z niego, a jego foldery DXF
   są na liście najwyżej. „Zaproponuj wykaz i foldery" proponuje wykazy (z folderu i jego
   podfolderów, robocze pierwsze) i wszystkie foldery z DXF (Technologia,
   `tmp\TMP_DXF_...`, wyniki ekstraktora). Każda ścieżka to zwykłe pole: klik
   w propozycję wpisuje ją do pola, można też wpisać własną. Folder DXF wybierasz sam,
   można kilka — przy tej samej nazwie pliku wygrywa folder wskazany wyżej.
   Pole OrdRef na bieżąco mówi, czy zamówienie już jest w LANTEKU i od której linii
   dopiszemy nowe.
2. **Kontrola przed wgraniem** — nic nie zapisuje. Raport `PRZED_*.html` + `.json`.
3. **XML** — kopiuje pliki DXF tam, gdzie widzi je LANTEK, i składa `SheetParts_*.xml`.
4. **Wgranie** — `XmlImporter.exe`, czekanie na log, log ląduje w folderze przebiegu.
5. **Kontrola po wgraniu** — odczyt z bazy: czy elementy są, z jakim materiałem
   i grubością, **jaką dostały marszrutę** i czy ilości w zamówieniu się zgadzają.

Wyniki każdego przebiegu: `data/<NN_XXXX>_<data>_<godzina>/`.
Dziennik wszystkich wgrań: `data/rejestr_wgran.jsonl`.

## Co sprawdza kontrola

| kod | poziom | znaczenie |
|---|---|---|
| `FORMULA_NIEPRZELICZONA` | STOP | wykaz ma formuły bez wyniku — otwórz i zapisz w Excelu |
| `BRAK_REFERENCJI` | STOP | pusta nazwa robocza |
| `REFERENCJA_ZA_DLUGA` | STOP | ponad 40 znaków (`PrdRef` to `nvarchar(40)`) |
| `ZNAK_SPOZA_CP1250` | STOP | XML idzie w windows-1250 |
| `DUPLIKAT_ROZNI_SIE` | STOP | ta sama referencja, ale inna grubość/gatunek/technologia |
| `DUPLIKAT_REFERENCJI` | STOP | ta sama referencja w kilku wierszach — w wykazie brakuje indeksu (domyślnie) |
| `LP_NIE_DZIELI_SIE` | STOP | wiersz `_LP` z nieparzystą ilością albo bez członu `Nst` |
| `GATUNEK_BEZ_MAPOWANIA`, `MATERIAL_NIEZNANY_LANTEKOWI` | STOP | materiału nie ma w kartotece |
| `BRAK_GRUBOSCI`, `BRAK_ILOSCI` | STOP | grubość 0 blokuje zapis produktu |
| `BRAK_DXF`, `DXF_NIE_OTWIERA`, `DXF_PUSTY` | STOP | plik geometrii |
| `DXF_ROZNE_WERSJE` | STOP | ta sama nazwa w dwóch folderach, różny rozmiar |
| `ELEMENT_INNY_W_BAZIE` | STOP | element już jest, ale z innym materiałem/grubością |
| `JUZ_W_ZAMOWIENIU` | UWAGA | element jest już linią **jakiegoś** zamówienia — wejdzie bez linii (patrz niżej) |
| `MARSZRUTA_BEZ_GIECIA` | UWAGA | technologia mówi o gięciu, a reguła LANTEKA go nie nada |
| `SCALONY_Z_WIELU_WIERSZY` | UWAGA | duplikat scalony — tylko gdy świadomie wybrano scalanie |
| `MASZYNA_POPRAWIANA` | UWAGA | reguła LANTEKA da inną maszynę niż wybrana — poprawka marszruty po imporcie |
| `REFERENCJA_ZMIENIONA` | UWAGA | referencja zmieniona ręcznie w podglądzie; plik DXF ten sam |
| `DXF_KOPIE_W_KILKU_FOLDERACH` | UWAGA | ten sam plik w kilku wskazanych folderach |
| `ILOSC_ROZJAZD` | UWAGA | kolumna ilości ≠ człon `Nst` w referencji |
| `KOD_ROZJAZD` | UWAGA | kolumna `Gięcie` ≠ kod w referencji (do LANTEKA idzie referencja) |
| `ELEMENT_JUZ_W_BAZIE` | UWAGA | import go nadpisze |

## Ponowne wgranie — da się, ale nie przez przypadek

Decyzja użytkownika (20.10.2026): ponowne wgranie ma być możliwe, ale utrudnione;
podwojenie ilości w zamówieniu tylko na wyraźne życzenie.

- **Element, który już jest linią zamówienia** (dowolnego, nie tylko wpisanego OrdRef),
  domyślnie idzie **bez linii zamówienia** — LANTEK tylko aktualizuje element.
  Numeracja linii pozostałych elementów idzie dalej bez dziur.
- **Podwojenie**: w kroku XML checkbox „dopisz je też do zamówienia — podwojenie
  ilości”, a przy wgraniu trzeba przepisać `PODWAJAM`.
- **Ponowne wgranie** = któryś element jest już w zamówieniu **albo** rejestr wgrań
  (`data/rejestr_wgran.jsonl`) ma wcześniejsze wgranie tych samych elementów (po liście
  `refy`; starsze wpisy bez listy — po numerze zlecenia). Wtedy strona pokazuje czerwoną
  ramkę z historią, a wgranie wymaga checkboxa „wgrywam ponownie świadomie” i
  przepisania numeru zamówienia (`PONOWNIE`, gdy OrdRef pusty).
- **Tuż przed importem** świeże zapytanie do bazy: jeśli element, któremu XML dopisuje
  linię, wszedł do zamówienia już po zbudowaniu XML — przerwane, zbuduj XML ponownie.
- **Jeden import naraz**: blokada w procesie aplikacji + przycisk gaśnie po kliknięciu
  (podwójne kliknięcie, druga karta).
- Kontrola po wgraniu nie zgłasza „brak linii w zamówieniu” dla elementów wgranych
  celowo bez linii.

## Marszruta — kiedy reguła LANTEKA nie wystarcza

Reguły mają realne luki, sprawdzone na 2000 elementów:

- kod **`SG`** (odwrócona kolejność) — brak reguły, wchodzi `L` bez gięcia,
- kody **`W` / `WS`** (walcowanie) — brak reguły, wchodzi `L`,
- **`GSO` przy grubości > 15** — reguła `P+G+S` sprawdza `UData1` zamiast grubości,
- kody spoza legendy, np. `MG`.

Dla takich pozycji zaznacz „popraw też marszrutę pozycjom bez gietarki". Powstanie drugi
plik `Marszruta_*.xml` (kasuje marszrutę i wpisuje ją od nowa) — **wgrywany automatycznie
zaraz po imporcie głównym**, tylko gdy główny przeszedł bez błędów. To utarty wzorzec:
w logach LANTEKA jest 937 takich usunięć, zero błędów.

## Maszyna: laser czy plazma

Decyzja użytkownika (20.10.2026): **od 20 mm plazma, poniżej laser** (16 mm na laser).
Próg i centra są w `mapowanie.json` (`plazma_od_grubosci`, `maszyny`).

Reguła LANTEKA tego **nie zapewnia**: ruta `P` (plazma) ma warunek `UData8 NOT LIKE *S*`,
a litera S jest w każdej referencji z `S235`/`S355`/`SL…`. Takie blachy (kody `O`, puste,
`SO` > 20 mm) nie pasują do żadnej reguły i dostają domyślne `L` = laser — także 20–30 mm
(np. `20_S235_SL6052994_p101_2st_O_8344_`, wgrany 19.10.2026).

- Przy kontroli tabela materiałów ma wybór maszyny **dla każdej grupy grubość+gatunek**,
  a podgląd pozycji — **wyjątek dla pojedynczej pozycji** (i edycję referencji, z
  natychmiastowym sprawdzeniem, czy taka już jest w bazie).
- Gdy przewidziana przez LANTEKA maszyna ≠ wybrana, pozycja trafia do poprawki marszruty
  (`2D Cut` na wybranej maszynie + gięcie wg kodu), wgrywanej zaraz po imporcie głównym.
- Kontrola po wgraniu sprawdza maszynę (centrum pierwszej operacji) — inna = STOP.

## Podgląd pozycji: filtry i zmiany ręczne

- **Filtry** (w przeglądarce): tekst (wszystkie słowa naraz), poziom, grubość, gatunek,
  maszyna, „LANTEK sam”, kod, stan DXF, „pokaż tylko…”. Licznik: ile pozycji i **suma sztuk**
  widocznych. „Widocznym ustaw maszynę” — zmiana dla całego przefiltrowanego zestawu.
- **Zmiany ręczne — tylko alternatywa, domyślnie nic się nie zmienia**: referencja,
  maszyna, **gatunek (MatRef wyłącznie z kartoteki INTEGRY)**, **ruta (wyłącznie z rut
  INTEGRY; wyznacza marszrutę i maszynę)**, grubość, ilość. Każda zmiana jest podświetlona
  na **fioletowo**, pod polem „było: …”; w uwagach `ZMIANA_RECZNA`. Serwer odrzuca
  materiał i rutę spoza INTEGRY.
- Zmiana materiału/grubości elementu, który **już jest w bazie** z innymi danymi, daje
  STOP `ELEMENT_INNY_W_BAZIE` — wtedy zmień też referencję na wolną.
- Formularz wysyła pełny stan zmian; zapis = ponowna kontrola. Stan w `stan.json`
  (`maszyny_grup`, `poprawki`).
- Filtr „grubość_gatunek” (np. `20_S235`) obok osobnych filtrów grubości i gatunku;
  przy każdej wartości liczba pozycji i sztuk.
- **Eksport Excel** (`services/eksport.py`): zakładki `Pozycje` i `Materialy`, zmiany ręczne
  na fioletowo, autofiltr. Plik `PODGLAD_<zlecenie>.xlsx` w folderze przebiegu odświeża się
  przy każdej kontroli (też po „Zastosuj zmiany”); przycisk „Eksport Excel” pobiera świeży
  (gdy plik jest otwarty w Excelu, zapis w folderze się nie uda — komunikat, przycisk działa).

## Zakres wgrywania i MAGAZYN

Decyzje użytkownika (20.10.2026), konfiguracja w `mapowanie.json` → `zakres`:

- Wgrywamy **tylko wiersze z wpisaną referencją**. Wiersz w zakresie bez referencji jest
  pomijany i liczony (`BEZ_REFERENCJI_POMINIETE`); STOP tylko, gdy to nieprzeliczona formuła.
- Domyślnie dodatkowo **ZAKUPY = blacha** (blacha/blachy/BLACHA…) — checkbox, można wyłączyć.
- Plusem dodaje się warunki **kolumna = wartość** (domyślnie kolumna `sprawdzenie`).
  Podpowiedzi wartości są czytane **z wybranego wykazu** (każdy ma inne), z liczbą wierszy;
  porównanie bez wielkości liter (`Z BAZY` = `z bazy`). Ta sama kolumna kilka razy = LUB
  (zakres rośnie), różne kolumny = I.
- **MAGAZYN**: gdy w kolumnach MODUŁ, komentarze dla technologów, INFO, KOOP/USŁUGA,
  MONTAŻ/WYSYŁKA — **tylko na lewo od kolumny z referencją** (na prawo bywają duplikaty) —
  stoi „MAGAZYN”, wiersza nie wgrywamy (lista na stronie kontroli i w Excelu,
  zakładka „Pominiete MAGAZYN”).
- **„MAGAZYN 2szt” / „2SZT” / „2 sztuki”** (MAGAZYN z liczbą) = część z magazynu, ilość
  pomniejszona: wiersz **wgrywamy**, ale jest podświetlony na bursztynowo (strona i Excel),
  uwaga `MAGAZYN_CZESCIOWO`, filtr „częściowo z magazynu”. Ilości aplikacja nie zmienia —
  w razie potrzeby popraw ręcznie w podglądzie.

Kolumna z referencją i z ilością: domyślnie `Nazwa` i `Anz.`, obok ▾ rozwija listę
nagłówków wybranego wykazu (najpierw `Nazwa…` / `Anz.`, `ILOŚĆ…`), klik wpisuje do pola.
Dopasowanie bez wielkości liter i kropek, wygrywa lewa kolumna; nieznana nazwa → wybór
automatyczny + uwaga `ZAKRES` w kontroli.

## Lewe i prawe (LP) oraz duplikaty

- Wiersz wykazu z końcówką `_LP` (np. `3_S235_41549_p1_2st_GS_1129_LP`, ilość 2) to **dwa
  elementy**: `…_1st_GS_1129_L` i `…_1st_GS_1129_P`, każdy po połowie sztuk — dokładnie
  tak, jak nazwane są pliki DXF (to one są prawdą, wykaz służy do sprawdzenia). Indeks
  na końcu też działa: `_LP_1` → `_L_1` i `_P_1`.
- **Duplikat referencji domyślnie = STOP**: w wykazie przy duplikacie powinien być indeks.
  Scalanie (ilość z pierwszego wiersza / suma) tylko świadomie, wyborem na stronie startowej.
- Kontrola pokazuje **bilans**: wierszy blachy + drugie strony LP = oczekiwanych elementów DXF,
  obok liczba pozycji po kontroli.

## Przewidywanie marszruty

Aplikacja czyta reguły z bazy i przewiduje rutę przed wgraniem. Sprawdzone na 2000
elementów z nadaną rutą: **99,9% trafień** co do obecności gięcia, bez ani jednego
przeoczenia (nigdy nie powie „bez gięcia", gdy LANTEK gięcie nada). Nazwa ruty bywa
inna niż przewidziana, ale operacje te same — ruty `L`, `L+S`, `L+SO`, `P` mają
identyczną marszrutę (`2D Cut`), więc realnie różnicuje je tylko gięcie.

## Pułapki, które już zapłaciliśmy

- **Propozycje nie w ciasteczku sesji.** Lista wykazów i folderów potrafi przekroczyć
  4 KB ciasteczka — przeglądarka po cichu je odrzuca. Trzymamy ją w
  `data/_propozycje/<id>.json`, w sesji tylko `prop_id`.

- **`LineNum` w zamówieniu** — klucz kolizji to `(OrdRef, LineNum)`, a kolizja
  **nadpisuje linię** (49 udokumentowanych przypadków). Numerację kontynuujemy po
  `max(LineNum)`, nigdy od 1.
- **Surowy `&` w wartości** psuje cały plik — import kończy się na 0 poleceń.
  Generator escapuje `& < > "`, makro tego nie robiło.
- **`Length` i `Width` > 0** przełączają geometrię na prostokąt parametryczny i DXF jest
  ignorowany. Nie wysyłamy tych pól.
- **Ostrzeżenie `already exists ... update is executed`** jest normalne. Liczy się
  `Commands with error`.
- **Brak linii gięcia w pliku DXF nie jest błędem** — produkcyjne DXF z bazy nie mają
  żadnych oznaczeń gięcia (warstwa `0`/`L`/`51`, kolor 7). Rysujemy je tylko przy P/L
  albo gięciu pod skosem. Dlatego ta kontrola jest wyłącznie informacyjna.
- **Ścieżki UNC w kodzie zapisujemy ukośnikami w przód** (`//QNAP-ENERGO/...`).
  Wersja z backslashami gubi znak przy przepisywaniu pliku i `Path` widzi `\SERWER`.
- **Podfolder w `GeometryPath`** — wszystkie 14 962 historyczne importy wskazywały
  pliki płasko w `DXF\`. Kopiujemy do podfolderu per zlecenie (pełna ścieżka w XML).
  Gdyby import zgłosił `Cannot find geometry file`, ustaw `DXF_PODFOLDER=0` w `.env`.
- **Import bez limitu czasu** (19.10.2026, zlecenie `64_8344`). Importer zakłada pusty
  log na starcie, a treść pisze dopiero po wszystkich poleceniach, wykonując je grupami:
  `PRODUCTS` → `IMPORTGEO` (DXF, to trwa) → `SALE ORDERS` → `SALE ORDER LINES`. Limit
  60 s ubił importer w trakcie geometrii: produkty weszły, zamówienia i linii nie było.
  Teraz czekamy do kompletnego logu; bez logu kończymy tylko wtedy, gdy importer sam się zamknął.
- **Okno postępu za przeglądarką** — serwis odpala importer w tle, Windows otwiera okno
  pod przeglądarką. `powersync._okno_na_wierzch` wyciąga je na wierzch (TOPMOST → NOTOPMOST).

## Pliki

```
app.py                     uruchomienie, port 5059
config.py / .env           ścieżki LANTEKA, dostęp do bazy, korzenie do propozycji
mapowanie.json             materiały, kody technologii, aliasy kolumn wykazu
modules/dxf/routes.py      pięć kroków przebiegu
services/wykaz.py          czytanie wykazu roboczego (pierwsza zakładka, po nagłówkach)
services/dxf_check.py      dopasowanie plików, gabaryt, kontrola otwieralności
services/ruty.py           reguły rut LANTEKA + przewidywanie marszruty
services/marszruta.py      kod technologii -> operacje
services/kontrola.py       reguły PRZED i PO
services/xml_sheetparts.py generator XML (cp1250, CRLF, escapowanie)
services/powersync.py      XmlImporter.exe + odczyt logu
services/lantek_db.py      baza LANTEKA — WYŁĄCZNIE SELECT
services/raport.py         raporty HTML/JSON
services/zlecenie.py       propozycje po numerze zlecenia, rejestr wgrań
services/zamowienia.py     lista zamówień sprzedaży w pamięci (jak w FORMATKA+CZASY_PALENIA)
testy/                     skrypty sprawdzające (uruchamiane ręcznie)
```

## Testy

```bash
python testy/t_wykaz.py              # parser wykazu na przykładzie 82_1129
python testy/t_xml_generator.py      # nasz XML kontra XML makra
python testy/t_ruty_giecie.py        # trafność przewidywania marszruty (baza)
python testy/t_kontrola_e2e.py 82_1129
python testy/t_e2e_flask.py 82_1129  # cały przebieg do XML, bez wgrywania
python testy/t_formularz_start.py 37_1731   # podpowiedzi folderu/zamówień, własny folder
python testy/t_ponowne_wgranie.py           # ochrona przed ponownym wgraniem (atrapa importu)
python testy/t_lp_maszyna.py                # LP, maszyna, edycja referencji, drugi import (82_1129)
python testy/t_rejestr_zrodel.py            # rejestr zrodel DXF: dopisywanie, backup, plik zajety
python testy/t_zakres.py 75_8981            # zakres (blacha, warunki z plusem), MAGAZYN, MAGAZYN 2szt
```

Testy z atrapą importu ustawiają `REJESTR_ZRODEL_DIR` na katalog tymczasowy — nie piszą
do prawdziwego rejestru na QNAP. Nowy test, który przechodzi przez „Wgraj”, musi zrobić to samo.

## Rejestr źródeł wgranych DXF

Po każdym wgraniu (gdy importer się uruchomił) aplikacja dopisuje do
`\\Qnap-energo\baza\.data\python\wgrywanie-do-lanteka-dxf\rejestr_zrodel_dxf.xlsx`
jeden wiersz na folder, z którego wzięła pliki DXF: **folder DXF, wykaz, zamówienie
sprzedaży, uwagi**, a dalej data, zlecenie, liczba plików z folderu, wynik importu,
folder przebiegu (`services/rejestr_zrodel.py`, ścieżka w `REJESTR_ZRODEL_DIR`).
Przed zapisem poprzednia wersja idzie do `backup\`. Gdy plik jest otwarty w Excelu,
wiersze czekają w `oczekujace.jsonl` i dopisują się przy następnym wgraniu.

## Stan na 18.09.2026 - potwierdzone dzialanie

Pierwsze wgranie z aplikacji, zlecenie testowe `199_9999`: **10 polecen, 0 bledow**.
Trzy elementy w kartotece, kazdy z ruta `L+G` i marszruta `2D Cut -> Giecie`,
zamowienie `199_9999_BLACHY` zalozone z trzema liniami. Podfolder w sciezce
geometrii (`C:\Lantek\importxml\DXF99_9999\...`) zadzialal bez zastrzezen.

## Czego jeszcze nie ma

- **Sprawdzanie daszków** — pole w formularzu jest, ale wyłączone. Daszek to blacha,
  do której dochodzą otwory pod uniwersalną giętą nakładkę; stare pliki z bazy ich nie
  mają. Definicja do doprecyzowania.
- Wgrywanie na **prawdziwym zleceniu** — pierwsza próba `64_8344` (18 elementów,
  19.10.2026) padła na limicie 60 s (opis w pułapkach); po poprawce do powtórzenia.
