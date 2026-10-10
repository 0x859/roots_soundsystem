# Historia zmian

Format: [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/), wersje według [SemVer](https://semver.org/lang/pl/).
MINOR odpowiada etapowi planu (`docs/PLAN.md`), PATCH – poprawkom w jego obrębie. Wersja jest w `version.py`.

## [Nieopublikowane]

### Dodane
- Funkcje dub sesji według badania w `docs/DUB_SESJA.md`:
  - izolator przed efektami (`iso.position` = „Muzyka (przed efektami)”): kill tnie muzykę, a ogony echa i sprężyny, mikrofon i syrena wybrzmiewają; przeniesienie w trakcie grania bez trzasków;
  - DRY CUT (`preamp.cut`, pad i skrót `C`): chwilowe wyciszenie suchej muzyki z zachowaniem efektów;
  - FX PANIC (`out.fx_panic`, karta WYJŚCIE, skrót `P`): wycisza i czyści echo i sprężynę, przytrzymany trzyma je wyciszone; ostrzeżenie „ECHO ↑ PANIC” w nagłówku LIVE, gdy echo się rozkręca;
  - THROW MIC (`mic.throw`, skrót `V`): chwilowo cały mikrofon do echa; SWELL (`echo.swell`, skrót `W`): przytrzymanie podnosi sprzężenie do samooscylacji;
  - MIDImix: SOLO + Rec Arm 1/2/3/6 = FX PANIC, THROW MIC, SWELL, MONO.
- Animacja powitalna diod kontrolera po podłączeniu (start z podpiętym MIDImix, podpięcie w trakcie, wybór portu): fala przez przyciski MUTE/REC ARM od lewej i błysk (~1,2 s), potem diody wracają do stanu parametrów. Sterowanie działa w trakcie animacji. Wyłączana przyciskiem **POWITANIE** na karcie MIDI – KONTROLER albo w menu MIDI (ustawienie `midi/intro`, domyślnie włączona); włączenie od razu ją pokazuje.

### Zmienione
- MIDImix: Rec Arm 6 to teraz DRY CUT (MONO przeniesione na SOLO + Rec Arm 6).
- Sprzężenie echa zmienia się płynnie (rampa 150 ms) – także przy kręceniu gałką.

### Poprawione
- Przycisk chwilowy na kontrolerze puszczony po zmianie warstwy SHIFT (SOLO puszczone lub wciśnięte w trakcie) zwalnia ten sam parametr, zamiast zostawić go włączonego.
- Odłączenie kontrolera (lub awaria portu), zmiana profilu, wyczyszczenie albo wczytanie mapy MIDI w chwili trzymania przycisku chwilowego zostawiały parametr włączony na stałe (syrena grała bez końca, FX PANIC trzymał efekty wyciszone, DRY CUT – muzykę). Teraz takie parametry są puszczane, a przełącznik wciśnięty w tej chwili działa przy pierwszym naciśnięciu po ponownym podłączeniu.
- CRASH wciśnięty przy trzymanym FX PANIC odpalał się dopiero po puszczeniu PANIC – teraz jest ignorowany (jak przy wyłączonej sprężynie).
- MIDI: awaria portu wejściowego pokazuje komunikat o odłączeniu; błąd wysyłania na diody zamyka port wyjściowy; import mapy w starym formacie zastępuje całą mapę (bez resztek warstwy SHIFT i diod poprzedniego profilu), a diody starej mapy gasną przy każdym wczytaniu.
- Profil układu zapisany przed dodaniem nowych kontrolek (SWELL, THROW MIC, FX PANIC, położenie izolatora, przełącznik modeli kolumn, pad DRY CUT i ich skróty) nie pokazywał ich – sceny zmieniały te parametry bez widocznej kontrolki. Profil ma teraz wersję (2): przy wczytaniu starszego dochodzą brakujące kontrolki w miejscach jak w układzie domyślnym, a usunięte przez użytkownika w bieżącej wersji nie wracają.

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
