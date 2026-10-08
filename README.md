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

Wynik: `dist\RootsSoundsystem\RootsSoundsystem.exe` (ikona w zasobach EXE oraz kopia `icon.ico` obok). Skopiuj cały folder `RootsSoundsystem` — sam plik EXE nie wystarczy.

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

- **Pokrętła**: przeciąganie w pionie lub kółko myszy, Shift = precyzyjnie, dwuklik = wartość domyślna.
- **Przyciski chwilowe** (THROW, SYRENA, CRASH, KILL): lewy przycisk = aktywny przy przytrzymaniu, prawy = zatrzaśnięcie.
- **Skróty**: `1`-`5` kill pasm izolatora, `Spacja` throw echa, `S` syrena, `D` crash sprężyny, `T` tap tempo, `M` mute, `F5`-`F8` pamięci syreny (Ctrl+klik na M1-M4 zapisuje).
- **Pasek LIVE**: START/STOP, sceny, kill 1-5, THROW, SYRENA, CRASH, sweep HP/LP, master, mute i mierniki – zawsze na górze okna.
- **Stół**: dwa rzędy bez poziomego paska narzędzi; wykresy są w pierwszym rzędzie po prawej. Przy mniejszym oknie stół skaluje się (dolna granica 0.7).
- **Sceny** (pasek LIVE): pełny stan toru; wbudowane: Neutralny, Roots warm, Steppers heavy, Dub echo chamber, Plener, Słuchawki (bass feel). Własne sceny i presety EQ są zapisywane jako JSON w `%APPDATA%\RootsSoundsystem\`.
- **Urządzenia i tryb**: przycisk *Audio…* albo kliknięcie podsumowania w pasku stanu.
- **Własna IR miejsca**: panel *Kolumny i miejsce* → *Wczytaj IR…*; plik jest resamplowany do częstotliwości pracy.
- **MIDI**: menu MIDI → wybór portu → *Tryb learn*: porusz kontrolką w aplikacji, a potem elementem kontrolera. Przyciski/nuty sterują przyciskami chwilowymi i przełącznikami, CC – pokrętłami.
- Zamknięcie okna kończy program; minimalizacja chowa go do zasobnika (można wyłączyć w menu Audio).

## Struktura

| Katalog | Zawartość |
| --- | --- |
| `dsp/` | moduły DSP (biquady, EQ12, preamp, izolator, zwrotnica, efekty, mikrofon, kolumny, splot, limitery) i `graph.py` ze składającym je `SignalChain` |
| `engine/` | rejestr parametrów, silnik audio WASAPI, sterowanie MIDI |
| `presets/` | wbudowane sceny i presety EQ, zapis własnych |
| `ui/` | okno główne, panele, widżety, wykresy |
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
