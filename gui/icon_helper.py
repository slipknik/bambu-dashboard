"""
icon_helper.py
Crea un QIcon con tutte le dimensioni disponibili dal file app_icon.py.
Aggiungere ogni dimensione esplicitamente permette a Qt di scegliere
quella giusta per ogni contesto (tray=16, taskbar=32, alt-tab=48, ecc.)
invece di scalare brutalmente da 256.
"""
from __future__ import annotations
import base64
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import QByteArray


def make_app_icon() -> QIcon:
    """Restituisce un QIcon con tutte le dimensioni disponibili."""
    try:
        from app_icon import ICON_SIZES
        icon = QIcon()
        for size in sorted(ICON_SIZES.keys()):
            png_bytes = QByteArray(base64.b64decode(ICON_SIZES[size]))
            pixmap = QPixmap()
            if pixmap.loadFromData(png_bytes, "PNG") and not pixmap.isNull():
                icon.addPixmap(pixmap)
        if not icon.isNull():
            return icon
    except Exception:
        pass
    # Fallback: icona di sistema
    from PySide6.QtWidgets import QApplication
    return QApplication.style().standardIcon(
        QApplication.style().StandardPixmap.SP_ComputerIcon
    )
