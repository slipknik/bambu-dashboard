from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import (
    QBrush, QColor, QFont, QFontMetrics,
    QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

CARD_WIDTH  = 82
CARD_HEIGHT = 66
LABEL_W     = 82


class AmsTraySlot(QWidget):
    """Slot filamento: etichetta in alto, sotto il rettangolo del materiale (bianco) e sotto il rettangolo del colore."""

    def __init__(self, slot_label: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self._slot_label = slot_label
        self._material   = ""
        self._color      = QColor("#444444")
        self._is_empty   = True
        self._is_active  = False

    def set_filled(self, material: str, color_hex: str) -> None:
        self._material = material or "?"
        self._color    = QColor(color_hex) if color_hex else QColor("#999999")
        self._is_empty = False
        self.update()

    def set_empty(self) -> None:
        self._material = ""
        self._color    = QColor("#3a3a3a")
        self._is_empty = True
        self.update()

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self.update()

    # ── disegno ─────────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 1. Etichetta slot (A1, B3 …) in alto al centro
        lf = QFont()
        lf.setPixelSize(13)
        lf.setBold(True)
        p.setFont(lf)
        p.setPen(QColor("#19F01C") if self._is_active else QColor("#999999"))
        p.drawText(QRect(0, 1, w, 17), Qt.AlignmentFlag.AlignCenter, self._slot_label)

        # Dimensioni del riquadro unificato (materiale + colore)
        box_w = w - 8
        unified_rect = QRect(4, 19, box_w, 40)
        cr_material = QRect(4, 19, box_w, 20)
        cr_color = QRect(4, 39, box_w, 20)

        # Usiamo QPainterPath per creare il tracciato arrotondato per il clip
        clip_path = QPainterPath()
        clip_path.addRoundedRect(unified_rect, 5, 5)

        p.save()
        p.setClipPath(clip_path)

        # Disegno la metà superiore (materiale: bianca o grigia se vuoto)
        p.setPen(Qt.PenStyle.NoPen)
        if self._is_empty:
            p.setBrush(QBrush(QColor("#3a3a3a")))
        else:
            p.setBrush(QBrush(QColor("white")))
        p.drawRect(cr_material)

        # Disegno la metà inferiore (colore)
        p.setBrush(QBrush(self._color))
        p.drawRect(cr_color)

        p.restore()

        # Bordo verde quando attivo (circonda la tabellina di materiale + colore)
        if self._is_active:
            bp = QPen(QColor("#19F01C"), 2)
            p.setPen(bp)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRect(3, 18, w - 6, 42), 5, 5)

        # Contenuto dei riquadri
        if self._is_empty:
            xf = QFont()
            xf.setPixelSize(13)
            xf.setBold(True)
            p.setFont(xf)
            p.setPen(QColor("#e53935"))
            p.drawText(cr_color, Qt.AlignmentFlag.AlignCenter, "✕")
        else:
            if self._material:
                mf = QFont()
                mf.setPixelSize(11)
                mf.setBold(True)
                p.setFont(mf)
                p.setPen(QColor("black"))
                p.drawText(cr_material, Qt.AlignmentFlag.AlignCenter, self._material)

        p.end()
# ─────────────────────────────────────────────────────────────────────────────
class AmsUnitWidget(QWidget):
    """Header cliccabile + riga di slot. Ispirato a BambuStudio."""

    def __init__(self, unit_label: str, humidity: Optional[int] = None,
                 temperature: Optional[float] = None, extra_label: Optional[str] = None,
                 parent=None):
        super().__init__(parent)
        self._unit_label = unit_label

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 4, 0, 8)
        vbox.setSpacing(6)

        # Header ─────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        header.setSpacing(16)

        self._btn = QPushButton("▼  " + unit_label)
        self._btn.setCheckable(True)
        self._btn.setChecked(True)
        self._btn.setFlat(True)
        self._btn.setFixedWidth(130)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(
            "QPushButton { color: #e0e0e0; font-size: 15px; font-weight: bold;"
            " text-align: left; padding: 1px 6px; border: none; background: transparent; }"
            "QPushButton:hover { color: #fff; }"
        )
        self._btn.clicked.connect(self._toggle)
        header.addWidget(self._btn)

        if humidity is not None:
            hum = QLabel(f"💧 {humidity}%")
            hum.setStyleSheet("color: #5bc4f5; font-size: 18px;")
            header.addWidget(hum)

        if temperature is not None:
            tmp = QLabel(f"🌡 {temperature:.0f}°C")
            tmp.setStyleSheet("color: #ffb74d; font-size: 18px;")
            header.addWidget(tmp)

        if extra_label:
            ext = QLabel(extra_label)
            ext.setStyleSheet("color: #ff7043; font-size: 18px;")
            header.addWidget(ext)

        header.addStretch()
        vbox.addLayout(header)

        # Riga slot ───────────────────────────────────────────────────────────
        self._slots_widget = QWidget()
        self._slots_widget.setStyleSheet("background: transparent;")
        row = QHBoxLayout(self._slots_widget)
        row.setContentsMargins(8, 0, 0, 0)
        row.setSpacing(6)
        self._slots_row = row
        vbox.addWidget(self._slots_widget)

        # Label stato AMS (Lettura RFID, Cambio filamento, ecc.) — sotto gli slot
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            "color: #64b5f6; font-size: 13px; font-style: italic; padding-left: 12px;"
        )
        self._status_label.setVisible(False)
        vbox.addWidget(self._status_label)

    def set_ams_status(self, text: str) -> None:
        """Mostra o nasconde la label di stato AMS sotto gli slot di questa unità."""
        if text:
            self._status_label.setText(f"⟳ {text}")
            self._status_label.setVisible(True)
        else:
            self._status_label.setVisible(False)

    def _toggle(self, checked: bool) -> None:
        self._slots_widget.setVisible(checked)
        self._btn.setText(("▼  " if checked else "▶  ") + self._unit_label)

    def add_slot(self, slot: AmsTraySlot) -> None:
        self._slots_row.addWidget(slot)

    def finalize(self) -> None:
        self._slots_row.addStretch()
