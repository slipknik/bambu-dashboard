"""
gui/printer_card.py
Dashboard a tutta pagina per UNA stampante ottimizzata per 1024x600 (7").
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSizePolicy, QScrollArea, QGroupBox, QPushButton, QComboBox, QGridLayout
)

from models import PrinterStatus
from gui.circular_gauge import CircularGauge
from gui.ams_tray import AmsTraySlot, AmsUnitWidget
from translations import tr

def PLACEHOLDER_TEXT() -> str:
    return tr("preview_none")
PREVIEW_SIZE = 188
GAUGE_SIZE   = 188


class PrinterCard(QWidget):

    def __init__(self, dev_id: str, name: str, model: str, widgets_enabled: dict, parent=None):
        super().__init__(parent)
        self.dev_id = dev_id
        self.name   = name
        self.model  = model
        self.widgets_enabled = widgets_enabled
        self._last_state = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(8)

        # ── Header: solo titolo e segnale wifi (no badge stato) ─────────────
        header = QHBoxLayout()
        title_text = name
        self.title_label = QLabel(title_text)
        self.title_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        self.wifi_label = QLabel("")
        self.wifi_label.setStyleSheet("font-size: 15px; color: #5bc4f5; font-weight: bold; margin-left: 8px;")
        header.addWidget(self.title_label)
        header.addWidget(self.wifi_label)
        header.addStretch()
        outer.addLayout(header)

        # ── Riga principale: anteprima | gauge | temperature | zona stato ────
        top_row = QHBoxLayout()
        top_row.setSpacing(20)

        if widgets_enabled.get("plate_preview", True):
            self.preview_label = QLabel(PLACEHOLDER_TEXT())
            self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.preview_label.setFixedSize(PREVIEW_SIZE, PREVIEW_SIZE)
            self.preview_label.setStyleSheet(
                "background: #757575; border-radius: 12px; color: #ddd; font-size: 13px;"
            )
            top_row.addWidget(self.preview_label, 0, Qt.AlignmentFlag.AlignTop)
        else:
            self.preview_label = None

        if widgets_enabled.get("progress", True):
            self.gauge = CircularGauge(diameter=GAUGE_SIZE, thickness=16)
            top_row.addWidget(self.gauge, 0, Qt.AlignmentFlag.AlignTop)
        else:
            self.gauge = None

        # ── Colonna destra ───────────────────────────────────────────────────
        right_col = QVBoxLayout()
        right_col.setSpacing(0)

        if widgets_enabled.get("temperatures", True):
            self.nozzle_label  = QLabel(tr("nozzle") + "   —/— °C")
            self.bed_label     = QLabel(tr("bed") + "    —/— °C")
            self.chamber_label = QLabel(tr("chamber") + "  — °C")
            self.fan_label     = QLabel("Cool —%  ·  Aux —%")
            self.extra_label   = QLabel("")
            for lbl in (self.nozzle_label, self.bed_label, self.chamber_label):
                lbl.setStyleSheet("font-size: 21px; letter-spacing: 0.5px;")
            self.fan_label.setStyleSheet("font-size: 16px; color: #aaa;")
            self.extra_label.setStyleSheet("font-size: 14px; color: #777;")
            self.chamber_label.setVisible(False)
            right_col.addWidget(self.nozzle_label)
            right_col.addSpacing(4)
            right_col.addWidget(self.bed_label)
            right_col.addSpacing(4)
            right_col.addWidget(self.chamber_label)
            right_col.addSpacing(4)
            right_col.addWidget(self.fan_label)
            right_col.addSpacing(2)
            right_col.addWidget(self.extra_label)
            right_col.addSpacing(4)
        else:
            self.nozzle_label = self.bed_label = self.chamber_label = self.fan_label = self.extra_label = None

        # Riga dettaglio: ugello + velocità
        if widgets_enabled.get("progress", True) or widgets_enabled.get("temperatures", True):
            self.detail_label = QLabel("")
            self.detail_label.setStyleSheet("font-size: 14px; color: #888;")
            right_col.addWidget(self.detail_label)
            right_col.addSpacing(4)
        else:
            self.detail_label = None

        right_col.addStretch(1)

        if widgets_enabled.get("progress", True):
            self.task_label = QLabel(tr("no_job"))
            self.task_label.setWordWrap(True)
            self.task_label.setStyleSheet("color: #bbb; font-size: 15px;")
            right_col.addWidget(self.task_label)
            right_col.addSpacing(4)
        else:
            self.task_label = None

        # Riga info: Layer · Fine · Peso
        info_row = QHBoxLayout()
        info_row.setSpacing(10)

        if widgets_enabled.get("progress", True):
            self.layer_label = QLabel(tr("layer") + " —")
            self.layer_label.setStyleSheet("font-size: 17px;")
            info_row.addWidget(self.layer_label)
        else:
            self.layer_label = None

        if widgets_enabled.get("finish_time", True):
            if self.layer_label:
                sep = QLabel("·")
                sep.setStyleSheet("color: #555; font-size: 17px;")
                info_row.addWidget(sep)
            self.finish_label = QLabel(tr("finish") + " —")
            self.finish_label.setStyleSheet("font-size: 17px;")
            info_row.addWidget(self.finish_label)
        else:
            self.finish_label = None

        if widgets_enabled.get("progress", True):
            self.weight_label = QLabel("")
            self.weight_label.setStyleSheet("font-size: 14px; color: #888;")
            info_row.addWidget(self.weight_label)

        if self.layer_label or self.finish_label:
            info_row.addStretch()
            right_col.addLayout(info_row)

        top_row.addLayout(right_col, 1)

        # ── Terza colonna: stato + fasi stampa + operazioni AMS ─────────────
        status_col = QVBoxLayout()
        status_col.setSpacing(6)
        status_col.setContentsMargins(0, 0, 0, 0)
        status_col.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # Stato principale (IN STAMPA, COMPLETATA, ecc.) — maiuscolo, stessa riga delle altre
        self.state_badge = QLabel(tr("disconnected").upper())
        self.state_badge.setStyleSheet("color: gray; font-size: 17px; font-weight: bold;")
        self.state_badge.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        status_col.addWidget(self.state_badge)

        # 🖨 fasi di stampa
        self.stage_label = QLabel("")
        self.stage_label.setStyleSheet("color: #4fc3f7; font-size: 17px; font-weight: bold;")
        self.stage_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.stage_label.setWordWrap(True)
        self.stage_label.setVisible(False)
        status_col.addWidget(self.stage_label)

        # ⚙ operazioni AMS
        self.ams_badge = QLabel("")
        self.ams_badge.setStyleSheet("color: #19F01C; font-size: 17px; font-weight: bold;")
        self.ams_badge.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.ams_badge.setWordWrap(True)
        self.ams_badge.setVisible(False)
        status_col.addWidget(self.ams_badge)

        status_col.addStretch()
        top_row.addLayout(status_col, 1)

        outer.addLayout(top_row)



        # ── AMS — scroll verticale con unità collassabili ────────────────────
        if widgets_enabled.get("ams", True):
            self.ams_scroll = QScrollArea()
            self.ams_scroll.setWidgetResizable(True)
            self.ams_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.ams_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.ams_scroll.setStyleSheet(
                "QScrollArea { border: none; background: transparent; }"
            )
            ams_container = QWidget()
            ams_container.setStyleSheet("background: transparent;")
            self.ams_col = QGridLayout(ams_container)
            self.ams_col.setSpacing(6)
            self.ams_col.setContentsMargins(0, 2, 0, 2)
            self.ams_scroll.setWidget(ams_container)
            outer.addWidget(self.ams_scroll, 1)
        else:
            self.ams_col = self.ams_scroll = None
            self.ams_status_label = None
            outer.addStretch(1)

        self._ams_collapsed: dict[str, bool] = {}  # label → True se collassata
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ────────────────────────────────────────────────────────────────────────
    _STATE_COLORS = {
        "RUNNING": "#19F01C",
        "PAUSE":   "#ffb300",
        "FINISH":  "#19F01C",
        "FAILED":  "#e53935",
        "IDLE":    "#aaa",
        "PREPARE": "#ffb300",
        "SLICING": "#aaa",
    }

    def set_connected(self, connected: bool) -> None:
        if not connected:
            # La stampante è definitivamente offline: mostriamolo
            self.state_badge.setText(tr("disconnected").upper())
            self.state_badge.setStyleSheet("color: gray; font-size: 17px; font-weight: bold;")
            self.wifi_label.setText("")
        # Se connected=True non facciamo nulla: il badge verrà aggiornato
        # da update_status quando arrivano i dati reali via MQTT.
        # Questo evita il badge "CONNECTED..." ambiguo che appare anche
        # quando la stampante è spenta ma il cloud la segna ancora online.

    def update_status(self, status: PrinterStatus) -> None:
        # Badge stato principale — MAIUSCOLO, stessa colonna di fasi e AMS
        badge_color = self._STATE_COLORS.get(status.raw_state, "#ccc")
        self.state_badge.setText(status.state_label.upper())
        self.state_badge.setStyleSheet(
            f"color: {badge_color}; font-size: 17px; font-weight: bold;"
        )

        # 🖨 Fase di stampa dettagliata (livellamento, riscaldamento, ecc.)
        stage_text = status.sub_stage_label
        if stage_text:
            self.stage_label.setText(f"🖨  {stage_text}")
            self.stage_label.setVisible(True)
        else:
            self.stage_label.setVisible(False)

        # ⚙ Operazione AMS (cambio filamento, taglio, spurgo, ecc.)
        from models import ams_status_label as _ams_status_label
        ams_text = _ams_status_label(status.ams_status)
        if ams_text:
            self.ams_badge.setText(f"⚙  {ams_text}")
            self.ams_badge.setVisible(True)
        else:
            self.ams_badge.setVisible(False)

        # Segnale Wi-Fi (Convertito a 5 tacche)
        if hasattr(status, "wifi_signal") and status.wifi_signal:
            try:
                sig_val = int(status.wifi_signal.replace("dBm", "").strip())
                if sig_val >= -50:
                    bars = "📶 5/5"
                elif sig_val >= -60:
                    bars = "📶 4/5"
                elif sig_val >= -70:
                    bars = "📶 3/5"
                elif sig_val >= -80:
                    bars = "📶 2/5"
                else:
                    bars = "📶 1/5"
                self.wifi_label.setText(bars)
            except Exception:
                self.wifi_label.setText("📶 —")
        else:
            self.wifi_label.setText("")

        if self.gauge is not None:
            self.gauge.set_value(status.progress_percent or 0)
            self.gauge.set_progress_color(self._STATE_COLORS.get(status.raw_state, "#19F01C"))

        if self.task_label is not None:
            self.task_label.setText(status.task_name or tr("no_job"))

        if self.layer_label is not None:
            if status.current_layer and status.total_layers:
                self.layer_label.setText(f"{tr('layer')} {status.current_layer}/{status.total_layers}")
            else:
                self.layer_label.setText(tr("layer") + " —")

        if self.finish_label is not None:
            finish = status.estimated_finish_time
            if finish and status.remaining_minutes is not None:
                h = status.remaining_minutes // 60
                m = status.remaining_minutes % 60
                time_str = f"{h}h {m}m"
                self.finish_label.setText(
                    f"{tr('finish')} {finish.strftime('%H:%M')}  (-{time_str})"
                )
            else:
                self.finish_label.setText(tr("finish") + " —")

        if hasattr(self, "weight_label"):
            if status.print_weight is not None and status.print_weight > 0:
                self.weight_label.setText(f"· {status.print_weight:.1f} g")
            else:
                self.weight_label.setText("")

        if self.nozzle_label is not None:
            self.nozzle_label.setText(
                f"{tr('nozzle')}   {_fmt(status.nozzle_temp)}/{_fmt(status.nozzle_target)} °C"
            )
            self.bed_label.setText(
                f"{tr('bed')}    {_fmt(status.bed_temp)}/{_fmt(status.bed_target)} °C"
            )
            if status.chamber_temp is not None:
                self.chamber_label.setText(f"{tr('chamber')}  {_fmt(status.chamber_temp)} °C")
                self.chamber_label.setVisible(True)

            # Ventole con etichette
            cool = status.cooling_fan_percent
            aux  = status.aux_fan_percent
            cam  = status.chamber_fan_percent
            fan_parts = []
            fan_parts.append(f"Cool {cool}%" if cool is not None else "Cool —%")
            fan_parts.append(f"Aux {aux}%"  if aux  is not None else "Aux —%")
            if cam is not None:
                fan_parts.append(f"Cam {cam}%")
            self.fan_label.setText("  ·  ".join(fan_parts))

            # Riga info extra: SD card + luce camera
            extra_parts = []
            if status.sd_free_kb is not None:
                gb = status.sd_free_kb / (1024 * 1024)
                if gb >= 1:
                    extra_parts.append(f"SD {gb:.1f} GB")
                else:
                    extra_parts.append(f"SD {status.sd_free_kb // 1024} MB")
            if status.chamber_light_on is not None:
                extra_parts.append(tr("light_on") if status.chamber_light_on else tr("light_off"))
            self.extra_label.setText("  ·  ".join(extra_parts))

        if self.detail_label is not None:
            parts = []
            if status.nozzle_diameter:
                parts.append(f"Ø {status.nozzle_diameter} mm")
            if status.speed_label:
                parts.append(status.speed_label)
            self.detail_label.setText("  ·  ".join(parts))

        # Salva lo stato
        self._last_state = status.raw_state



        if self.ams_col is not None:
            self._render_ams(status)

    def _render_ams(self, status: PrinterStatus) -> None:
        # Salva lo stato collapsed prima di ricostruire i widget
        for i in range(self.ams_col.count()):
            item = self.ams_col.itemAt(i)
            if item:
                w = item.widget()
                if isinstance(w, AmsUnitWidget):
                    self._ams_collapsed[w._unit_label] = not w._btn.isChecked()

        while self.ams_col.count():
            item = self.ams_col.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        has_ams = bool(status.ams_units)
        has_ext = status.vt_tray is not None or status.ams_external_active

        if not has_ams and not has_ext:
            self.ams_scroll.setVisible(False)
            return

        self.ams_scroll.setVisible(True)

        from models import ams_status_label as _ams_status_label

        # Controlla PRIMA del loop se qualche slot ha il bit 4 di state attivo.
        any_state_bit4 = any(
            bool(tray.state & 16)
            for unit in status.ams_units
            if not unit.is_external
            for tray in unit.trays
        )

        widget_count = 0
        regular_index = 0
        first_regular_widget = None

        for unit in status.ams_units:
            if unit.is_external:
                # Unità esterna (id >= 128): essiccatore / AMS HT
                dry_info = ""
                if unit.dry_temp is not None:
                    dry_info = f"🔥 {unit.dry_temp:.0f}°C"
                    if unit.dry_time:
                        dry_info += f" · {unit.dry_time} min"
                label = tr("dryer")
                unit_w = AmsUnitWidget(label, humidity=unit.humidity, temperature=unit.temperature,
                                       extra_label=dry_info or None)
                for tray in unit.trays:
                    try:
                        tray_num = int(tray.slot_id)
                    except (ValueError, TypeError):
                        tray_num = None
                    display = f"E{tray_num + 1}" if tray_num is not None else "E?"
                    slot = AmsTraySlot(display)
                    if tray.is_empty:
                        slot.set_empty()
                    else:
                        slot.set_filled(tray.material, tray.color_hex)
                    unit_w.add_slot(slot)
            else:
                label = f"AMS {regular_index + 1}"
                unit_w = AmsUnitWidget(label, humidity=unit.humidity, temperature=unit.temperature)
                if first_regular_widget is None:
                    first_regular_widget = unit_w
                prefix = chr(ord("A") + regular_index)

                try:
                    unit_id_int = int(unit.unit_id)
                except (ValueError, TypeError):
                    unit_id_int = regular_index

                # Questa unità è quella attiva se contiene il tray_now
                unit_has_active = False
                for tray in unit.trays:
                    try:
                        tray_num = int(tray.slot_id)
                    except (ValueError, TypeError):
                        tray_num = None
                    display = f"{prefix}{tray_num + 1}" if tray_num is not None else f"{prefix}?"
                    slot = AmsTraySlot(display)
                    if tray.is_empty:
                        slot.set_empty()
                    else:
                        slot.set_filled(tray.material, tray.color_hex)
                    if any_state_bit4:
                        # P2S e firmware recenti: usa il bit 4 di tray.state
                        is_active = not status.ams_external_active and bool(tray.state & 16)
                    else:
                        # A1 e firmware vecchi: usa tray_now come indice assoluto
                        is_active = (
                            not status.ams_external_active
                            and status.ams_tray_now is not None
                            and tray_num is not None
                            and status.ams_tray_now == unit_id_int * 4 + tray_num
                        )
                    if is_active:
                        unit_has_active = True
                    slot.set_active(is_active)
                    unit_w.add_slot(slot)

                # Mostra lo stato AMS nella label dedicata in alto (gestito in update_status)
                regular_index += 1

            unit_w.finalize()
            if self._ams_collapsed.get(label, False):
                unit_w._btn.setChecked(False)
                unit_w._toggle(False)

            row_idx = widget_count // 2
            col_idx = widget_count % 2
            self.ams_col.addWidget(unit_w, row_idx, col_idx)
            widget_count += 1

        if has_ext:
            label = tr("external_spool")
            ext_w = AmsUnitWidget(label)
            ext_slot = AmsTraySlot("Ext")
            vt = status.vt_tray
            if vt and not vt.is_empty:
                ext_slot.set_filled(vt.material, vt.color_hex)
            else:
                ext_slot.set_empty()
            ext_slot.set_active(status.ams_external_active)
            ext_w.add_slot(ext_slot)
            ext_w.finalize()
            if self._ams_collapsed.get(label, False):
                ext_w._btn.setChecked(False)
                ext_w._toggle(False)
            row_idx = widget_count // 2
            col_idx = widget_count % 2
            self.ams_col.addWidget(ext_w, row_idx, col_idx)
            widget_count += 1

        # Colonne uguali, stretch verticale sull'ultima riga vuota
        self.ams_col.setColumnStretch(0, 1)
        self.ams_col.setColumnStretch(1, 1)
        row_count = (widget_count + 1) // 2
        for r in range(row_count):
            self.ams_col.setRowStretch(r, 0)
        self.ams_col.setRowStretch(row_count, 1)

    def set_preview_bytes(self, raw_bytes: bytes) -> None:
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
            self.preview_label.setText(PLACEHOLDER_TEXT())




def _fmt(value: Optional[float]) -> str:
    return f"{value:.0f}" if value is not None else "—"
