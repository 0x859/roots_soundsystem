"""Ciemny motyw Fusion z akcentami w barwach roots (czerwień, złoto, zieleń)."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPalette, QPen, QPixmap

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


def app_icon() -> QIcon:
    ico = bundled_icon_path()
    if ico is not None:
        return QIcon(str(ico))
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    rect = QRectF(4, 4, 56, 56)
    for i, col in enumerate((RED, GOLD, GREEN)):
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(col))
        p.drawPie(rect, (90 + i * 120) * 16, 120 * 16)
    p.setBrush(QBrush(QColor("#111")))
    p.drawEllipse(QRectF(20, 20, 24, 24))
    p.setPen(QPen(GOLD, 3))
    p.drawEllipse(QRectF(27, 27, 10, 10))
    p.end()
    return QIcon(pm)
