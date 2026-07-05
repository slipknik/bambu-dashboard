"""
gui/printer_card.py
Dashboard a tutta pagina per UNA stampante. Viene usata come contenuto di
una singola tab (vedi gui/main_window.py): con una stampante sola occupa
tutta la finestra, con più stampanti ognuna ha la propria tab, così non
serve comprimere tutto in piccole card affiancate e si possono usare
caratteri grandi e leggibili anche su un monitor piccolo.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QSizePolicy, QMessageBox, QScrollArea,
)

from models import PrinterStatus
from gui.circular_gauge import CircularGauge
from gui.ams_tray import AmsTraySlot

PLACEHOLDER_TEXT = "Nessuna\nanteprima"
PREVIEW_SIZE = 200
GAUGE_SIZE = 190


class PrinterCard(QWidget):
    def __init__(self, dev_id: str, name: str, widgets_enabled: dict, parent=None):
        super().__init__(parent)
        self.dev_id = dev_id
        self.name = name
        self.widgets_enabled = widgets_enabled
        self.on_skip_object = None
        self.on_pause = None
        self.on_resume = None
        self.on_stop = None

        self.setStyleSheet(
            "QLabel { font-size: 16px; }"
            "QPushButton { padding: 12px 20px; font-size: 16px; }"
            "QSpinBox { padding: 6px; font-size: 16px; min-width: 70px; }"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 20, 28, 20)
        outer.setSpacing(14)

        # --- Header -----------------------------------------------------
        header = QHBoxLayout()
        self.title_label = QLabel(name)
        self.title_label.setStyleSheet("font-size: 26px; font-weight: bold;")
        self.state_badge = QLabel("Disconnessa")
        self.state_badge.setStyleSheet("color: gray; font-size: 18px; font-weight: bold;")
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.state_badge)
        outer.addLayout(header)

        # --- Riga principale: anteprima + gauge + temperature -----------
        top_row = QHBoxLayout()
        top_row.setSpacing(28)

        if widgets_enabled.get("plate_preview", True):
            self.preview_label = QLabel(PLACEHOLDER_TEXT)
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_label.setFixedSize(PREVIEW_SIZE, PREVIEW_SIZE)
            self.preview_label.setStyleSheet(
                "background: #2a2a2a; border-radius: 14px; color: #888; font-size: 14px;"
            )
            top_row.addWidget(self.preview_label, 0, Qt.AlignmentFlag.AlignTop)
        else:
            self.preview_label = None

        if widgets_enabled.get("progress", True):
            self.gauge = CircularGauge(diameter=GAUGE_SIZE, thickness=16)
            top_row.addWidget(self.gauge, 0, Qt.AlignmentFlag.AlignTop)
        else:
            self.gauge = None

        if widgets_enabled.get("temperatures", True):
            temp_box = QVBoxLayout()
            temp_box.setSpacing(10)
            self.nozzle_label = QLabel("Ugello —/— °C")
            self.bed_label = QLabel("Piatto —/— °C")
            self.fan_label = QLabel("Ventole —% · —%")
            for lbl in (self.nozzle_label, self.bed_label, self.fan_label):
                lbl.setStyleSheet("font-size: 19px;")
            temp_box.addWidget(self.nozzle_label)
            temp_box.addWidget(self.bed_label)
            temp_box.addWidget(self.fan_label)
            top_row.addLayout(temp_box)
        else:
            self.nozzle_label = self.bed_label = self.fan_label = None

        top_row.addStretch()
        outer.addLayout(top_row)

        # --- Nome lavoro ---------------------------------------------------
        if widgets_enabled.get("progress", True):
            self.task_label = QLabel("Nessun lavoro in corso")
            self.task_label.setWordWrap(True)
            self.task_label.setStyleSheet("color: #bbb; font-size: 16px;")
            outer.addWidget(self.task_label)
        else:
            self.task_label = None

        # --- Layer + fine stimata ------------------------------------------
        info_row = QHBoxLayout()
        info_row.setSpacing(18)
        if widgets_enabled.get("progress", True):
            self.layer_label = QLabel("Layer —")
            self.layer_label.setStyleSheet("font-size: 17px;")
            info_row.addWidget(self.layer_label)
        else:
            self.layer_label = None

        if widgets_enabled.get("progress", True) and widgets_enabled.get("finish_time", True):
            sep = QLabel("·")
            sep.setStyleSheet("color: #555; font-size: 17px;")
            info_row.addWidget(sep)

        if widgets_enabled.get("finish_time", True):
            self.finish_label = QLabel("Fine —")
            self.finish_label.setStyleSheet("font-size: 17px;")
            info_row.addWidget(self.finish_label)
        else:
            self.finish_label = None
        info_row.addStretch()
        if self.layer_label or self.finish_label:
            outer.addLayout(info_row)

        # --- AMS: slot in stile "spool card", scorrevole se necessario ----
        if widgets_enabled.get("ams", True):
            self.ams_title = QLabel("AMS")
            self.ams_title.setStyleSheet("color: #999; font-size: 16px; margin-top: 4px;")
            outer.addWidget(self.ams_title)

            self.ams_scroll = QScrollArea()
            self.ams_scroll.setWidgetResizable(True)
            self.ams_scroll.setFixedHeight(150)
            self.ams_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.ams_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.ams_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

            ams_container = QWidget()
            ams_container.setStyleSheet("background: transparent;")
            self.ams_row = QHBoxLayout(ams_container)
            self.ams_row.setSpacing(14)
            self.ams_row.setContentsMargins(0, 4, 0, 4)
            self.ams_scroll.setWidget(ams_container)
            outer.addWidget(self.ams_scroll)
        else:
            self.ams_title = self.ams_row = self.ams_scroll = None

        # --- Controlli --------------------------------------------------------
        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.pause_btn = QPushButton("Pausa")
        self.resume_btn = QPushButton("Riprendi")
        self.stop_btn = QPushButton("Stop")
        self.pause_btn.clicked.connect(lambda: self._safe_call(self.on_pause))
        self.resume_btn.clicked.connect(lambda: self._safe_call(self.on_resume))
        self.stop_btn.clicked.connect(self._confirm_stop)
        controls.addWidget(self.pause_btn)
        controls.addWidget(self.resume_btn)
        controls.addWidget(self.stop_btn)
        outer.addLayout(controls)

        if widgets_enabled.get("skip_object", True):
            skip_row = QHBoxLayout()
            skip_row.setSpacing(10)
            skip_label = QLabel("Salta pezzo n.:")
            skip_label.setStyleSheet("font-size: 16px;")
            skip_row.addWidget(skip_label)
            self.skip_spin = QSpinBox()
            self.skip_spin.setRange(0, 200)
            self.skip_btn = QPushButton("Salta")
            self.skip_btn.clicked.connect(self._on_skip_clicked)
            skip_row.addWidget(self.skip_spin)
            skip_row.addWidget(self.skip_btn)
            skip_row.addStretch()
            outer.addLayout(skip_row)
            note = QLabel("Se rifiutato dalla stampante: serve il Developer Mode.")
            note.setStyleSheet("color: #6a6a6a; font-size: 12px;")
            outer.addWidget(note)
        else:
            self.skip_spin = self.skip_btn = None

        outer.addStretch()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ------------------------------------------------------------------
    def _safe_call(self, fn) -> None:
        if fn:
            fn()

    def _confirm_stop(self) -> None:
        reply = QMessageBox.question(
            self, "Confermi l'arresto?",
            f"Vuoi davvero interrompere la stampa su {self.name}?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._safe_call(self.on_stop)

    def _on_skip_clicked(self) -> None:
        if self.on_skip_object:
            self.on_skip_object(self.skip_spin.value())

    def set_connected(self, connected: bool) -> None:
        if connected:
            self.state_badge.setText("Connessa")
            self.state_badge.setStyleSheet("color: #4caf50; font-size: 18px; font-weight: bold;")
        else:
            self.state_badge.setText("Disconnessa")
            self.state_badge.setStyleSheet("color: gray; font-size: 18px; font-weight: bold;")

    # ------------------------------------------------------------------
    def update_status(self, status: PrinterStatus) -> None:
        self.state_badge.setText(status.state_label)

        if self.gauge is not None:
            self.gauge.set_value(status.progress_percent or 0)
            color = {
                "RUNNING": "#2196f3",
                "PAUSE": "#ffb300",
                "FINISH": "#4caf50",
                "FAILED": "#e53935",
            }.get(status.raw_state, "#2196f3")
            self.gauge.set_progress_color(color)

        if self.task_label is not None:
            self.task_label.setText(status.task_name or "Nessun lavoro in corso")

        if self.layer_label is not None:
            if status.current_layer and status.total_layers:
                self.layer_label.setText(f"Layer {status.current_layer}/{status.total_layers}")
            else:
                self.layer_label.setText("Layer —")

        if self.finish_label is not None:
            finish = status.estimated_finish_time
            if finish and status.remaining_minutes is not None:
                self.finish_label.setText(
                    f"Fine {finish.strftime('%H:%M')} (-{status.remaining_minutes} min)"
                )
            else:
                self.finish_label.setText("Fine —")

        if self.nozzle_label is not None:
            self.nozzle_label.setText(
                f"Ugello {_fmt(status.nozzle_temp)}/{_fmt(status.nozzle_target)} °C"
            )
            self.bed_label.setText(
                f"Piatto {_fmt(status.bed_temp)}/{_fmt(status.bed_target)} °C"
            )
            cool = status.cooling_fan_percent
            aux = status.aux_fan_percent
            cool_txt = f"{cool}%" if cool is not None else "—"
            aux_txt = f"{aux}%" if aux is not None else "—"
            self.fan_label.setText(f"Ventole {cool_txt} · {aux_txt}")

        if self.ams_row is not None:
            self._render_ams(status)

    def _render_ams(self, status: PrinterStatus) -> None:
        while self.ams_row.count():
            item = self.ams_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not status.ams_units:
            self.ams_title.setText("AMS non rilevata")
            self.ams_scroll.setVisible(False)
            return

        self.ams_scroll.setVisible(True)
        humidities = [u.humidity for u in status.ams_units if u.humidity is not None]
        if humidities:
            self.ams_title.setText(f"AMS · umidità {humidities[0]}%")
        else:
            self.ams_title.setText("AMS")

        for unit_index, unit in enumerate(status.ams_units):
            prefix = chr(ord("A") + unit_index)
            for tray_index, tray in enumerate(unit.trays):
                slot = AmsTraySlot(f"{prefix}{tray_index + 1}")
                if tray.is_empty:
                    slot.set_empty()
                else:
                    slot.set_filled(tray.material, tray.color_hex)
                self.ams_row.addWidget(slot)
        self.ams_row.addStretch()

    # ------------------------------------------------------------------
    def set_preview_bytes(self, raw_bytes: bytes) -> None:
        """Mostra un'anteprima scaricata dal cloud Bambu (bytes grezzi di
        un'immagine jpg/png)."""
        if self.preview_label is None:
            return
        pixmap = QPixmap()
        if pixmap.loadFromData(raw_bytes):
            scaled = pixmap.scaled(
                PREVIEW_SIZE, PREVIEW_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
        else:
            self.preview_label.setText(PLACEHOLDER_TEXT)


def _fmt(value: Optional[float]) -> str:
    return f"{value:.0f}" if value is not None else "—"
