# Roots Soundsystem

Cyfrowe odtworzenie toru soundsystemu roots and culture na Windows 11: przedwzmacniacz z nasyceniem lampowym i filtrami sweep, echo taśmowe, reverb sprężynowy, syrena dubowa, mikrofon MC z talkoverem, 5-drożny izolator z kill, aktywna zwrotnica i dwa tryby wyjścia:

- **Symulacja** – modele kolumn (scoopy, bass biny, mid horny, tweetery) i akustyka miejsca (splot z IR) na słuchawkach lub zwykłych głośnikach stereo,
- **Multi** – osobne drogi (sub / bass / mid / top) na kanałach wielokanałowej karty dźwiękowej, z limiterem dla każdej drogi.

## Tor sygnału

```
CABLE Output ─► Preamp ─┬─► Mikser ─► (+ powroty echa i sprężyny) ─► EQ12 ─► Izolator ─► Zwrotnica ─┬─► Kolumny ─► Miejsce ─► stereo
Mikrofon ─► kanał MC ───┤     │                                                                     └─► Limitery dróg ─► kanały karty
Syrena ─────────────────┘     └─► send / throw ─► echo taśmowe, sprężyna
```

## Instalacja

1. Python 3.11+ (testowane na 3.14).
2. W katalogu projektu:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python -m pip install -r requirements.txt
   ```

   `numba`, `mido` i `pygame-ce` są opcjonalne. Bez `numba` sweep HP/LP preampu jest aktualizowany co blok (zamiast w każdej próbce). Na Pythonie 3.14 `python-rtmidi` nie ma gotowych pakietów, dlatego MIDI korzysta z backendu `pygame-ce`.

3. Uruchomienie z katalogu `roots_soundsystem`: `.\.venv\Scripts\python main.py` albo `python main.py` (jeśli systemowy Python nie ma PySide6, `main.py` uruchamia się ponownie przez `.venv`).

## Kompilacja EXE (Windows)

Pakiet onedir (folder z EXE, ikoną i DLL-ami Qt / PortAudio / libsndfile):

```powershell
.\.venv\Scripts\python assets\generate_icon.py
.\.venv\Scripts\python -m pip install pyinstaller
.\build_exe.ps1
```

Wynik: `dist\RootsSoundsystem\RootsSoundsystem.exe` (ikona w zasobach EXE oraz kopia `icon.ico` obok). Skopiuj cały folder `RootsSoundsystem` — sam plik EXE nie wystarczy. Paczka ma ok. 400 MB: spec pomija nieużywane części Qt (WebEngine, 3D, Multimedia, wykresy Qt, style Controls inne niż Basic, tłumaczenia) oraz testy, dokumentację i przykłady bibliotek. Największe pozostałe części to LLVM dla numba (~118 MB), scipy i Qt. Skrypt po zbudowaniu sam uruchamia autotest paczki i przerywa się, jeśli autotest nie przejdzie.

Sprawdzenie paczki bez klikania (EXE nie ma konsoli, wynik trafia do pliku JSON; tymczasowe ustawienia, bez dźwięku):

```powershell
Start-Process .\dist\RootsSoundsystem\RootsSoundsystem.exe -ArgumentList "--selftest", "$env:TEMP\roots_selftest.json" -Wait
Get-Content $env:TEMP\roots_selftest.json
```

`"ok": true` oznacza, że interfejs QML załadował się bez błędów, a ekrany LIVE, KONFIGURACJA i tryb edycji działają. To samo z kodu: `.\.venv\Scripts\python main.py --selftest wynik.json`.

## VB-Cable (przechwytywanie dźwięku systemu)

1. Pobierz darmowy sterownik [VB-Cable](https://vb-audio.com/Cable/), rozpakuj i uruchom `VBCABLE_Setup_x64.exe` jako administrator. Uruchom ponownie komputer.
2. *Ustawienia → System → Dźwięk*: jako urządzenie wyjściowe ustaw **CABLE Input (VB-Audio Virtual Cable)**. Od teraz wszystkie aplikacje grają do kabla.
3. W panelu dźwięku (`mmsys.cpl`) → *Nagrywanie* → *CABLE Output* → *Właściwości* → *Zaawansowane* ustaw format **2 kanały, 48000 Hz** (taki sam jak w aplikacji).
4. W aplikacji: **Muzyka** = *CABLE Output*, **Wyjście** = słuchawki/głośniki (lub karta wielokanałowa), opcjonalnie **Mikrofon**. Kliknij **START**.

Jeśli CABLE Output nie zostanie znaleziony, aplikacja pokaże tę instrukcję (Pomoc → Instalacja VB-Cable).

## Tryb Multi (prawdziwy wielodrożny system)

1. Otwórz **Ustawienia audio…** (pasek LIVE albo menu Audio), wybierz kartę wielokanałową jako wyjście i **Tryb: Multi**.
2. W panelu **Zwrotnica** ustaw liczbę dróg (2-4), nachylenie (LR2 / LR4), punkty podziału, wzmocnienia, opóźnienia (wyrównanie czasowe stosów) i polaryzację.
3. W oknie ustawień audio przypisz każdej drodze kanały L/R (lub tylko jeden kanał – wtedy droga idzie w mono) i ustaw progi limiterów dróg.
4. Aplikacja blokuje start przy błędnym mapowaniu (kanał poza zakresem, ten sam kanał dla dwóch dróg, droga bez kanału) i prosi o potwierdzenie przed startem.

Zabezpieczenia: droga top jest zawsze filtrowana górnoprzepustowo (punkt podziału nie niżej niż 800 Hz), subsonic HP (domyślnie 25 Hz) chroni głośniki niskotonowe, każda droga ma limiter brickwall z wyprzedzeniem, a wyjście startuje z 1,5-sekundowym narastaniem głośności. Przed pierwszym uruchomieniem skręć wzmacniacze.

## Obsługa

### Nowy interfejs (QML)

Domyślnie aplikacja otwiera nowy interfejs: ciemny stół z kartami (złoto = tor sygnału, turkus = efekty, czerwień = kill/stop). Menu **Widok** przełącza między nim (`Ctrl+L`) a stołem klasycznym (`Ctrl+K`); wybór jest zapamiętywany.

- **LIVE / KONFIGURACJA**: przełącznik w nagłówku. LIVE to karty do grania (preamp, echo, sprężyna, syrena, izolator, mikrofon, wyjście) i pasek padów; KONFIGURACJA – urządzenia i kanały, wykresy (odpowiedź toru, zwrotnica, analizator widma), zwrotnica, limitery, EQ 12 pasm z presetami, kolumny i miejsce (z wczytywaniem własnej IR), podział izolatora. Pełny stół klasyczny – przycisk w nagłówku KONFIGURACJI.
- **Urządzenia i kanały** (KONFIGURACJA): muzyka i para kanałów (np. Loopback 5–6), wyjście i gotowe układy (Scarlett 4i4: Symulacja z kopią na słuchawki, Multi 2/3/4 drogi), mikrofon i jego wejście, tryb Symulacja/Multi, blok, mapowanie dróg na kanały L/R (jeden kanał = mono) z kontrolą błędów. Zmiany są robocze – do silnika trafiają po **ZASTOSUJ** (PRZYWRÓĆ cofa). Okno *Ustawienia audio…* nadal działa i pokazuje to samo.
- **Czysty tor przy starcie**: domyślnie aplikacja startuje z wyłączonymi wszystkimi modułami DSP (preamp, mikrofon, echo, sprężyna, EQ, izolator, modele kolumn, miejsce) – muzyka przechodzi bez zmian, zostają tylko zwrotnica, ochrona (subsonic, limitery) i master. Ustawienia gałek są zapamiętane. Przycisk **DSP n/8** w nagłówku wyłącza wszystko albo przywraca poprzedni zestaw modułów (także akcja `action:dsp_toggle` dla skrótu/MIDI). Zmiana: karta Urządzenia → „Przy starcie aplikacji: CZYSTY TOR / OSTATNI STAN” albo menu Audio.
- Kliknięcie tytułu karty zwija ją do samego nagłówka (stan jest zapamiętywany).
- Przy kontrolerze MIDI z przejęciem wartości (pickup) niebieski znacznik na gałce/suwaku pokazuje położenie elementu kontrolera, dopóki nie „złapie” wartości.
- Liczba kolumn kart zależy od szerokości okna – w wąskim oknie karty układają się jedna pod drugą zamiast się zmniejszać.
- Karta z przełącznikiem **ON/OFF** w nagłówku włącza moduł; **WIĘCEJ · n** rozwija rzadziej używane kontrolki.
- **✎ UKŁAD** – tryb edycji układu (wszystko można zmienić):
  - przeciągnij kartę za `⋮⋮` lub kontrolkę, aby zmienić kolejność (także między kartami); niebieska kreska pokazuje miejsce wstawienia, strefa na dole przenosi kartę na koniec;
  - przeciągnij prawą krawędź karty (szerokość 1–4 kolumn), dolną (dowolna wysokość w pikselach, dwuklik = automatyczna) albo złoty róg (oba naraz) – podgląd pokazuje nowy rozmiar; gdy karta jest niższa niż treść, wnętrze się przewija; prowadnice pokazują kolumny siatki;
  - `⋯` lub prawy przycisk na karcie: menu (rozmiar, liczba kontrolek w rzędzie, ekran, kolor, zwinięcie, duplikat, usunięcie);
  - złoty uchwyt S/M/L w rogu zaznaczonej kontrolki zmienia jej rozmiar;
  - klawiatura: `←`/`→` przesuwa zaznaczoną kontrolkę lub kartę (`↑`/`↓` – karta o rząd), `Shift`+strzałki – rozmiar karty, `+`/`−` – rozmiar kontrolki, `Del` – usuń, `Ctrl+Z`/`Ctrl+Y` – cofnij/ponów, `Ctrl+D` – duplikuj kartę, `Esc` – odznacz / wyjdź;
  - szerokość inspektora można zmienić, przeciągając uchwyt między stołem a inspektorem;
  - inspektor **KONTROLKA**: cel (parametr, akcja `action:*` albo widok `view:*`), typ (gałka, suwak, przycisk, pad, wartość), rozmiar S/M/L, etykieta, kolor, skrót klawiszowy (kliknij pole i naciśnij klawisz), przypisanie MIDI (learn);
  - **KARTA**: tytuł, szerokość 1–4 kolumn, wysokość (auto lub px, także `Shift+↑/↓`), rzędy siatki 1–3, liczba kontrolek w rzędzie, zwinięcie w LIVE, widoczność (LIVE/KONFIGURACJA/obie), zwijanie „Więcej”, kolor, przełącznik i informacja w nagłówku;
  - **PADY**: zawartość i kolejność paska padów, położenie (dół/góra/ukryty), wysokość;
  - **MOTYW**: skala 80–160%, gęstość, styl gałek, ramki kontrolek w trybie gry, minimalna szerokość karty, kolory, czcionki;
  - wyszukiwarka u dołu dodaje parametr do zaznaczonej karty (albo pad);
  - COFNIJ/PONÓW, profile układu (ZAPISZ JAKO, przełączanie, usuwanie), IMPORT/EKSPORT JSON, RESET do układu domyślnego.
- Profile układu to pliki JSON w `%APPDATA%\RootsSoundsystem\layouts\` (zapis automatyczny).
- Czcionki: interfejs używa *Barlow Condensed* i *IBM Plex Mono*, jeśli są zainstalowane albo leżą w `assets/fonts/` (licencja OFL); w przeciwnym razie Bahnschrift i Consolas z Windows.

### Wspólne dla obu interfejsów

- **Pokrętła**: przeciąganie w pionie lub kółko myszy, Shift = precyzyjnie, dwuklik = wartość domyślna.
- **Przyciski chwilowe** (THROW, SYRENA, CRASH, KILL): lewy przycisk = aktywny przy przytrzymaniu, prawy = zatrzaśnięcie.
- **Skróty** (domyślne, zmienialne w trybie ✎ UKŁAD): `1`-`5` kill pasm izolatora, `Spacja` throw echa, `S` syrena, `D` crash sprężyny, `T` tap tempo, `M` mute, `F5`-`F8` pamięci syreny (Ctrl+klik na M1-M4 zapisuje). W trybie edycji układu skróty są wyłączone.
- **Pasek LIVE** (stół klasyczny): START/STOP, sceny, kill 1-5, THROW, SYRENA, CRASH, sweep HP/LP, master, mute i mierniki – zawsze na górze okna.
- **Stół klasyczny**: dwa rzędy bez poziomego paska narzędzi; wykresy są w pierwszym rzędzie po prawej. Przy mniejszym oknie stół skaluje się (dolna granica 0.7).
- **Sceny** (pasek LIVE): pełny stan toru; wbudowane: Neutralny, Roots warm, Steppers heavy, Dub echo chamber, Plener, Słuchawki (bass feel). Własne sceny i presety są zapisywane jako JSON w `%APPDATA%\RootsSoundsystem\` (`scenes\`, `eq\`, `siren\`).
- **Presety EQ** (karta EQ 12 pasm / panel EQ): m.in. Flat, Dub (sub i dół), Steppers, Lovers rock, Plener, Mała i Duża sala, Winyl, Ochrona góry, Stare nagranie, Radio/telefon. Wybór od razu ustawia pasma; własne oznaczone gwiazdką.
- **Presety syreny** (karta SYRENA / panel SYRENA): gotowe brzmienia – Klasyczna (dub siren), Wznosząca (riser), Spadająca bomba, Laser, Alarm (dwa tony), Whoop, Ptak (ćwierk), Sub drop. Preset ustawia brzmienie (fala, wysokość, LFO, sweep, release, poziom, send echo), ale nie wyzwala syreny. W QML: lista, `+` zapisuje bieżące brzmienie pod nową nazwą, `×` usuwa własne, `↺` przywraca domyślne. Pamięci M1–M4 działają jak dotąd (szybkie przełączanie skrótem/MIDI).
- **Wersja**: w tytule okna i w *Pomoc → O programie* (razem z wersjami Pythona i Qt – przydatne przy zgłaszaniu problemów); EXE ma ją we *Właściwościach → Szczegóły*. Historia zmian: `CHANGELOG.md`.
- **Urządzenia i tryb**: przycisk *Audio…* albo kliknięcie podsumowania w pasku stanu.
- **Własna IR miejsca**: panel *Kolumny i miejsce* → *Wczytaj IR…*; plik jest resamplowany do częstotliwości pracy.
- **MIDI**: menu MIDI → wybór portu → *Tryb learn*: porusz kontrolką w aplikacji, a potem elementem kontrolera. Przyciski/nuty sterują przyciskami chwilowymi i przełącznikami, CC – pokrętłami.
- **Akai MIDImix**: podłączony kontroler jest wykrywany sam (także po odłączeniu i ponownym podłączeniu oraz gdy Windows zmieni numer portu) i dostaje gotowy profil. Wybór „— bez kontrolera —” wyłącza automatyczne łączenie.
- **Mapa kontrolera** (KONFIGURACJA → *MIDI – KONTROLER*, menu *MIDI → Podgląd mapy kontrolera…* albo przycisk **MIDI** w nagłówku): rysunek MIDImix z podpisem każdej gałki, suwaka i przycisku (moduł + parametr), wartościami na żywo, diodami MUTE/REC ARM i podświetleniem elementu, którym właśnie ruszasz. Kropka na gałce i czerwona kreska na suwaku pokazują położenie elementu, który czeka na przejęcie wartości. Przełącznik **NORMAL / SHIFT (SOLO)** pokazuje drugą warstwę (włącza się sam, gdy trzymasz SOLO; elementy bez własnego przypisania w SHIFT są przygaszone). Kliknięcie elementu otwiera edycję: przypisanie w obu warstwach, **USUŃ** i wyszukiwarka parametrów i akcji (m.in. DSP on/off, pamięci syreny M1–M4, sceny, tap). Dalej: port, profil, LEARN, PRZEJĘCIE, **EKSPORT/IMPORT** mapy (JSON) i WYCZYŚĆ. Przypisania spoza mapy (np. z learn na innym kontrolerze) są na liście pod rysunkiem. Nagłówek LIVE pokazuje stan: kropka = połączony, „MIDI · SHIFT” = trzymane SOLO.
- Zamknięcie okna kończy program; minimalizacja chowa go do zasobnika (można wyłączyć w menu Audio).

## Struktura

| Katalog | Zawartość |
| --- | --- |
| `dsp/` | moduły DSP (biquady, EQ12, preamp, izolator, zwrotnica, efekty, mikrofon, kolumny, splot, limitery) i `graph.py` ze składającym je `SignalChain` |
| `engine/` | rejestr parametrów, silnik audio WASAPI, sterowanie MIDI |
| `presets/` | wbudowane sceny, presety EQ i syreny, zapis własnych (`PRESET_KINDS` – wspólne dla obu interfejsów) |
| `ui/` | okno główne, stół klasyczny (panele, widżety, wykresy), profil układu `layout_profile.py` |
| `ui/quick/` | nowy interfejs: most parametrów, model układu, motyw i sesja dla QML; pliki `qml/` |
| `tests/` | testy jednostkowe, wydajności i GUI |

## Testy i wydajność

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m pytest -q -s tests/test_chain.py -k performance
```

