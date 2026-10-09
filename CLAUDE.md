# Roots Soundsystem – kontekst dla Claude Code

Cyfrowy tor soundsystemu roots and culture na Windows 11 (Python 3.14, PySide6, numpy/scipy, sounddevice/WASAPI).
Pełny plan, decyzje i stan prac: `Plan.md` (sekcja „Etap 2: rozwój”). README opisuje obsługę dla użytkownika.

## Język i styl
- Rozmawiaj po polsku. Komentarze, docstringi i teksty w UI po polsku.
- Końce linii **CRLF** we wszystkich plikach (patrz `.editorconfig`, `ruff format` ma `line-ending = "cr-lf"`). Nie zmieniaj końców linii w plikach, których nie edytujesz.
- Formatowanie przy zapisie jest wyłączone celowo – nie przeformatowuj całych plików.

## Polecenia
- Testy: `.\.venv\Scripts\python -m pytest -q` (zadanie VS Code „Testy: wszystkie”).
- Test wydajności: `.\.venv\Scripts\python -m pytest -q -s tests/test_chain.py -k performance` (mediana < 50% czasu bloku).
- Lint: `.\.venv\Scripts\python -m ruff check .` – ma przechodzić bez uwag.
- Uruchomienie: `.\.venv\Scripts\python main.py`. Build EXE: `.\build_exe.ps1` (plik ma BOM – wymagany przez Windows PowerShell 5.1; po buildzie sam uruchamia `--selftest`). Spec odfiltrowuje nieużywane części Qt (czarna lista `QT_UNUSED` i wzorce QML) – nowy moduł Qt/QML w kodzie może wymagać zmiany tej listy.
- Autotest paczki (QML, ekrany, tryb edycji; wynik JSON): `main.py --selftest wynik.json` lub `RootsSoundsystem.exe --selftest wynik.json`.

## Architektura w skrócie
- `dsp/` – moduły DSP; `dsp/graph.py` (`SignalChain`) składa tor. Każdy moduł ma listę `PARAMS` (`ParamSpec`).
- `engine/params.py` – `ParamStore`: jedno źródło prawdy dla GUI, presetów, MIDI i DSP (słuchacze z `source`).
- `engine/audio_engine.py` – strumienie WASAPI, bufory kołowe, callback wyjściowy. Kod w callbackach nie może rzucać wyjątków ani alokować dużo pamięci.
- `engine/midi.py` + `engine/midi_profiles.py` – mapowanie MIDI: learn, profile (Akai MIDImix), warstwa SHIFT, przejęcie wartości (pickup), akcje `action:*`, diody przez port wyjściowy. Format zapisu JSON v2 (zgodny ze starym płaskim).
- `engine/devices.py` – gotowe układy wyjść dla kart 4-kanałowych (Focusrite Scarlett 4i4 3rd gen: słuchawki = wyjścia 3–4, Loopback = wejścia 5–6).
- `presets/` – sceny, presety EQ i syreny (JSON w `%APPDATA%\RootsSoundsystem\`); `store.PRESET_KINDS` opisuje rodzaje presetów wspólnie dla okna, QML (`PresetsView`, żądania `<kind>_apply/_save/_delete/_reset`) i Widgets (`PresetBar`).
- `version.py` – jedyne źródło wersji (SemVer; MINOR = etap planu). Przy zmianie wersji zaktualizuj też `pyproject.toml` (test pilnuje) i `CHANGELOG.md`.
- Ikona: rysunek w `ui.theme.paint_icon`, plik `assets/icon.ico` generuje `assets/generate_icon.py` (build robi to sam).
- Czysty tor: `dsp.graph.DSP_SWITCHES` (wszystkie `*.enabled`, w tym `sim.enabled` = modele kolumn) i `bypass_values()`; `presets.store.restore_state` przy starcie wyłącza moduły (ustawienie `startup/dsp` = `clean` domyślnie | `last`).
- `ui/audio_config.py` – wybór urządzeń i zapis ustawień audio bez widżetów (wspólne dla okna Audio i `ui/quick/audio.py`).
- `ui/layout_profile.py` – profil układu (JSON, bez Qt): karty, kontrolki, pady, skróty, motyw; walidacja i pliki w `%APPDATA%\RootsSoundsystem\layouts\`.
- `ui/quick/` – nowy interfejs QML osadzony w `MainWindow` przez `QQuickWidget`: `QmlParams` (parametry), `LayoutModel` + `QmlTheme`, `QmlSession` (stan i polecenia do okna, sygnał `requested`), `QmlPlots` (krzywe wykresów), pliki `qml/`. Kontekst QML: `Params`, `Profile`, `Theme`, `Session`, `Plots`.
- Każda zmiana profilu przebudowuje wszystkie karty (Repeater po `Profile.cards`) – stan, który ma przetrwać (zaznaczenie, menu karty, rozwinięcia), trzymaj w `Main.qml`, nie w `Card.qml`.
- `ui/main_window.py`, `ui/panels/`, `ui/widgets/` – stół klasyczny (Qt Widgets), dostępny w menu Widok do końca migracji.

## Sprzęt użytkownika
- Akai MIDImix (USB, kanał 1; CC i nuty opisane w `engine/midi_profiles.py` i `Plan.md`).
- Focusrite Scarlett 4i4 3rd gen. Źródło muzyki domyślnie VB-Cable; Loopback jako opcja (ryzyko pętli sprzężenia).

## Etap w toku: QML z konfigurowalnym układem
- Zrobione: LIVE i KONFIGURACJA jako karty z profilu JSON, pasek padów, tryb „Edycja układu” (inspektor, przeciąganie, cofanie, profile, import/eksport). Do zrobienia – patrz `Plan.md`, sekcja „QML – stan”.
- Podgląd QML bez okna: `QQuickWindow.setGraphicsApi(Software)` + `QT_QPA_PLATFORM=offscreen` + `QT_QPA_FONTDIR=C:/Windows/Fonts`, potem `grabFramebuffer()`.
- Zatwierdzony kierunek wizualny: ciemny stół, złoto = tor sygnału, turkus = efekty, czerwień = kill/stop; Barlow Condensed (etykiety) + IBM Plex Mono (wartości).
- Ekrany: LIVE (karty w siatce o liczbie kolumn zależnej od szerokości okna + pasek padów) i KONFIGURACJA (urządzenia, zwrotnica, kolumny/miejsce, EQ12, MIDI, sceny).
- Użytkownik chce móc dostosować **każdy** aspekt: układ to profil JSON (karty, kontrolki z parametrami `ParamStore`, pady, motyw), edytowany w trybie „Edycja układu”.
- Makiety: artefakt „Roots Soundsystem – nowy interfejs” na claude.ai (https://claude.ai/artifact/FPCv64ttVvLbMYPsUwX82F).
- Migracja panel po panelu; wersja Widgets działa do końca etapu.

## Zasady pracy
- Przed zmianą zachowania DSP lub silnika dopisz/uzupełnij test w `tests/`.
- Nie commituj bez prośby użytkownika.
