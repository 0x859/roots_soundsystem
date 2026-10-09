"""Generuje assets/icon.ico (16/32/48/256) z tym samym znakiem co UI."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

from ui.theme import GOLD, GREEN, RED


def paint_mark(image: QImage) -> None:
    s = image.width()
    image.fill(Qt.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.Antialiasing)
    m = s * 0.06
    rect = QRectF(m, m, s - 2 * m, s - 2 * m)
    for i, col in enumerate((RED, GOLD, GREEN)):
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(col))
        p.drawPie(rect, (90 + i * 120) * 16, 120 * 16)
    inner = s * 0.31
    p.setBrush(QBrush(QColor("#111")))
    p.drawEllipse(QRectF((s - inner) / 2, (s - inner) / 2, inner, inner))
    ring = s * 0.16
    p.setPen(QPen(GOLD, max(1.5, s * 0.045)))
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(QRectF((s - ring) / 2, (s - ring) / 2, ring, ring))
    p.end()


def png_bytes(image: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    return bytes(ba)


def write_ico(path: Path, images: list[QImage]) -> None:
    pngs = [png_bytes(im) for im in images]
    offset = 6 + 16 * len(pngs)
    out = bytearray()
    out += struct.pack("<HHH", 0, 1, len(pngs))
    for im, data in zip(images, pngs, strict=True):
        w = 0 if im.width() >= 256 else im.width()
        h = 0 if im.height() >= 256 else im.height()
        out += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    for data in pngs:
        out += data
    path.write_bytes(out)


def main() -> None:
    app = QApplication.instance() or QApplication([])
    dest = Path(__file__).resolve().parent / "icon.ico"
    images = []
    for size in (16, 32, 48, 256):
        im = QImage(size, size, QImage.Format_ARGB32)
        paint_mark(im)
        images.append(im)
    write_ico(dest, images)
    print(f"Zapisano {dest} ({dest.stat().st_size} B)")
    del app  # QApplication musi istnieć do końca rysowania


if __name__ == "__main__":
    main()
