"""Pomocnicze funkcje DSP: przeliczenia dB, rampy parametrów, bufor kołowy."""

from __future__ import annotations

import threading

import numpy as np


def db2lin(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def lin2db(x: float, floor: float = -120.0) -> float:
    return float(20.0 * np.log10(x)) if x > 10 ** (floor / 20) else floor


def gain_from_db(db: float, kill_floor: float | None = None) -> float:
    if kill_floor is not None and db <= kill_floor:
        return 0.0
    return db2lin(db)


class Ramp:
    """Liniowa rampa wartości o stałym czasie przejścia.

    Cel ustawia wątek sterujący, wątek audio pobiera kolejne bloki. Gdy wartość
    jest stała, `block` zwraca skalar, co pozwala uniknąć zbędnych alokacji.
    """

    def __init__(self, value: float, ramp_ms: float, fs: float):
        self.target = float(value)
        self._cur = float(value)
        self._last_target = self.target
        self._len = max(1, int(round(ramp_ms * fs / 1000.0)))
        self._step = 0.0

    @property
    def value(self) -> float:
        return self._cur

    def set(self, target: float) -> None:
        self.target = float(target)

    def snap(self, value: float | None = None) -> None:
        if value is not None:
            self.target = float(value)
        self._cur = self.target
        self._last_target = self.target

    def block(self, n: int):
        t = self.target
        if t != self._last_target:
            self._last_target = t
            self._step = (t - self._cur) / self._len
        if self._cur == t:
            return t
        vals = self._cur + self._step * np.arange(1, n + 1)
        if self._step > 0:
            np.minimum(vals, t, out=vals)
        else:
            np.maximum(vals, t, out=vals)
        self._cur = float(vals[-1])
        return vals[:, None]

    def is_silent(self) -> bool:
        return self._cur == 0.0 and self.target == 0.0


SWITCH_MS = 15.0


class Switch:
    """Włącznik modułu: krótkie przenikanie (bez trzasków) i czysty stan po każdym ponownym włączeniu.

    `set` woła wątek sterujący (configure), `block` – wątek audio. `block(n)` zwraca None, gdy moduł
    jest wyłączony i już wyciszony (nie trzeba go liczyć), w przeciwnym razie wzmocnienie ścieżki
    modułu: 1.0 albo tablicę (n, 1) w trakcie przenikania. Gdy wyciszony moduł zostaje włączony,
    `block` raz woła `on_reset` (reset stanu modułu) – w wątku audio, więc bez wyścigu z konfiguracją,
    i dopiero po wszystkich zmianach ustawień z czasu wyłączenia (czas echa, sweep od razu docelowe).
    Bez tego wyłączony moduł zamrażał bufory i filtry, a po włączeniu odgrywał resztki sprzed minut.
    Moduł woła `set` na końcu `configure`, żeby reset widział już nowe ustawienia.
    """

    def __init__(self, fs: float, on: bool = True, ms: float = SWITCH_MS, on_reset=None):
        self.on = bool(on)
        self.ramp = Ramp(1.0 if self.on else 0.0, ms, fs)
        self.on_reset = on_reset
        self._silent = not self.on
        self._started = False
        self._flush = False

    def set(self, on: bool) -> None:
        target = 1.0 if on else 0.0
        if not self._started:  # konfiguracja przed pierwszym blokiem obowiązuje od razu, bez przenikania
            self.on = bool(on)
            self.ramp.snap(target)
            self._silent = not self.on
            return
        if self._flush:  # czyszczenie w toku: rampę prowadzi `block`, po resecie wróci do `on`
            self.on = bool(on)
            return
        # najpierw cel rampy, potem flaga: wątek audio nie zobaczy `on` przy rampie jeszcze na 0
        self.ramp.set(target)
        self.on = bool(on)

    def flush(self) -> None:
        """Wyciszenie, czysty stan (`on_reset`) i powrót – np. FX PANIC na rozkręconym echu.

        Działa do końca nawet wtedy, gdy zaraz po nim przyjdzie `set(True)` (naciśnięcie krótsze niż
        przenikanie). Przed pierwszym blokiem nie ma czego czyścić.
        """
        if not self._started:
            return
        self._flush = True
        self.ramp.set(0.0)

    def block(self, n: int):
        self._started = True
        if self._flush:
            if not self.ramp.is_silent():
                self.ramp.set(0.0)  # `set` z wątku sterującego mógł się minąć z `flush`
                return self.ramp.block(n)
            self._flush = False
            self._silent = True  # ponowne włączenie poniżej woła `on_reset`
            if self.on:
                self.ramp.set(1.0)
        if self.on:
            if self._silent:
                self._silent = False
                if self.on_reset is not None:
                    self.on_reset()
        elif self._silent:
            return None
        elif self.ramp.is_silent():
            self._silent = True
            return None
        return self.ramp.block(n)


def crossfade(dry: np.ndarray, wet: np.ndarray, g) -> np.ndarray:
    """Ścieżka modułu w torze według wzmocnienia z `Switch.block` (1.0 = sam moduł)."""
    if isinstance(g, float) and g == 1.0:
        return wet
    return dry + (wet - dry) * g


def one_pole_coef(tau_s: float, n: int, fs: float) -> float:
    """Współczynnik zbliżenia do celu po `n` próbkach dla stałej czasowej `tau_s`."""
    if tau_s <= 0:
        return 1.0
    return float(1.0 - np.exp(-n / (tau_s * fs)))


class RingBuffer:
    """Bufor kołowy ramek audio (wiele kanałów) dla wymiany między strumieniami."""

    def __init__(self, capacity: int, channels: int):
        self.capacity = int(capacity)
        self.channels = int(channels)
        self._buf = np.zeros((self.capacity, self.channels), dtype=np.float32)
        self._r = 0
        self._w = 0
        self._count = 0
        self._lock = threading.Lock()
        self.overflows = 0

    def __len__(self) -> int:
        return self._count

    def clear(self) -> None:
        with self._lock:
            self._r = self._w = self._count = 0

    def write(self, data: np.ndarray) -> None:
        n = len(data)
        if n == 0:
            return
        with self._lock:
            if n > self.capacity:
                data = data[-self.capacity:]
                n = self.capacity
            free = self.capacity - self._count
            if n > free:
                drop = n - free
                self._r = (self._r + drop) % self.capacity
                self._count -= drop
                self.overflows += 1
            end = self._w + n
            if end <= self.capacity:
                self._buf[self._w:end] = data
            else:
                k = self.capacity - self._w
                self._buf[self._w:] = data[:k]
                self._buf[: n - k] = data[k:]
            self._w = end % self.capacity
            self._count += n

    def read(self, n: int, out: np.ndarray) -> int:
        """Czyta do `out[:n]`; zwraca liczbę faktycznie odczytanych ramek (reszta zerowana)."""
        with self._lock:
            k = min(n, self._count)
            end = self._r + k
            if end <= self.capacity:
                out[:k] = self._buf[self._r:end]
            else:
                m = self.capacity - self._r
                out[:m] = self._buf[self._r:]
                out[m:k] = self._buf[: k - m]
            self._r = end % self.capacity
            self._count -= k
        if k < n:
            out[k:n] = 0.0
        return k

    def discard(self, n: int) -> None:
        with self._lock:
            n = min(n, self._count)
            self._r = (self._r + n) % self.capacity
            self._count -= n


class DelayLine:
    """Opóźnienie całkowitoliczbowe o zmiennej długości (wyrównanie czasowe dróg)."""

    def __init__(self, channels: int):
        self.channels = channels
        self.delay = 0
        self._hist = np.zeros((0, channels))

    def set_delay(self, samples: int) -> None:
        self.delay = max(0, int(samples))

    def reset(self) -> None:
        self._hist = np.zeros((0, self.channels))

    def process(self, x: np.ndarray) -> np.ndarray:
        d = self.delay
        if d == 0 and len(self._hist) == 0:
            return x
        h = self._hist
        if len(h) != d:
            if len(h) > d:
                h = h[len(h) - d:]
            else:
                h = np.vstack([np.zeros((d - len(h), self.channels)), h])
        buf = np.vstack([h, x]) if d else x
        out = buf[: len(x)]
        self._hist = buf[len(buf) - d:].copy() if d else np.zeros((0, self.channels))
        return out


class Tap:
    """Podsłuch sygnału (mono) do analizatora widma; GUI czyta ostatnie próbki."""

    def __init__(self, size: int = 8192):
        self.size = size
        self._buf = np.zeros(size, dtype=np.float32)
        self._w = 0
        self.peak = 0.0

    def push(self, x: np.ndarray) -> None:
        mono = x.mean(axis=1) if x.ndim == 2 else x
        n = len(mono)
        if n >= self.size:
            self._buf[:] = mono[-self.size:]
            self._w = 0
        else:
            end = self._w + n
            if end <= self.size:
                self._buf[self._w:end] = mono
            else:
                k = self.size - self._w
                self._buf[self._w:] = mono[:k]
                self._buf[: n - k] = mono[k:]
            self._w = end % self.size
        p = float(np.max(np.abs(x))) if n else 0.0
        self.peak = max(p, self.peak * 0.85)

    def latest(self, n: int) -> np.ndarray:
        n = min(n, self.size)
        idx = (self._w - n + np.arange(n)) % self.size
        return self._buf[idx].astype(np.float64)
