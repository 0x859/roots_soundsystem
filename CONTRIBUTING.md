# Współtworzenie

Dziękujemy za zainteresowanie projektem! Interfejs, komentarze i dokumentacja są po polsku – zgłoszenia
i pull requesty po polsku lub angielsku są mile widziane.

## Środowisko

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
.\.venv\Scripts\python main.py
```

Wymagany Windows 10/11 (WASAPI) i Python 3.11+ (projekt rozwijany na 3.14). Testy działają bez kart dźwiękowych
i bez okna (`QT_QPA_PLATFORM=offscreen`).

## Zanim wyślesz zmianę

- `.\.venv\Scripts\python -m ruff check .` – bez uwag,
- `.\.venv\Scripts\python -m pytest -q` – wszystkie testy zielone,
- zmiana w DSP lub silniku audio = najpierw test w `tests/`, potem kod (tor ma być też szybki:
  `pytest -q -s tests/test_chain.py -k performance`, mediana < 50% czasu bloku),
- końce linii CRLF (pilnują `.editorconfig` i `.gitattributes`); nie formatuj całych plików przy okazji,
- komentarze i teksty interfejsu po polsku,
- przy zmianie zachowania zaktualizuj `README.md` i `CHANGELOG.md`.

Architektura i konwencje: [CLAUDE.md](CLAUDE.md), plan i decyzje: [docs/PLAN.md](docs/PLAN.md).

## Zgłaszanie błędów

Podaj wersję z *Pomoc → O programie* (wersje Pythona i Qt są tam razem), tryb (Symulacja/Multi), urządzenia
audio i kroki do odtworzenia. Przy problemach z paczką EXE dołącz wynik `RootsSoundsystem.exe --selftest wynik.json`.
