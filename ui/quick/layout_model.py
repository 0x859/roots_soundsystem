"""Model profilu układu dla QML: karty, pady, skróty, motyw; edycja z cofaniem i autozapisem."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QFontDatabase, QKeySequence

from engine.params import ParamSpec

from .. import layout_profile as lp

UNDO_LIMIT = 100
CARD_PROPS = ("title", "color", "span", "rows", "height", "cols", "collapsed", "visible", "more", "toggle", "info")
SAVE_DELAY_MS = 400

LABEL_FONTS = ("Barlow Condensed", "Bahnschrift SemiCondensed", "Bahnschrift", "Arial Narrow", "Segoe UI")
VALUE_FONTS = ("IBM Plex Mono", "Cascadia Mono", "Consolas", "Courier New")
DENSITY_SPACING = {"compact": 8, "normal": 12, "touch": 16}


def load_bundled_fonts() -> None:
    """Czcionki z `assets/fonts` (np. Barlow Condensed, IBM Plex Mono – licencja OFL), jeśli są."""
    root = Path(__file__).resolve().parents[2] / "assets" / "fonts"
    if root.is_dir():
        for f in sorted(root.glob("*.[ot]tf")):
            QFontDatabase.addApplicationFont(str(f))


def resolve_font(wanted: str, fallbacks: tuple[str, ...]) -> str:
    families = set(QFontDatabase.families())
    for name in (wanted, *fallbacks):
        if name in families:
            return name
    return fallbacks[-1]


def key_code(name: str) -> int:
    seq = QKeySequence(name)
    if seq.isEmpty():
        return 0
    return seq[0].key().value


class QmlTheme(QObject):
    """Motyw z profilu: kolory, czcionki (z zamiennikami), skala, gęstość, styl gałek, pady."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._t: dict[str, Any] = copy.deepcopy(lp.DEFAULT_THEME)
        self._fit = 1.0
        self._label_font = resolve_font(self._t["fonts"]["label"], LABEL_FONTS)
        self._value_font = resolve_font(self._t["fonts"]["value"], VALUE_FONTS)

    # rozmiar widoku, przy którym skala automatyczna = 1.0, i granice mnożnika
    FIT_BASE = (1600.0, 1000.0)
    FIT_RANGE = (0.9, 1.3)

    def set_viewport(self, width: float, height: float) -> None:
        """Mnożnik skali z rozmiaru widoku (krok 0.05, żeby zmiana okna nie przeliczała wszystkiego co piksel)."""
        lo, hi = self.FIT_RANGE
        fit = min(width / self.FIT_BASE[0], height / self.FIT_BASE[1])
        fit = round(min(hi, max(lo, fit)) * 20) / 20
        if fit != self._fit:
            self._fit = fit
            if self._t.get("autoScale", True):
                self.changed.emit()

    def _scale(self) -> float:
        return float(self._t["scale"]) * (self._fit if self._t.get("autoScale", True) else 1.0)

    def apply(self, theme: dict[str, Any]) -> None:
        if theme == self._t:
            return
        self._t = copy.deepcopy(theme)
        self._label_font = resolve_font(theme["fonts"]["label"], LABEL_FONTS)
        self._value_font = resolve_font(theme["fonts"]["value"], VALUE_FONTS)
        self.changed.emit()

    def _col(self, name: str) -> str:
        return self._t["colors"][name]

    bg = Property(str, lambda s: s._col("bg"), notify=changed)
    card = Property(str, lambda s: s._col("card"), notify=changed)
    raised = Property(str, lambda s: s._col("raised"), notify=changed)
    line = Property(str, lambda s: s._col("line"), notify=changed)
    text = Property(str, lambda s: s._col("text"), notify=changed)
    muted = Property(str, lambda s: s._col("muted"), notify=changed)
    accent = Property(str, lambda s: s._col("accent"), notify=changed)
    fx = Property(str, lambda s: s._col("fx"), notify=changed)
    kill = Property(str, lambda s: s._col("kill"), notify=changed)
    labelFont = Property(str, lambda s: s._label_font, notify=changed)
    valueFont = Property(str, lambda s: s._value_font, notify=changed)
    scale = Property(float, lambda s: s._scale(), notify=changed)
    fit = Property(float, lambda s: s._fit, notify=changed)
    autoScale = Property(bool, lambda s: bool(s._t.get("autoScale", True)), notify=changed)
    autoExpand = Property(bool, lambda s: bool(s._t.get("autoExpand", True)), notify=changed)
    density = Property(str, lambda s: s._t["density"], notify=changed)
    spacing = Property(int, lambda s: int(DENSITY_SPACING[s._t["density"]] * s._scale()), notify=changed)
    knobStyle = Property(str, lambda s: s._t["knobStyle"], notify=changed)
    padPosition = Property(str, lambda s: s._t["pads"]["position"], notify=changed)
    padHeight = Property(int, lambda s: int(s._t["pads"]["height"] * s._scale()), notify=changed)
    minCardWidth = Property(int, lambda s: int(s._t["minCardWidth"] * s._scale()), notify=changed)
    tiles = Property(bool, lambda s: bool(s._t["tiles"]), notify=changed)
    inspectorWidth = Property(int, lambda s: int(s._t["inspectorWidth"]), notify=changed)

    @Slot(str, str, result=str)
    def color(self, name: str, fallback: str = "accent") -> str:
        """Kolor kontrolki/karty: nazwa z palety, #RRGGBB albo „auto” (= `fallback`)."""
        if name and name.startswith("#"):
            return name
        colors = self._t["colors"]
        if name in colors:
            return colors[name]
        return colors.get(fallback, colors["accent"])

    @Slot(str, result=str)
    def raw(self, path: str) -> str:
        """Surowa wartość motywu (np. „colors.accent”, „fonts.label”) dla inspektora."""
        node: Any = self._t
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return ""
            node = node[part]
        return str(node)


