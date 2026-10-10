# Dub sesja na żywo – badanie i propozycje

Badanie z 2026-10-10: co warto dodać do aplikacji pod prowadzenie dub sesji (mikser jako instrument, echo taśmowe, sprężyna, kill, syreny, MC, dubplate'y, praca z MIDImix). Najpierw sprawdzono, co już jest w kodzie i w `docs/PLAN.md`, potem zebrano braki. Stan wdrożenia – sekcja „Dub sesja” w `docs/PLAN.md`.

## 1. Stan obecny

Aplikacja ma już większość klasycznego zestawu dubowego, więc część propozycji to rozszerzenia istniejących modułów.

- **Preamp** (`dsp/preamp.py`): drive i asymetria lampy, bass/treble, sweep HP 20–1000 Hz i LP 300–20k Hz z rezonansem, `preamp.mono`, sendy `preamp.echo_send` i `preamp.spring_send`.
- **Echo taśmowe** (`dsp/fx_echo.py`):
  - czas 20–1500 ms, sync 1/2–1/16 z BPM, tap tempo (`ui/dub_actions.py`);
  - feedback do 1,2 (samooscylacja), HP/LP i `tanh` w pętli, wow/flutter;
  - glide daje efekt pitch jak w taśmie;
  - chwilowy `echo.throw` ustawia send na 1,0 (`SignalChain._configure_sends` w `dsp/graph.py`).
- **Sprężyna** (`dsp/fx_spring.py`): decay, tone, return, `spring.crash`. Wejście ma tylko z preampu.
- **Syrena** (`dsp/fx_siren.py`): 4 fale, LFO w 5 kształtach, sweep, release, send do echa. Pamięci M1–M4, 8 presetów wbudowanych i własne.
- **Mikrofon MC** (`dsp/mic.py`): gate, stały HP 100 Hz, kompresor, 3-pasmowy EQ, send do echa, talkover z głębokością.
- **Izolator 5-pasmowy z kill** (`dsp/isolator.py`): kill to −40 dB z rampą 5 ms. Przed zmianami z tego badania działał tylko na sumie: muzyka + mikrofon + syrena + powroty echa i sprężyny.
- **Sceny**: 6 wbudowanych, w tym „Dub echo chamber” (`presets/builtin.py`). Wczytują się natychmiast przez `set_many`; Bank ◀/▶ = poprzednia/następna scena.
- **MIDImix** (`engine/midi_profiles.py`):
  - zajęte są wszystkie 24 gałki w obu warstwach, 8 suwaków, master, Mute 1–8 (kill i włączniki FX), Rec Arm 1–8 (THROW, SYRENA, CRASH, TAP, TALKOVER, MONO, następna pamięć syreny, MUTE);
  - działa pickup i diody, ale diody pokazują tylko warstwę NORMAL.
- **Pady i skróty** (`ui/layout_profile.py`): KILL ×5, THROW, SYRENA, CRASH, TAP. Akcje `action:*` w `ACTIONS` (`engine/midi_profiles.py`).
- **Wyjście**: Symulacja z kopią na słuchawki 3–4 (`sim_mirror`) albo Multi. Muzyka wchodzi jednym stereo (VB-Cable lub Loopback).
- **Zaplanowane w etapie 2.5, jeszcze niezrobione**: nagrywanie do WAV, odtwarzacz plików, ewentualnie hostowanie VST.

Budżet CPU: pełny tor ok. 24% czasu bloku przy limicie 50%, więc zostaje ok. 25 punktów procentowych zapasu.

## 2. Propozycje

Nakład: S = do 1 dnia, M = kilka dni, L = tydzień i więcej.

### Efekty i tor (DSP)

| Propozycja (co daje operatorowi) | Gdzie w architekturze | MIDImix | Nakład / ryzyko | Prio |
| --- | --- | --- | --- | --- |
| **Izolator przed FX („kill zostawia ogon”).** Kill na sumie tnie też ogon echa, MC i syrenę. W dubie wycisza się źródło, a echo dalej brzmi. Opcja „Muzyka (przed FX)”: kill działa tylko na muzykę. | `iso.position` (choice: Suma / Muzyka) w `dsp/isolator.py`; kolejność w `SignalChain._process_block`; `response()` dla wykresu | bez zmian (Mute 1–5) | M. Koszt CPU ten sam, moduł tylko się przesuwa. | **P1** |
| **DRY CUT.** Chwilowe wyciszenie suchej muzyki; echo, sprężyna, MC i syrena grają dalej. Klasyczny „drop do echa”, z THROW gest „throw & cut”. | `preamp.cut` (bool, `momentary=True`, `scene=False`), rampa 5 ms na suchej ścieżce; pad | Rec Arm 6 (dziś MONO; MONO na SHIFT+Rec 6) | S. Bez ryzyka. | **P1** |
| **FX PANIC i wskaźnik samooscylacji.** Przy feedbacku do 1,2 na prawdziwym systemie (Multi) uciekające echo jest realnym zagrożeniem. Akcja wycisza i czyści echo i sprężynę (fade ok. 30 ms); karta ECHO świeci na czerwono przy feedbacku >1 lub rosnącym powrocie. | `action:fx_flush` w `ACTIONS` i etykietach `layout_profile`; flaga, a reset w wątku audio (jak `Switch.on_reset`), bez `buf.fill` z wątku GUI; miernik powrotu | SHIFT+Rec Arm 1 | S. Ryzyko wyścigu, jeśli reset zrobi się z wątku GUI. | **P1** |
| **Głowice RE-201.** Tryby 1 / 2 / 3 / 2+3 / 1+2+3 przy równym rozstawie głowic dają rytmiczne, synkopowane powtórzenia. | `echo.heads` (choice) w `TapeEcho._process`: 1–3 odczyty z interpolacją, sprzężenie z sumy | gałka SHIFT albo tylko GUI | S/M. Każda głowica to dodatkowy wektorowy odczyt. | P2 |
| **Echo → sprężyna (tryby 5–11 RE-201).** Ogon echa idzie w sprężynę – „mokry” dub. | `echo.to_spring` (0–1); wejście sprężyny = `x·send + e·to_spring` | gałka SHIFT | S | P2 |
| **SWELL.** Przytrzymanie podnosi feedback do ok. 1,05 z rampą, puszczenie przywraca poprzedni. Ręczne „podkręcanie pętli” jak na konsoli. | `echo.swell` (momentary); `configure` podmienia `fb` | SHIFT+Rec Arm 3 | S. Ryzyko ograniczają `tanh` w pętli, limiter i FX PANIC. | P2 |
| **Filtr sendu echa.** Echo dostaje tylko pasmo werbla lub wokalu z miksu stereo (osobnych ścieżek nie ma). | `echo.send_hp`, `echo.send_lp` (SOS liczony tylko przy send >0) | gałki SHIFT | S. Na gęstych aranżacjach efekt słaby. | P2 |
| **Rewind / tape stop.** Hamowanie taśmy albo „wheel-up” od tyłu z bufora ostatnich ok. 3 s; po puszczeniu muzyka wraca z fade-in. Mikrofon zostaje na żywo. | nowy `dsp/fx_spinback.py`, prealokowany bufor (ok. 2,3 MB), odczyt ze zmienną prędkością; `action:rewind`, `action:tapestop` | SHIFT+Bank ◀ | M. Przy VB-Cable utwór i tak trzeba zatrzymać w odtwarzaczu (pełny rewind dopiero z wbudowanym odtwarzaczem). | P2 |
| **„Big Knob” krokowy.** Sweep HP przeskakuje po stałych progach jak Altec 9069B u Tubby'ego. | `preamp.hp_steps` (bool) kwantuje `preamp.hp` | – | S | P3 |
| **Ping-pong / stereo echo.** Różne czasy dla L i R. | `echo.spread` | – | S | P3 |

### Sterowanie na żywo (performance)

| Propozycja | Gdzie | MIDImix | Nakład / ryzyko | Prio |
| --- | --- | --- | --- | --- |
| **Pady-makra chwilowe.** Przytrzymanie ustawia część parametrów (np. „tylko bas i bęben” = kill low-mid, high-mid i top), puszczenie przywraca poprzednie. | nowy rodzaj presetu w `PRESET_KINDS` („makro”) i `action:macro:<nazwa>` z trybem hold | SHIFT+Rec Arm 5–8 | M. Przywracanie wartości przy zmianie sceny w trakcie trzymania. | P2 |
| **Morphing scen.** Płynne przejście do sceny w ustawionym czasie (0–8 s); bool przełączają się na końcu. | `scene/morph_ms`; timer GUI co ok. 30 ms woła `set_many` (poza callbackiem) | Bank ◀/▶ bez zmian | M. Pickup przy rekonfiguracji filtrów. | P2 |
| **Throw mikrofonu.** Chwilowy send mikrofonu do echa na 1,0 – „zdubowanie” ostatniego słowa MC. | `mic.throw` (momentary), logika jak `echo.throw` w `_configure_sends` | SHIFT+Rec Arm 2 | S | **P1** |
| **Sync LFO syreny z BPM.** Rate syreny w wartościach nutowych z `echo.bpm`. | `siren.lfo_sync` (choice) | – | S | P3 |

### MIDI / kontroler

| Propozycja | Gdzie | Nakład | Prio |
| --- | --- | --- | --- |
| **Warstwa SHIFT dla Rec Arm i Bank.** SHIFT+Rec Arm odpada do warstwy NORMAL (`MidiController.target_for`), więc jest 8+2 wolnych miejsc na gesty z tabel wyżej. Rec Arm nie zmienia nut przy SOLO, więc rozróżnia je tylko warstwa programowa. | `shift_mapping` w `_midimix()` | S | **P1** |
| **Diody: warstwa SHIFT i tempo.** Przy trzymanym SOLO diody pokazują stan `shift_mapping`; dioda TAP (Rec 4) miga w tempie `echo.bpm`. | `_led_value` i `_on_params` z SHIFT; mruganie w `flush_leds` z timera okna | S | P2 |
| **MIDI clock na wejściu.** Echo idzie za tempem odtwarzacza (np. Traktor). | `midi.handle` dla 0xF8 | M. pygame-ce może słabo obsługiwać komunikaty czasu rzeczywistego. | P3 |

### Przepływ sesji (selekcja, odsłuch, nagrywanie)

| Propozycja | Gdzie | Nakład / ryzyko | Prio |
| --- | --- | --- | --- |
| **Nagrywanie setu** (etap 2.5). Stereo miksu po izolatorze, a przed zwrotnicą; w trybie Multi to jedyny sensowny miks. Znaczniki zmian scen i opcjonalnie stały bufor ostatnich 60 s („nagraj to, co właśnie było”). | callback kopiuje blok do prealokowanego `RingBuffer` (`dsp/common.py`); wątek zapisujący przez `soundfile` (WAV/FLAC float); `action:record` | M. Nigdy I/O w callbacku; przepełnienie liczyć w `EngineStats`. | **P1** |
| **Pady dubplate'ów i sampli.** 8 slotów one-shot: jingle, ID soundu, airhorn, laser, specjały. Pliki wczytane i przeliczone na fs przy załadowaniu; opcjonalny send do echa. Pierwszy krok odtwarzacza. | `dsp/sampler.py` (sumowanie głosów bez alokacji), `sample.level`, `sample.echo_send`, `action:sample:<n>`, `view:samples`, presety banków | M. Pamięć ok. 1,5 MB na 10 s stereo float32. | **P1** |
| **Odsłuch na słuchawkach (Scarlett 3–4).** Do wyboru: kopia, „podsłuch echa” (nastawienie czasu i feedbacku przed wyrzuceniem na system) albo split L = suma, R = podsłuch. | rozszerzenie `sim_mirror` o źródło; `out.phones_level`; dodatkowa szyna w `SignalChain` | M. W Multi 2×stereo i 4×mono wyjścia 3–4 to drogi – tylko w Symulacji. | P2 |
| **Podpowiedź BPM z wejścia.** Autokorelacja obwiedni z `tap_in` co ok. 2 s w wątku GUI; „≈74 BPM – zastosuj”, nic nie ustawia samo. | `ui/dub_actions.py` lub nowy moduł; wartość w `LiveHeader` | M. W one drop łatwo o pomyłkę ×2 / ÷2. | P2 |

### Mikrofon / MC

| Propozycja | Gdzie | Nakład | Prio |
| --- | --- | --- | --- |
| Send mikrofonu i syreny do sprężyny | `mic.spring_send`, `siren.spring_send` w `_configure_sends` | S | P2 |
| **Detektor sprzężenia mikrofonu.** Wąski, utrzymujący się pik w FFT z miernika mikrofonu daje ostrzeżenie i proponuje notch jednym kliknięciem. | analiza w wątku GUI; `mic.notch_hz`, `mic.notch_on` (1 biquad) | M | P2 |
| Regulowany HP mikrofonu (60–300 Hz) zamiast stałego 100 Hz | `mic.hp_hz` | S | P3 |
| Drugi mikrofon (wejście 2 Scarlett, dwóch MC lub singjay) | druga instancja `MicChannel` z prefiksem `mic2.` | M | P3 |

### UI

| Propozycja | Gdzie | Nakład | Prio |
| --- | --- | --- | --- |
| Karta „DUB GESTY”: DRY CUT, THROW MIC, SWELL, PANIC, REWIND, sample; gotowe pady w profilu domyślnym | `default_profile()`, pady | S | P2 |
| Kontrolka XY (dwa parametry jednym gestem: czas × feedback albo HP × LP) | nowy typ `xy` z `param2` w `layout_profile` i Inspector | M | P3 |
| Wskaźnik tempa (mruga z BPM) i licznik nagrywania w `LiveHeader` | `QmlSession` | S | P3 |

## 3. Top 5 – kolejność wdrożenia

1. **Izolator przed FX + DRY CUT.** Największa zmiana charakteru gry przy małym koszcie: kill i drop przestają ucinać ogony i MC. Koszt CPU bez zmian.
2. **FX PANIC i wskaźnik samooscylacji.** Bezpieczeństwo przed graniem na prawdziwym systemie (Multi), na istniejącym mechanizmie `Switch` i resetu w wątku audio.
3. **Warstwa SHIFT dla Rec Arm i Bank + `mic.throw` + SWELL.** Kontroler jest pełny; bez nowych miejsc nowe gesty nie trafią pod palce.
4. **Nagrywanie setu** (etap 2.5). Archiwum sesji i materiał na dubplate'y; osobny wątek zapisu i prealokowany bufor.
5. **Pady dubplate'ów i sampli.** Pierwszy krok odtwarzacza; jingle i specjały. Potem rewind, morphing scen i głowice RE-201.

## 4. Czego nie robić / pułapki

- **Hostowanie VST** w callbacku Pythona: GIL, nieprzewidywalna latencja, awaria wtyczki zabija tor. Jeśli w ogóle – w osobnym procesie; README wskazuje Equalizer APO i LightHost.
- **Separacja ścieżek w czasie rzeczywistym** (Demucs i podobne): wielokrotność budżetu CPU. Zamiast tego filtr sendu echa.
- **Sprężyna jako splot z IR** obok splotu miejsca: koszt dwóch splotów; model allpassowy wystarcza.
- **Pełne decki DJ-skie** (crossfader, waveform, biblioteka): poza zakresem. Selekcję prowadzi zewnętrzny odtwarzacz przez VB-Cable.
- **Loopback jako źródło przy odsłuchu lub nagrywaniu na 3–4**: ryzyko pętli sprzężenia (`ui/audio_config.py`).
- **Callback audio**: żadnego I/O ani alokacji o zmiennym rozmiarze; bufory nowych modułów w `__init__`; wersja bez numba wektorowa.
- **Nowe moduły z `.enabled`** trafiają do `DSP_SWITCHES` i licznika „DSP n/8”: `Switch(on_reset=…)` + test w `tests/test_switching.py`. Sampler nie musi mieć `.enabled`.
- **Każda nowa akcja** do `ACTIONS` i etykiet w `layout_profile` (test pilnuje nadzbioru). Gesty chwilowe: `momentary=True, scene=False`.
- **Nie przypisywać ciągłych parametrów do SHIFT na suwakach 1–5**: dziś odpadają do izolatora, a pickup na żywo myli.

## 5. Źródła

- Roland Space Echo RE-201 – tryby, głowice, intensity: [gearnews](https://www.gearnews.com/?p=176600), [Roland Articles – Tips and Tricks RE-201](https://articles.roland.com/?p=88324), [Animagraffs](https://animagraffs.com/roland-re-201-space-echo), [Effects Database](https://www.effectsdatabase.com/model/roland/re201), [Sound On Sound – Stardust 201](https://www.soundonsound.com/reviews/cherry-audio-stardust-201?amp)
- King Tubby, filtr HP, Altec 9069B „Big Knob”: [Wikipedia – King Tubby](https://en.wikipedia.org/wiki/King_Tubby), [Sound On Sound – KTBK](https://www.soundonsound.com/news/audio-merge-ktbk-passive-filter), [AudioThing – Dub Filter](https://www.audiothing.net/effects/dub-filter/), [Soundgas](https://soundgas.com/?p=60642)
- Rewind, selekcja, dubplate'y: [Dub-Stuy – Wheel It Up (L. Fintoni)](https://www.dub-stuy.com/wheel-it-up-history-of-the-rewind/), [Sonicfield – selector](https://sonicfield.org/wiki/selector), [Clash – Dubplate Culture](https://www.clashmusic.com/?p=88249), [Mixcloud – Ras IKEL](https://www.mixcloud.com/RasIKEL/), [The World – Mini Mart Hi-Power](https://theworld.org/stories/2014/06/04/roots-sound-system-mini-mart-hi-power-explained)
- Techniki miksu dub (wyciszenie źródła z ogonem echa, podkręcanie feedbacku, send werbla, dropouty): [Waves – dub mixing tips](https://www.waves.com/dub-mixing-tips-daniel-boyle), [Steinberg forum](https://forums.steinberg.net/t/mixer-effects-set-up/649459), [KVR forum](https://www.kvraudio.com/forum/viewtopic.php?p=8160223), [DJ TechTools forum](https://forum.djtechtools.com/t/emulating-traktors-fx-routing-for-dub-style-echoes-in-ableton/72127), [Ableton forum](https://forum.ableton.com/viewtopic.php?p=715661)
