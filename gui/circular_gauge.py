"""
gui/circular_gauge.py
Un gauge circolare (anello di progresso) per mostrare la percentuale di
stampa. Qt non ha un widget di questo tipo pronto all'uso: lo disegniamo
manualmente con QPainter, sovrascrivendo paintEvent.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget


class CircularGauge(QWidget):
    def __init__(self, diameter: int = 96, thickness: int = 10, parent=None):
        super().__init__(parent)
        self._value = 0  # percentuale 0-100
        self._thickness = thickness
        self._track_color = QColor("#1a4a1a")
        self._progress_color = QColor("#19F01C")
        self._text_color = QColor("#e8e8e8")
        self._label = ""  # piccola etichetta sotto la percentuale (es. "12/12")
        self.setFixedSize(diameter, diameter)

    def set_value(self, value: int) -> None:
        self._value = max(0, min(100, value))
        self.update()

    def set_label(self, text: str) -> None:
        self._label = text
        self.update()

    def set_progress_color(self, color_hex: str) -> None:
        self._progress_color = QColor(color_hex)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (nome richiesto da Qt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        margin = self._thickness / 2 + 1
        rect = QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin)

        # Anello di sfondo (track)
        pen = QPen(self._track_color)
        pen.setWidth(self._thickness)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Arco di progresso: parte dalle "ore 12" e va in senso orario
        if self._value > 0:
            pen.setColor(self._progress_color)
            painter.setPen(pen)
            span = int(360 * 16 * (self._value / 100))
            painter.drawArc(rect, 90 * 16, -span)

        # Percentuale al centro
        painter.setPen(self._text_color)
        font = painter.font()
        font.setPointSize(max(9, self.width() // 6))
        font.setBold(True)
        painter.setFont(font)

        text_rect = QRectF(self.rect())
        if self._label:
            text_rect.adjust(0, -self.height() * 0.08, 0, -self.height() * 0.08)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{self._value}%")

        if self._label:
            small_font = painter.font()
            small_font.setPointSize(max(7, self.width() // 11))
            small_font.setBold(False)
            painter.setFont(small_font)
            label_rect = QRectF(self.rect())
            label_rect.adjust(0, self.height() * 0.28, 0, self.height() * 0.28)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self._label)
