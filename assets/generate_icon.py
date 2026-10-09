"""Generuje assets/icon.ico (16–256 px, także 20/24/40 dla skalowania 125–150%) ze znakiem z `ui.theme`."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from ui.theme import ICON_SIZES, paint_icon


def paint_mark(image: QImage) -> None:
    image.fill(Qt.transparent)
    p = QPainter(image)
    paint_icon(p, image.width())
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
    for size in ICON_SIZES:
        im = QImage(size, size, QImage.Format_ARGB32)
        paint_mark(im)
        images.append(im)
    write_ico(dest, images)
    print(f"Zapisano {dest} ({dest.stat().st_size} B)")
    del app  # QApplication musi istnieć do końca rysowania


if __name__ == "__main__":
    main()
