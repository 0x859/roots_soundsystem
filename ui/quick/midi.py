"""Kontroler MIDI dla QML: port, profil, podgląd mapy (układ fizyczny + przypisania) i edycja przypisań.

Stan mapy odświeża się po zmianie `MidiController.revision`, stan „na żywo” (pozycje elementów,
aktywność, SHIFT) – w `tick()` wołanym z timera okna, tylko gdy coś się zmieniło.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Property, QObject, Signal, Slot

from engine.midi import MidiController, element_name
from engine.midi_profiles import ACTIONS, PROFILES

# skrót modułu nad etykietą parametru na mapie (etykiety same bywają dwuznaczne: „Powrót”, „Poziom”)
MODULES = {
    "preamp": "PREAMP", "echo": "ECHO", "spring": "SPRĘŻYNA", "siren": "SYRENA", "mic": "MIC",
    "iso": "IZOLATOR", "xo": "ZWROTNICA", "sim": "KOLUMNY", "room": "MIEJSCE", "eq": "EQ",
    "out": "WYJŚCIE", "action": "AKCJA",
}
FX_MODULES = ("echo", "spring", "siren")
KILL_PREFIXES = ("iso.kill.", "out.mute", "xo.mute.")


class QmlMidi(QObject):
    stateChanged = Signal()
    liveChanged = Signal()
    selectionChanged = Signal()
    portRequested = Signal(str)  # okno otwiera port (zapis w ustawieniach, komunikaty o błędach)
    fileRequested = Signal(str)  # "export" | "import" – okno pokazuje okno wyboru pliku

    def __init__(self, controller: MidiController, parent=None):
        super().__init__(parent)
        self.ctl = controller
        self._ports: list[str] = []
        self._rev = -1
        self._flags: tuple = ()
        self._strips: list[dict] = []
        self._others: list[dict] = []
        self._live: tuple = ()
        self._hw: dict[str, float] = {}
        self._activity: dict[str, int] = {}
        self._last = ""
        self._selected = ""
        self._shift_view = False
        self.refreshPorts()
        self.tick()

    # --- opisy celów ---
    def _label(self, target: str | None) -> str:
        if not target:
            return ""
        spec = self.ctl.store.specs.get(target)
        return spec.label if spec is not None else ACTIONS.get(target, target)

    @staticmethod
    def _module(target: str | None) -> str:
        return MODULES.get((target or "").split(".")[0].split(":")[0], "") if target else ""

    @staticmethod
    def _tone(target: str | None) -> str:
        t = target or ""
        if t.startswith(KILL_PREFIXES):
            return "kill"
        if t.split(".")[0] in FX_MODULES:
            return "fx"
        return "accent" if t else "none"

    def _describe(self, mid: str, target: str | None) -> dict[str, Any]:
        spec = self.ctl.store.specs.get(target or "")
        return {
            "target": target or "",
            "label": self._label(target),
            "module": self._module(target),
            "tone": self._tone(target),
            "bool": spec is not None and spec.kind == "bool",
            "action": bool(target and target in ACTIONS),
        }

    # --- odświeżanie ---
    def _rebuild(self) -> None:
        c = self.ctl
        strips = []
        on_map: set[str] = set()
        for strip in c.layout:
            elements = []
            for e in strip.elements:
                sid = e.shift_id or e.id
                on_map |= {e.id, sid}
                own = sid in c.shift_mapping
                item = {
                    "id": e.id, "sid": sid, "kind": e.kind, "name": e.name, "led": e.led,
                    "isShift": e.id == c.shift_id, "code": element_name(e.id),
                    "normal": self._describe(e.id, c.mapping.get(e.id)),
                    # w warstwie SHIFT element bez własnego przypisania działa jak bez SHIFT
                    "shift": self._describe(sid, c.shift_mapping[sid] if own else c.mapping.get(sid)),
                    "shiftOwn": own,
                }
                elements.append(item)
            strips.append({"name": strip.name, "elements": elements})
        others = []
        for shift, layer in ((False, c.mapping), (True, c.shift_mapping)):
            for mid, target in sorted(layer.items()):
                if mid not in on_map:
                    others.append({"id": mid, "name": element_name(mid), "shift": shift} | self._describe(mid, target))
        self._strips, self._others = strips, others

    def tick(self) -> None:
        """Wołane z timera okna (~30 Hz): emituje sygnały tylko przy zmianach."""
        c = self.ctl
        flags = (c.port_name, c.out_port is not None, c.profile_name, c.learning, c.pickup, c.available, c.intro_enabled)
        if c.revision != self._rev or flags != self._flags:
            self._rev, self._flags = c.revision, flags
            self._rebuild()
            self.stateChanged.emit()
        last = ""
        if c.last_event is not None:
            mid, value = c.last_event
            target = c.target_for(mid)
            last = f"{element_name(mid)} = {round(value * 127)}" + (f" → {self._label(target)}" if target else "")
        live = (c.shift_held, last, sum(c.activity.values()))
        if live != self._live:
            self._live = live
            self._hw = c.hw_positions()
            self._activity = dict(c.activity)
            self._last = last
            self.liveChanged.emit()

    # --- stan ---
    @Property(bool, notify=stateChanged)
    def available(self) -> bool:
        return self.ctl.available

    @Property("QVariantList", notify=stateChanged)
    def ports(self) -> list[dict]:
        items = [{"label": "— bez kontrolera —", "value": ""}]
        names = list(self._ports)
        if self.ctl.port_name and self.ctl.port_name not in names:
            names.append(self.ctl.port_name)
        return items + [{"label": n, "value": n} for n in names]

    @Property(str, notify=stateChanged)
    def port(self) -> str:
        return self.ctl.port_name or ""

    @Property(bool, notify=stateChanged)
    def connected(self) -> bool:
        return self.ctl.port is not None

    @Property(bool, notify=stateChanged)
    def ledsOut(self) -> bool:
        return self.ctl.out_port is not None

    @Property(str, notify=stateChanged)
    def profileName(self) -> str:
        return self.ctl.profile_name or ""

    @Property("QVariantList", notify=stateChanged)
    def profiles(self) -> list[dict]:
        return [{"label": n, "value": n} for n in PROFILES]

    @Property(bool, notify=stateChanged)
    def learning(self) -> bool:
        return self.ctl.learning

    @Property(bool, notify=stateChanged)
    def pickup(self) -> bool:
        return self.ctl.pickup

    @Property(bool, notify=stateChanged)
    def intro(self) -> bool:
        return self.ctl.intro_enabled

    @Property("QVariantList", notify=stateChanged)
    def strips(self) -> list[dict]:
        return self._strips

    @Property("QVariantList", notify=stateChanged)
    def others(self) -> list[dict]:
        return self._others

    @Property(int, notify=stateChanged)
    def mappedCount(self) -> int:
        return len(self.ctl.mapping) + len(self.ctl.shift_mapping)

    @Property("QVariantMap", notify=liveChanged)
    def hw(self) -> dict[str, float]:
        return self._hw

    @Property("QVariantMap", notify=liveChanged)
    def activity(self) -> dict[str, int]:
        return self._activity

    @Property(bool, notify=liveChanged)
    def hwShift(self) -> bool:
        return self.ctl.shift_held

    @Property(str, notify=liveChanged)
    def lastEvent(self) -> str:
        return self._last

    @Property(str, notify=selectionChanged)
    def selected(self) -> str:
        return self._selected

    @Property(bool, notify=selectionChanged)
    def shiftView(self) -> bool:
        return self._shift_view

    # --- polecenia ---
    @Slot(str)
    def select(self, mid: str) -> None:
        if mid != self._selected:
            self._selected = mid
            self.selectionChanged.emit()

    @Slot(bool)
    def setShiftView(self, on: bool) -> None:
        if on != self._shift_view:
            self._shift_view = on
            self.selectionChanged.emit()

    @Slot()
    def refreshPorts(self) -> None:
        self._ports = self.ctl.inputs()
        self.stateChanged.emit()

    @Slot(str)
    def openPort(self, name: str) -> None:
        self.portRequested.emit(name)

    @Slot(str)
    def applyProfile(self, name: str) -> None:
        if name in PROFILES:
            self.ctl.apply_profile(name)
            self.tick()

    @Slot()
    def clearMapping(self) -> None:
        self.ctl.clear()
        self.tick()

    @Slot(bool)
    def setLearning(self, on: bool) -> None:
        self.ctl.learning = on
        self.ctl.armed_key = None
        self.tick()

    @Slot(bool)
    def setPickup(self, on: bool) -> None:
        self.ctl.pickup = on
        self.tick()

    @Slot(bool)
    def setIntro(self, on: bool) -> None:
        """Animacja powitalna diod po podłączeniu; włączenie od razu pokazuje ją na kontrolerze."""
        self.ctl.set_intro(on)
        self.tick()

    @Slot(str, str, bool)
    def assign(self, mid: str, target: str, shift: bool) -> None:
        try:
            self.ctl.assign(mid, target, shift)
        except KeyError:
            return
        self.tick()

    @Slot(str, bool)
    def unassign(self, mid: str, shift: bool) -> None:
        self.ctl.unassign(mid, shift)
        self.tick()

    @Slot(str, result="QVariantList")
    def search(self, text: str) -> list[dict[str, str]]:
        """Cele do przypisania: parametry i akcje (po kluczu, etykiecie i nazwie modułu)."""
        q = text.strip().lower()
        entries = [(k, s.label) for k, s in self.ctl.store.specs.items()] + list(ACTIONS.items())
        out = []
        for key, label in entries:
            module = self._module(key)
            if not q or q in key.lower() or q in label.lower() or q in module.lower():
                out.append({"value": key, "label": label, "module": module, "tone": self._tone(key)})
            if len(out) >= 40:
                break
        return out

    @Slot(str)
    def requestFile(self, what: str) -> None:
        self.fileRequested.emit(what)
