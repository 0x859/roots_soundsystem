# Historia zmian

Format: [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/), wersje według [SemVer](https://semver.org/lang/pl/).
MINOR odpowiada etapowi planu (`docs/PLAN.md`), PATCH – poprawkom w jego obrębie. Wersja jest w `version.py`.

## [0.2.0] – 2026-10-09

Etap 2 (w toku): nowy interfejs QML z konfigurowalnym układem.

### Dodane
- Profil kontrolera Akai MIDImix (warstwa SHIFT, przejęcie wartości, akcje, diody) i gotowe układy wyjść dla Focusrite Scarlett 4i4.
- Mapa kontrolera MIDI (karta „MIDI – KONTROLER”): rysunek MIDImix z przypisaniami, warstwy NORMAL/SHIFT, wartości i diody na żywo, edycja przypisań, eksport/import mapy; wskaźnik MIDI w nagłówku LIVE.
- Automatyczne łączenie z MIDImix: wykrycie po podłączeniu, ponowne połączenie po odłączeniu (także pod innym numerem portu). Do kontrolera można przypisać DSP on/off i pamięci syreny M1–M4.
- Interfejs QML: ekrany LIVE i KONFIGURACJA z kart opisanych profilem JSON, pasek padów, tryb „Edycja układu” (inspektor, przeciąganie, zmiana szerokości i wysokości kart, cofanie, profile, import/eksport).
- Urządzenia i mapowanie kanałów bezpośrednio w QML, wczytywanie własnej IR, wykresy (odpowiedź toru, zwrotnica, analizator widma).
- Start z czystym torem (moduły DSP wyłączone; przełącznik DSP n/8), przełącznik modeli kolumn `sim.enabled`.
- Presety syreny: 8 wbudowanych brzmień i własne presety; 10 nowych presetów EQ (Dub, Steppers, Lovers rock, Plener, sale, Winyl, Ochrona góry, lo-fi, Radio).
- Wersja w tytule okna, okno *Pomoc → O programie*, zasób wersji w EXE, autotest paczki `--selftest`.

### Poprawione
- Moduły DSP po wyłączeniu i ponownym włączeniu odgrywały resztki sprzed wyłączenia (echo, sprężyna, pogłos miejsca, stany filtrów – przy ciszy nawet do −0,5 dBFS), a przełączanie dawało trzaski; CRASH wciśnięty przy wyłączonej sprężynie odpalał się po jej włączeniu. Teraz krótkie przenikanie i czysty stan po każdym włączeniu – z ustawieniami zmienionymi w czasie wyłączenia (czas echa i sweep preampu od razu docelowe, bez przewijania).
- Układ kart: rzędy wypełniają szerokość (bez dziur na dużych ekranach), skala dopasowana do okna, karty same rozwijają „WIĘCEJ”, gdy jest miejsce.

### Zmienione
- Repozytorium gotowe do publikacji: licencja MIT, `CONTRIBUTING.md`, CI (GitHub Actions: ruff + pytest na Windows), `.gitattributes`, plan w `docs/PLAN.md`.
- Nowa ikona (głośnik na ciemnym kafelku z paskiem roots) we wszystkich rozmiarach 16–256 px; pasek zadań Windows pokazuje ją także przy starcie z kodu.
- Paczka EXE odchudzona z 727 do ok. 400 MB; build sam uruchamia autotest.

## [0.1.0] – 2026-10-08

Etap 1: kompletny tor na Qt Widgets – preamp, echo taśmowe, sprężyna, syrena, mikrofon MC z talkoverem, izolator 5-drożny, zwrotnica, tryby Symulacja i Multi, sceny i presety EQ, MIDI learn, build EXE.