class LayoutModel(QObject):
    cardsChanged = Signal()
    padsChanged = Signal()
    shortcutsChanged = Signal()
    historyChanged = Signal()
    profilesChanged = Signal()
    message = Signal(str)

    def __init__(self, specs: dict[str, ParamSpec], name: str = lp.DEFAULT_NAME, parent: QObject | None = None,
                 autosave: bool = True):
        super().__init__(parent)
        self.specs = specs
        self.theme = QmlTheme(self)
        self._undo: list[dict] = []
        self._redo: list[dict] = []
        self._autosave = autosave
        self._save_timer = QTimer(self, singleShot=True, interval=SAVE_DELAY_MS, timeout=self.save)
        self._profiles = lp.list_profiles()
        self._p: dict[str, Any] = lp.load_profile(name, specs)
        self.theme.apply(self._p["theme"])

    # --- dostęp ---
    @property
    def profile(self) -> dict[str, Any]:
        return self._p

    @Property("QVariantList", notify=cardsChanged)
    def cards(self) -> list[dict]:
        return self._p["cards"]

    @Property("QVariantList", notify=padsChanged)
    def pads(self) -> list[dict]:
        return self._p["pads"]

    @Property("QVariantMap", notify=shortcutsChanged)
    def shortcuts(self) -> dict[str, str]:
        return self._p["shortcuts"]

    @Property(str, notify=profilesChanged)
    def profileName(self) -> str:
        return self._p["name"]

    @Property("QVariantList", notify=profilesChanged)
    def profiles(self) -> list[str]:
        return self._profiles

    @Property(bool, notify=historyChanged)
    def canUndo(self) -> bool:
        return bool(self._undo)

    @Property(bool, notify=historyChanged)
    def canRedo(self) -> bool:
        return bool(self._redo)

    @Property("QVariantList", constant=True)
    def controlTypes(self) -> list[str]:
        return list(lp.CONTROL_TYPES)

    def shortcut_map(self) -> dict[int, str]:
        """Kod klawisza Qt → cel (parametr lub akcja)."""
        out: dict[int, str] = {}
        for name, target in self._p["shortcuts"].items():
            code = key_code(name)
            if code:
                out[code] = target
        return out

    @Slot(str, result=str)
    def shortcutFor(self, target: str) -> str:
        return lp.shortcut_for(self._p, target)

    # --- zmiany ---
    def _commit(self, new: dict[str, Any], record: bool = True) -> None:
        new = lp.normalize(new, self.specs)
        new["name"] = self._p["name"]
        if new == self._p:
            return
        if record:
            self._undo.append(copy.deepcopy(self._p))
            del self._undo[:-UNDO_LIMIT]
            self._redo.clear()
        old = self._p
        self._p = new
        self._emit_diff(old, new)
        self.historyChanged.emit()
        if self._autosave:
            self._save_timer.start()

    def _emit_diff(self, old: dict[str, Any], new: dict[str, Any]) -> None:
        if old["cards"] != new["cards"]:
            self.cardsChanged.emit()
        if old["pads"] != new["pads"]:
            self.padsChanged.emit()
        if old["shortcuts"] != new["shortcuts"]:
            self.shortcutsChanged.emit()
            self.padsChanged.emit()
        if old["theme"] != new["theme"]:
            self.theme.apply(new["theme"])

    def _edit(self) -> dict[str, Any]:
        return copy.deepcopy(self._p)

    def _card(self, p: dict, ci: int) -> dict | None:
        cards = p["cards"]
        return cards[ci] if 0 <= ci < len(cards) else None

    # karty
    @Slot(int, int)
    def moveCard(self, src: int, dst: int) -> None:
        p = self._edit()
        cards = p["cards"]
        if not (0 <= src < len(cards)) or src == dst:
            return
        dst = max(0, min(len(cards) - 1, dst))
        cards.insert(dst, cards.pop(src))
        self._commit(p)

    @Slot(int, str, "QVariant")
    def setCardProp(self, ci: int, name: str, value: Any) -> None:
        p = self._edit()
        card = self._card(p, ci)
        if card is None or name not in CARD_PROPS:
            return
        card[name] = value
        self._commit(p)

    @Slot(int, int, int)
    def setCardSize(self, ci: int, span: int, rows: int) -> None:
        """Szerokość (kolumny siatki) i rzędy siatki karty jako jedna zmiana."""
        self.setCardBox(ci, span, rows, -1)

    @Slot(int, int, int, int)
    def setCardBox(self, ci: int, span: int, rows: int, height: int) -> None:
        """Szerokość, rzędy i wysokość w px przy skali 100% (0 = automatyczna, -1 = bez zmiany) – jedna zmiana."""
        p = self._edit()
        card = self._card(p, ci)
        if card is None:
            return
        card["span"], card["rows"] = span, rows
        if height >= 0:
            card["height"] = height
        self._commit(p)

    @Slot(int, str, "QVariant")
    def setCardState(self, ci: int, name: str, value: Any) -> None:
        """Zmiana stanu karty bez wpisu do historii cofania (np. zwinięcie w trybie LIVE)."""
        p = self._edit()
        card = self._card(p, ci)
        if card is None or name not in CARD_PROPS:
            return
        card[name] = value
        self._commit(p, record=False)

    @Slot(str, str, result=int)
    def addCard(self, title: str = "", visible: str = "live") -> int:
        p = self._edit()
        p["cards"].append({"title": title or "MOJA KARTA", "visible": visible, "controls": []})
        self._commit(p)
        return len(self._p["cards"]) - 1

    @Slot(int)
    def removeCard(self, ci: int) -> None:
        p = self._edit()
        if self._card(p, ci) is None:
            return
        p["cards"].pop(ci)
        self._commit(p)

    @Slot(int, result=int)
    def duplicateCard(self, ci: int) -> int:
        p = self._edit()
        card = self._card(p, ci)
        if card is None:
            return -1
        dup = copy.deepcopy(card)
        dup.pop("id", None)
        p["cards"].insert(ci + 1, dup)
        self._commit(p)
        return ci + 1

    # kontrolki
    @Slot(int, str, result=int)
    def addControl(self, ci: int, target: str) -> int:
        p = self._edit()
        card = self._card(p, ci)
        if card is None or not lp.is_target(target, self.specs):
            return -1
        types = lp.allowed_types(target, self.specs)
        card["controls"].append({"param": target, "type": types[0], "size": "M"})
        self._commit(p)
        return len(self._p["cards"][ci]["controls"]) - 1

    @Slot(int, int)
    def removeControl(self, ci: int, k: int) -> None:
        p = self._edit()
        card = self._card(p, ci)
        if card is None or not (0 <= k < len(card["controls"])):
            return
        card["controls"].pop(k)
        self._commit(p)

    @Slot(int, int, int, int)
    def moveControl(self, ci: int, k: int, to_ci: int, to_k: int) -> None:
        p = self._edit()
        src, dst = self._card(p, ci), self._card(p, to_ci)
        if src is None or dst is None or not (0 <= k < len(src["controls"])):
            return
        ctl = src["controls"].pop(k)
        to_k = max(0, min(len(dst["controls"]), to_k))
        dst["controls"].insert(to_k, ctl)
        self._commit(p)

    @Slot(int, int, str, "QVariant")
    def setControlProp(self, ci: int, k: int, name: str, value: Any) -> None:
        p = self._edit()
        card = self._card(p, ci)
        if card is None or not (0 <= k < len(card["controls"])):
            return
        if name not in ("param", "type", "size", "label", "color", "kill"):
            return
        ctl = card["controls"][k]
        if value in (None, ""):
            ctl.pop(name, None)
        else:
            ctl[name] = value
        if name == "param":
            types = lp.allowed_types(value, self.specs) if lp.is_target(value, self.specs) else ()
            if types and ctl.get("type") not in types:
                ctl["type"] = types[0]
        self._commit(p)

    # pady i skróty
    @Slot(str)
    def addPad(self, target: str) -> None:
        if target in lp.VIEWS or not lp.is_target(target, self.specs):
            return
        p = self._edit()
        p["pads"].append({"param": target, "label": lp.target_label(target, self.specs).upper()})
        self._commit(p)

    @Slot(int)
    def removePad(self, i: int) -> None:
        p = self._edit()
        if 0 <= i < len(p["pads"]):
            p["pads"].pop(i)
            self._commit(p)

    @Slot(int, int)
    def movePad(self, src: int, dst: int) -> None:
        p = self._edit()
        pads = p["pads"]
        if 0 <= src < len(pads) and src != dst:
            pads.insert(max(0, min(len(pads) - 1, dst)), pads.pop(src))
            self._commit(p)

    @Slot(int, str)
    def setPadLabel(self, i: int, label: str) -> None:
        p = self._edit()
        if 0 <= i < len(p["pads"]):
            p["pads"][i]["label"] = label
            self._commit(p)

    @Slot(str, str, result=bool)
    def setShortcut(self, target: str, key: str) -> bool:
        """Przypisuje klawisz celowi (pusty = usuń). Klawisz zajęty przez inny cel zostaje przejęty."""
        p = self._edit()
        sc = {k: t for k, t in p["shortcuts"].items() if t != target}
        nk = lp.normalize_shortcut(key)
        if key.strip() and not nk:
            self.message.emit(f"Nieobsługiwany klawisz: {key}")
            return False
        if nk:
            sc[nk] = target
        p["shortcuts"] = sc
        self._commit(p)
        return True

    # motyw
    def _theme_edit(self, path: str, value: Any) -> dict[str, Any]:
        p = self._edit()
        node = p["theme"]
        parts = path.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        return p

    @Slot(str, "QVariant")
    def setTheme(self, path: str, value: Any) -> None:
        self._commit(self._theme_edit(path, value))

    @Slot(str, "QVariant")
    def setThemeQuiet(self, path: str, value: Any) -> None:
        """Jak `setTheme`, ale bez historii (np. szerokość inspektora przy przeciąganiu)."""
        self._commit(self._theme_edit(path, value), record=False)

    @Slot()
    def resetTheme(self) -> None:
        p = self._edit()
        p["theme"] = copy.deepcopy(lp.DEFAULT_THEME)
        self._commit(p)

    # historia
    @Slot()
    def undo(self) -> None:
        if not self._undo:
            return
        self._redo.append(copy.deepcopy(self._p))
        old, self._p = self._p, self._undo.pop()
        self._emit_diff(old, self._p)
        self.historyChanged.emit()
        if self._autosave:
            self._save_timer.start()

    @Slot()
    def redo(self) -> None:
        if not self._redo:
            return
        self._undo.append(copy.deepcopy(self._p))
        old, self._p = self._p, self._redo.pop()
        self._emit_diff(old, self._p)
        self.historyChanged.emit()
        if self._autosave:
            self._save_timer.start()

    # profile
    @Slot()
    def save(self) -> None:
        self._save_timer.stop()
        lp.save_profile(self._p)
        if self._p["name"] not in self._profiles:
            self._profiles = lp.list_profiles()
            self.profilesChanged.emit()

    def flush(self) -> None:
        if self._save_timer.isActive():
            self.save()

    def _replace(self, new: dict[str, Any]) -> None:
        old = self._p
        self._p = new
        self._undo.clear()
        self._redo.clear()
        self._emit_diff(old, new)
        self.historyChanged.emit()
        self.profilesChanged.emit()

    @Slot(str)
    def switchProfile(self, name: str) -> None:
        if not name or name == self._p["name"]:
            return
        self.flush()
        self._replace(lp.load_profile(name, self.specs))

    @Slot(str, result=bool)
    def saveAs(self, name: str) -> bool:
        name = name.strip()
        if not name:
            return False
        self.flush()
        new = copy.deepcopy(self._p)
        new["name"] = name
        lp.save_profile(new)
        self._profiles = lp.list_profiles()
        self._replace(new)
        return True

    @Slot()
    def deleteProfile(self) -> None:
        name = self._p["name"]
        self._save_timer.stop()
        lp.delete_profile(name)
        self._profiles = lp.list_profiles()
        self._replace(lp.load_profile(lp.DEFAULT_NAME, self.specs))

    @Slot()
    def resetProfile(self) -> None:
        """Przywraca układ domyślny w bieżącym profilu (z możliwością cofnięcia)."""
        self._commit(lp.default_profile())

    @Slot(QUrl, result=bool)
    def exportTo(self, url: QUrl) -> bool:
        try:
            lp.export_profile(self._p, url.toLocalFile())
        except OSError as exc:
            self.message.emit(f"Eksport nieudany: {exc}")
            return False
        self.message.emit("Wyeksportowano układ")
        return True

    @Slot(QUrl, result=bool)
    def importFrom(self, url: QUrl) -> bool:
        try:
            new = lp.import_profile(url.toLocalFile(), self.specs)
        except (OSError, ValueError) as exc:
            self.message.emit(f"Import nieudany: {exc}")
            return False
        self._commit(new)
        self.message.emit("Zaimportowano układ")
        return True
