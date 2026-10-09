"""Wielopasmowy podział Linkwitz-Riley w drzewie z kompensacją allpass.

Pasmo k przechodzi przez allpassy wszystkich wyższych punktów podziału, dzięki
czemu suma pasm jest allpassem, a jej amplituda jest płaska.
"""

from __future__ import annotations

import numpy as np

from .biquad import SOSFilter, lr_allpass, lr_highpass, lr_hp_sign, lr_lowpass, response


class BandSplitter:
    def __init__(self, fs: float, freqs: list[float], order: int, channels: int = 2):
        self.fs = fs
        self.order = order
        self.channels = channels
        self.freqs = list(freqs)
        self.sign = lr_hp_sign(order)
        n = len(self.freqs)
        self._lp = [SOSFilter(channels=channels) for _ in range(n)]
        self._hp = [SOSFilter(channels=channels) for _ in range(n)]
        self._ap = [SOSFilter(channels=channels) for _ in range(n)]
        self.set_freqs(self.freqs)

    @property
    def n_bands(self) -> int:
        return len(self.freqs) + 1

    def _design(self, freqs):
        lp = [lr_lowpass(f, self.order, self.fs) for f in freqs]
        hp = [lr_highpass(f, self.order, self.fs) for f in freqs]
        ap = []
        for k in range(len(freqs)):
            rows = [lr_allpass(f, self.order, self.fs) for f in freqs[k + 1:]]
            ap.append(np.vstack(rows) if rows else None)
        return lp, hp, ap

    def reset(self) -> None:
        for f in (*self._lp, *self._hp, *self._ap):
            f.reset()

    def set_freqs(self, freqs: list[float]) -> None:
        freqs = list(freqs)
        if len(freqs) != len(self.freqs):
            raise ValueError("Liczba punktów podziału nie może się zmienić")
        self.freqs = freqs
        lp, hp, ap = self._design(freqs)
        self._lp_sos, self._hp_sos, self._ap_sos = lp, hp, ap
        for k in range(len(freqs)):
            self._lp[k].set_sos(lp[k])
            self._hp[k].set_sos(hp[k])
            if ap[k] is not None:
                self._ap[k].set_sos(ap[k])

    def process(self, x: np.ndarray) -> list[np.ndarray]:
        bands = []
        rest = x
        n = len(self.freqs)
        for k in range(n):
            low = self._lp[k].process(rest)
            if self._ap_sos[k] is not None:
                low = self._ap[k].process(low)
            bands.append(low)
            rest = self._hp[k].process(rest)
            if self.sign < 0:
                rest = -rest
        bands.append(rest)
        return bands

    def responses(self, freqs: np.ndarray) -> list[np.ndarray]:
        out = []
        rest = np.ones(len(freqs), dtype=complex)
        for k in range(len(self.freqs)):
            low = rest * response(self._lp_sos[k], freqs, self.fs)
            if self._ap_sos[k] is not None:
                low = low * response(self._ap_sos[k], freqs, self.fs)
            out.append(low)
            rest = rest * response(self._hp_sos[k], freqs, self.fs) * self.sign
        out.append(rest)
        return out