Test wydajności liczy pełny tor (wszystkie moduły, splot z IR sali betonowej) na bloku 512 próbek przy 48 kHz i wymaga mediany poniżej 50% czasu bloku. Na maszynie deweloperskiej wynik to około 24% (z `numba` i bez). W trakcie pracy obciążenie jest widoczne w pasku stanu; przy przekroczeniu 80% aplikacja proponuje większy blok lub wyłączenie splotu.

Znane ograniczenie: przy 5 wąskich pasmach izolatora kill tłumi pasmo w jego środku o około 38-57 dB (48 dB/okt), a nie 60 dB – granicę wyznacza nachylenie sąsiednich filtrów.

## Darmowe wtyczki VST z efektami dubowymi

Aplikacja nie hostuje wtyczek, ale można ich używać w DAW (np. do przygotowania dubplate'ów) albo w torze systemowym przez [Equalizer APO](https://sourceforge.net/projects/equalizerapo/) z nakładką Peace (obsługuje VST2) lub przez [LightHost](https://www.hermannseib.com/english/lighthost.htm).

- **Echo / delay**: TAL-Dub-X (TAL Software, delay taśmowy w stylu dub), Valhalla Supermassive i Valhalla Freq Echo (Valhalla DSP), NastyDLA (Variety of Sound), Kilohearts Essentials (m.in. Delay, Filter).
- **Reverb**: TAL-Reverb-4 (plate w stylu vintage), Dragonfly Reverb (open source: room, hall, plate).
- **Saturacja / taśma**: Ferric TDS (Variety of Sound), Airwindows Consolidated (setki darmowych, otwartych efektów, w tym emulacje taśmy i konsolet).
- **Filtry**: TAL-Filter-2.
- **Syreny**: u-he Tyrell N6 (darmowy syntezator analogowy – dobre źródło syren i efektów „laser”).
- **Analiza**: Voxengo SPAN (analizator widma).

Dostępność i licencje wtyczek należy sprawdzić na stronach producentów.
