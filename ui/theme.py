"""Ciemny motyw Fusion z akcentami w barwach roots (czerwień, złoto, zieleń)."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
    QRadialGradient,
)

RED = QColor("#d62828")
GOLD = QColor("#f7b801")
GREEN = QColor("#2a9d38")
BG = QColor("#16181c")
PANEL = QColor("#1f2227")
TEXT = QColor("#e6e6e6")
MUTED = QColor("#8a8f98")
WAY_COLORS = {"sub": "#d62828", "bass": "#f77f00", "mid": "#f7b801", "top": "#2a9d38"}

STYLESHEET = """
QGroupBox {{ border: 1px solid #33373e; border-radius: 6px; margin-top: 10px; padding: 4px; background: #1f2227; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #f7b801; font-weight: bold; }}
QPushButton {{ background: #2a2e35; border: 1px solid #3a3f47; border-radius: 4px; padding: 4px 8px; }}
QPushButton:hover {{ background: #333842; }}
QPushButton:checked {{ background: #2a9d38; color: #101010; font-weight: bold; }}
QPushButton[momentary="true"] {{ background: #3a1e1e; border-color: #6b2b2b; font-weight: bold; min-height: 26px; }}
QPushButton[momentary="true"][active="true"] {{ background: #d62828; color: white; }}
QPushButton[kill="true"][active="true"] {{ background: #d62828; color: white; }}
QComboBox {{ background: #2a2e35; border: 1px solid #3a3f47; border-radius: 4px; padding: 2px 6px; }}
QLabel[role="value"] {{ color: #f7b801; font-size: {value_pt}px; }}
QLabel[role="caption"] {{ color: #b8bcc4; font-size: {caption_pt}px; }}
QStatusBar QLabel {{ padding: 0 8px; }}
QScrollArea {{ border: none; }}
QSlider::groove:vertical {{ background: #2a2e35; width: 6px; border-radius: 3px; }}
QSlider::handle:vertical {{ background: #f7b801; height: 14px; margin: 0 -6px; border-radius: 3px; }}
QSlider::sub-page:vertical {{ background: #2a2e35; }}
QSlider::add-page:vertical {{ background: #5a4a10; }}
"""


def stylesheet_for(scale: float = 1.0) -> str:
    return STYLESHEET.format(
        caption_pt=max(8, int(round(10 * scale))),
        value_pt=max(8, int(round(10 * scale))),
    )


def apply_scaled_stylesheet(app, scale: float = 1.0) -> None:
    app.setStyleSheet(stylesheet_for(scale))


def apply_theme(app) -> None:
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window, BG)
    pal.setColor(QPalette.WindowText, TEXT)
    pal.setColor(QPalette.Base, QColor("#121418"))
    pal.setColor(QPalette.AlternateBase, PANEL)
    pal.setColor(QPalette.ToolTipBase, PANEL)
    pal.setColor(QPalette.ToolTipText, TEXT)
    pal.setColor(QPalette.Text, TEXT)
    pal.setColor(QPalette.Button, QColor("#2a2e35"))
    pal.setColor(QPalette.ButtonText, TEXT)
    pal.setColor(QPalette.BrightText, RED)
    pal.setColor(QPalette.Highlight, GOLD)
    pal.setColor(QPalette.HighlightedText, QColor("#101010"))
    pal.setColor(QPalette.Disabled, QPalette.Text, MUTED)
    pal.setColor(QPalette.Disabled, QPalette.ButtonText, MUTED)
    pal.setColor(QPalette.Disabled, QPalette.WindowText, MUTED)
    app.setPalette(pal)
    apply_scaled_stylesheet(app, 1.0)


def bundled_icon_path() -> Path | None:
    roots = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        roots.append(Path(sys._MEIPASS) / "assets" / "icon.ico")
        roots.append(Path(sys.executable).resolve().parent / "assets" / "icon.ico")
    roots.append(Path(__file__).resolve().parents[1] / "assets" / "icon.ico")
    for path in roots:
        if path.is_file():
            return path
    return None


ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
ICON_BG = QColor("#1A1916")
ICON_EDGE = QColor("#3A362E")
ICON_GOLD = QColor("#E3A52B")
ICON_STRIPE = (QColor("#B8362A"), QColor("#E3A52B"), QColor("#3F8F4A"))


def paint_icon(p: QPainter, s: int) -> None:
    """Znak aplikacji: głośnik (złote zawieszenie, ciemny stożek, złota nakładka) na ciemnym kafelku.

    Od 32 px dochodzi pasek czerwień–złoto–zieleń; mniejsze rozmiary mają grubsze, prostsze kreski,
    żeby znak nie zlewał się w plamę na pasku zadań.
    """
    p.setRenderHint(QPainter.Antialiasing)
    small = s < 32
    m = s * 0.03
    tile = QRectF(m, m, s - 2 * m, s - 2 * m)
    radius = s * 0.22
    p.setPen(QPen(ICON_EDGE, max(1.0, s * 0.02)) if not small else Qt.NoPen)
    p.setBrush(QBrush(ICON_BG))
    p.drawRoundedRect(tile, radius, radius)
    if not small:
        # pasek roots przycięty do dolnej krawędzi kafelka
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(tile, radius, radius)
        p.setClipPath(clip)
        h = s * 0.1
        w = tile.width() / 3
        for i, col in enumerate(ICON_STRIPE):
            p.fillRect(QRectF(tile.left() + i * w, tile.bottom() - h, w + 0.5, h), col)
        p.restore()
    cx = s / 2
    cy = s * (0.5 if small else 0.45)
    r = s * (0.36 if small else 0.31)
    ring = max(1.6, s * (0.11 if small else 0.065))
    cone = QRadialGradient(cx, cy, r)
    cone.setColorAt(0.0, QColor("#3A362E"))
    cone.setColorAt(1.0, QColor("#0B0A08"))
    p.setPen(QPen(ICON_GOLD, ring))
    p.setBrush(QBrush(cone))
    p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
    if s >= 48:  # przetłoczenie stożka
        rc = r * 0.62
        p.setPen(QPen(ICON_EDGE, s * 0.015))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QRectF(cx - rc, cy - rc, 2 * rc, 2 * rc))
    cap = r * (0.38 if small else 0.32)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(ICON_GOLD))
    p.drawEllipse(QRectF(cx - cap, cy - cap, 2 * cap, 2 * cap))


def app_icon() -> QIcon:
    ico = bundled_icon_path()
    if ico is not None:
        return QIcon(str(ico))
    icon = QIcon()
    for s in ICON_SIZES:
        pm = QPixmap(s, s)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        paint_icon(p, s)
        p.end()
        icon.addPixmap(pm)
    return icon
