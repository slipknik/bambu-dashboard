"""
gui/main_window.py
Finestra principale dell'app. Al primo avvio chiede il login Bambu Lab,
recupera le stampanti associate all'account e apre una connessione MQTT
per ciascuna stampante selezionata, mostrando una PrinterCard per ognuna.
"""
from __future__ import annotations

import os
import sys
import threading
import json
from datetime import datetime

import requests
from PySide6.QtCore import Qt, QTimer, QObject, Signal
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QMessageBox, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QTabWidget, QSystemTrayIcon,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QDoubleSpinBox, QMenu,
)

from bambu_cloud import BambuCloudClient, BambuAuthError
from bambu_mqtt import PrinterConnection
from config import AppConfig, load_config, save_config
from gui.login_dialog import LoginDialog
from gui.printer_card import PrinterCard
from translations import tr, set_language, get_language

# ---------------------------------------------------------------------------
# Avvio automatico con Windows (solo su Windows, solo quando frozen in .exe)
# ---------------------------------------------------------------------------
try:
    import winreg as _winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False

_AUTOSTART_REG_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_APP_NAME = "BambuDashboard"


def _is_autostart() -> bool:
    if not _HAS_WINREG:
        return False
    try:
        key = _winreg.OpenKey(
            _winreg.HKEY_CURRENT_USER, _AUTOSTART_REG_KEY, 0, _winreg.KEY_READ
        )
        _winreg.QueryValueEx(key, _AUTOSTART_APP_NAME)
        _winreg.CloseKey(key)
        return True
    except (FileNotFoundError, OSError):
        return False


def _set_autostart(enable: bool) -> None:
    if not _HAS_WINREG:
        return
    try:
        key = _winreg.OpenKey(
            _winreg.HKEY_CURRENT_USER, _AUTOSTART_REG_KEY, 0, _winreg.KEY_SET_VALUE
        )
        if enable:
            _winreg.SetValueEx(
                key, _AUTOSTART_APP_NAME, 0, _winreg.REG_SZ, f'"{sys.executable}"'
            )
        else:
            try:
                _winreg.DeleteValue(key, _AUTOSTART_APP_NAME)
            except FileNotFoundError:
                pass
        _winreg.CloseKey(key)
    except OSError:
        pass


# ---------------------------------------------------------------------------

class _PreviewFetcher(QObject):
    preview_ready = Signal(str, bytes)

    def fetch_async(self, cloud_client: BambuCloudClient, access_token: str, dev_id: str,
                    task_name: str = "") -> None:
        thread = threading.Thread(
            target=self._fetch, args=(cloud_client, access_token, dev_id, task_name), daemon=True
        )
        thread.start()

    def _fetch(self, cloud_client: BambuCloudClient, access_token: str, dev_id: str,
               task_name: str = "") -> None:
        try:
            cover_url = cloud_client.get_current_task_cover_url(
                access_token, dev_id, task_name or None
            )
            if not cover_url:
                return
            resp = requests.get(cover_url, timeout=10)
            if resp.status_code == 200 and resp.content:
                self.preview_ready.emit(dev_id, resp.content)
        except Exception:
            pass


class PrinterPickerDialog(QDialog):
    def __init__(self, devices: list[dict], already_added: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("pick_title"))
        self.devices = devices

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("pick_label")))

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for dev in devices:
            dev_id = dev.get("dev_id", "")
            label = f"{dev.get('name', dev_id)} ({dev.get('dev_model_name', '?')})"
            item = QListWidgetItem(label)
            item.setData(1000, dev_id)
            self.list_widget.addItem(item)
            if dev_id in already_added:
                item.setSelected(True)
        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_devices(self) -> list[dict]:
        selected_ids = {
            self.list_widget.item(i).data(1000)
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).isSelected()
        }
        return [d for d in self.devices if d.get("dev_id") in selected_ids]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bambu Dashboard")
        self.resize(1024, 600)

        self.config: AppConfig = load_config()
        set_language(self.config.language)  # inizializza la lingua salvata
        self.cloud_client: BambuCloudClient | None = None
        self.connections: dict[str, PrinterConnection] = {}
        self.cards: dict[str, PrinterCard] = {}

        self._last_print_state: dict[str, str] = {}
        self._print_start_times: dict[str, datetime] = {}
        self._allow_exit = False

        self._tray = self._build_tray()

        self.preview_fetcher = _PreviewFetcher(self)
        self.preview_fetcher.preview_ready.connect(self._on_preview_ready)
        self._last_preview_task: dict[str, str] = {}
        self._preview_cache: dict[str, bytes] = {}   # chiave: dev_id
        self._preview_task_key: dict[str, str] = {}  # dev_id → task_name per cui è stata scaricata
        self._last_layer: dict[str, int] = {}
        self._preview_retry_timer = QTimer(self)
        self._preview_retry_timer.setInterval(15000)  # ogni 15 secondi nei primi layer
        self._preview_retry_timer.timeout.connect(self._retry_missing_previews)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(
            "QTabBar::tab { padding: 10px 24px; font-size: 16px; font-weight: bold; }"
            "QTabBar::tab:selected { font-size: 16px; font-weight: bold; }"
        )
        self.setCentralWidget(self.tab_widget)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        self._build_toolbar()

        QTimer.singleShot(100, self._startup)

    # ------------------------------------------------------------------
    def _build_tray(self) -> QSystemTrayIcon:
        from gui.icon_helper import make_app_icon
        icon = make_app_icon()
        # Imposta l'icona sulla finestra solo quando NON siamo nell'exe compilato
        # (nell'exe PyInstaller la gestisce già come risorsa PE, meglio non sovrascriverla)
        if not getattr(sys, "frozen", False):
            self.setWindowIcon(icon)
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("Bambu Dashboard")
        tray.activated.connect(self._on_tray_activated)

        # Menu contestuale per la System Tray (in stile Telegram)
        menu = QMenu()
        show_action = menu.addAction(tr("tray_show"))
        show_action.triggered.connect(self._show_window)
        menu.addSeparator()
        exit_action = menu.addAction(tr('tray_exit'))
        exit_action.triggered.connect(self._exit_app)
        tray.setContextMenu(menu)

        tray.show()
        return tray

    def _show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _exit_app(self) -> None:
        self._allow_exit = True
        self._disconnect_all()
        if self._tray:
            self._tray.hide()
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger):
            self._show_window()

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Principale")
        toolbar.setMovable(False)

        self.login_action = toolbar.addAction(tr("tb_login"))
        self.login_action.triggered.connect(self._do_login)

        toolbar.addSeparator()

        self.manage_action = toolbar.addAction(tr("tb_manage"))
        self.manage_action.triggered.connect(self._manage_printers)

        self.refresh_action = toolbar.addAction(tr("tb_refresh"))
        self.refresh_action.triggered.connect(self._refresh_all)



        self.logout_action = toolbar.addAction(tr("tb_logout"))
        self.logout_action.triggered.connect(self._do_logout)

        # Menu selezione lingua
        lang_btn = QPushButton(tr("tb_language"))
        lang_btn.setFlat(True)
        lang_btn.setStyleSheet("QPushButton { padding: 2px 8px; } QPushButton::menu-indicator { width: 0; }")
        lang_menu = QMenu(self)
        action_it = lang_menu.addAction("🇮🇹  Italiano")
        action_en = lang_menu.addAction("🇬🇧  English")
        action_it.triggered.connect(lambda: self._change_language("it"))
        action_en.triggered.connect(lambda: self._change_language("en"))
        lang_btn.setMenu(lang_menu)
        toolbar.addWidget(lang_btn)
        self._lang_btn = lang_btn

        # Avvio automatico: visibile solo nell'exe compilato (non durante sviluppo)
        if getattr(sys, "frozen", False):
            # Spacer per spingere tutto a destra
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            toolbar.addWidget(spacer)

            self.autostart_btn = QPushButton(tr("tb_autostart"))
            self.autostart_btn.setCheckable(True)
            self.autostart_btn.setChecked(_is_autostart())
            self._update_autostart_btn_style(self.autostart_btn.isChecked())
            self.autostart_btn.toggled.connect(self._toggle_autostart)
            toolbar.addWidget(self.autostart_btn)
        else:
            self.autostart_btn = None

        self._update_login_ui()

    def _update_autostart_btn_style(self, checked: bool) -> None:
        if not hasattr(self, "autostart_btn") or self.autostart_btn is None:
            return
        if checked:
            self.autostart_btn.setStyleSheet(
                "QPushButton { background-color: #19F01C; color: black; font-weight: bold; padding: 4px 12px; border-radius: 4px; border: none; }"
                "QPushButton:hover { background-color: #00c853; }"
            )
        else:
            self.autostart_btn.setStyleSheet(
                "QPushButton { background-color: #e53935; color: white; font-weight: bold; padding: 4px 12px; border-radius: 4px; border: none; }"
                "QPushButton:hover { background-color: #d32f2f; }"
            )

    def _update_login_ui(self) -> None:
        logged_in = bool(self.config.access_token)
        self.login_action.setVisible(not logged_in)
        self.login_action.setText(tr("tb_login"))
        self.logout_action.setVisible(logged_in)
        self.logout_action.setText(tr("tb_logout"))
        self.manage_action.setEnabled(logged_in)
        self.manage_action.setText(tr("tb_manage"))
        self.refresh_action.setEnabled(logged_in)
        self.refresh_action.setText(tr("tb_refresh"))
        self._lang_btn.setText(tr("tb_language"))

    def _change_language(self, lang: str) -> None:
        """Cambia lingua, salva la preferenza e ricostruisce la UI."""
        if lang == get_language():
            return
        set_language(lang)
        self.config.language = lang
        save_config(self.config)
        # Aggiorna toolbar
        self._update_login_ui()
        if self.autostart_btn:
            self.autostart_btn.setText(tr("tb_autostart"))
        # Aggiorna tab storico se esiste
        if hasattr(self, "history_tab"):
            idx = self.tab_widget.indexOf(self.history_tab)
            if idx >= 0:
                self.tab_widget.setTabText(idx, f"📜 {tr('tab_history')}")
        # Ricostruisce le schede (le card leggono tr() al momento della costruzione)
        self._disconnect_all()
        self._rebuild_cards()
        self._connect_all()
        self._restore_previews()  # ripristina le anteprime già scaricate


    def _save_config(self) -> None:
        save_config(self.config)

    def _toggle_autostart(self, checked: bool) -> None:
        _set_autostart(checked)
        self._update_autostart_btn_style(checked)
        msg = tr("autostart_on") if checked else tr("autostart_off")
        self.statusBar().showMessage(msg, 4000)

    # ------------------------------------------------------------------
    def _startup(self) -> None:
        token = self.config.access_token

        if self.config.access_token and not self.config.account_uid:
            temp_client = BambuCloudClient(region=self.config.region)
            uid = temp_client.get_account_uid(self.config.access_token)
            if uid:
                self.config.account_uid = uid
                save_config(self.config)

        if not self.config.access_token:
            self._rebuild_cards()   # mostra il placeholder con il pulsante "Accedi"
            self._do_login()
        else:
            self.cloud_client = BambuCloudClient(region=self.config.region)
            self._update_login_ui()
            self._rebuild_cards()
            self._connect_all()

    def _do_logout(self) -> None:
        self._disconnect_all()
        self.config.access_token  = None
        self.config.refresh_token = None
        self.config.account_uid   = None
        self.config.printers      = []
        save_config(self.config)
        self.cloud_client = None
        self._update_login_ui()
        self._rebuild_cards()

    def _do_login(self) -> None:
        dialog = LoginDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.result_login:
            # L'utente ha annullato: il placeholder con il pulsante "Accedi"
            # rimane visibile nella finestra principale, nessun popup.
            return

        result = dialog.result_login
        self.config.region = dialog.selected_region()
        self.config.access_token = result.access_token
        self.config.refresh_token = result.refresh_token
        self.config.account_uid = result.account_uid
        self._save_config()

        self.cloud_client = BambuCloudClient(region=self.config.region)
        self._update_login_ui()
        self._manage_printers()

    # ------------------------------------------------------------------
    def _manage_printers(self) -> None:
        if not self.cloud_client or not self.config.access_token:
            QMessageBox.warning(self, "Accesso richiesto", "Devi prima accedere con il tuo account Bambu Lab.")
            return
        try:
            devices = self.cloud_client.get_bound_printers(self.config.access_token)
        except BambuAuthError as exc:
            reply = QMessageBox.question(
                self,
                "Errore di accesso",
                f"Non riesco a leggere le stampanti:\n{exc}\n\nVuoi fare il login?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.config.access_token = None
                self.config.refresh_token = None
                # Non salviamo su disco qui: se il re-login non va a buon fine
                # il vecchio token rimane disponibile al prossimo avvio.
                self._update_login_ui()
                self._rebuild_cards()
                self._do_login()
            return

        if not devices:
            QMessageBox.information(self, "Nessuna stampante", "Non risultano stampanti associate al tuo account.")
            return

        already = {p.dev_id for p in self.config.printers}
        picker = PrinterPickerDialog(devices, already, self)
        if picker.exec() != QDialog.DialogCode.Accepted:
            return

        chosen = picker.selected_devices()
        self.config.printers = []
        for dev in chosen:
            self.config.add_printer(
                dev_id=dev.get("dev_id"),
                name=dev.get("name", dev.get("dev_id")),
                model=dev.get("dev_model_name", ""),
            )
        self._save_config()

        self._disconnect_all()
        self._rebuild_cards()
        self._connect_all()

    # ------------------------------------------------------------------
    def _rebuild_cards(self) -> None:
        self.tab_widget.clear()
        for card in self.cards.values():
            card.deleteLater()
        self.cards.clear()

        if not self.config.access_token:
            # Non loggato: placeholder con pulsante di login centrale
            placeholder = QWidget()
            lay = QVBoxLayout(placeholder)
            lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl = QLabel("Accedi con il tuo account Bambu Lab\nper vedere le stampanti.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 16px; color: #888;")
            btn = QPushButton("Accedi")
            btn.setFixedWidth(160)
            btn.setStyleSheet("font-size: 15px; padding: 10px 20px;")
            btn.clicked.connect(self._do_login)
            lay.addWidget(lbl)
            lay.addSpacing(16)
            lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignHCenter)
            self.tab_widget.addTab(placeholder, "")
            self.tab_widget.tabBar().setVisible(False)
            return

        if not self.config.printers:
            placeholder = QLabel(
                "Nessuna stampante configurata.\nUsa 'Gestisci stampanti' per aggiungerne una."
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("font-size: 16px; color: #888;")
            self.tab_widget.addTab(placeholder, "")
            self.tab_widget.tabBar().setVisible(False)
            return

        for printer in self.config.printers:
            card = PrinterCard(printer.dev_id, printer.name, printer.model, self.config.widgets)

            self.tab_widget.addTab(card, printer.name)
            self.cards[printer.dev_id] = card

        # Aggiunge il tab dello Storico
        self.history_tab = PrintHistoryWidget(self)
        self.tab_widget.addTab(self.history_tab, f"📜 {tr('tab_history')}")

        # Tab bar visibile sempre con stampanti reali o storico
        self.tab_widget.tabBar().setVisible(True)

    def _connect_all(self) -> None:
        if not self.config.account_uid or not self.config.access_token:
            self.statusBar().showMessage(
                "Dati di accesso incompleti. Prova a rifare il login.", 10000
            )
            return
        for printer in self.config.printers:
            conn = PrinterConnection(
                mqtt_host=self.cloud_client.mqtt_host(),
                account_uid=self.config.account_uid,
                access_token=self.config.access_token,
                dev_id=printer.dev_id,
                name=printer.name,
                model=printer.model,
            )
            card = self.cards[printer.dev_id]
            conn.status_updated.connect(
                lambda status, d=printer.dev_id: self._on_status_updated(d, status)
            )
            conn.connection_changed.connect(card.set_connected)
            conn.command_error.connect(self._show_error)
            conn.connect()
            self.connections[printer.dev_id] = conn
        self._preview_retry_timer.start()

    def _on_status_updated(self, dev_id: str, status) -> None:
        card = self.cards.get(dev_id)
        if card:
            card.update_status(status)

        prev = self._last_print_state.get(dev_id)
        curr = status.raw_state
        printer_name = status.name or dev_id

        # Stima start time anche se il programma si è avviato a stampa già in corso:
        # se la stampa è RUNNING ma non abbiamo un orario di inizio registrato,
        # lo stimiamo da remaining_minutes e progress_percent.
        if curr == "RUNNING" and dev_id not in self._print_start_times:
            if (status.remaining_minutes is not None and
                    status.progress_percent and 0 < status.progress_percent < 100):
                elapsed = status.remaining_minutes * status.progress_percent / (100 - status.progress_percent)
                from datetime import timedelta
                self._print_start_times[dev_id] = datetime.now() - timedelta(minutes=elapsed)
            else:
                self._print_start_times[dev_id] = datetime.now()

        if prev and prev != curr:
            if prev == "RUNNING" and curr == "FINISH":
                self._notify(
                    "Stampa completata ✓",
                    f"{printer_name}: {status.task_name or 'lavoro terminato'}",
                    QSystemTrayIcon.MessageIcon.Information,
                )
                self._log_print_history(dev_id, printer_name, status, "Completata")
            elif prev == "RUNNING" and curr == "FAILED":
                self._notify(
                    "Errore stampa",
                    f"{printer_name}: la stampa è fallita",
                    QSystemTrayIcon.MessageIcon.Critical,
                )
                self._log_print_history(dev_id, printer_name, status, "Fallita")
            elif prev in ("IDLE", "FINISH", "FAILED", "PREPARE") and curr == "RUNNING":
                self._notify(
                    "Stampa avviata",
                    f"{printer_name}: {status.task_name or 'stampa in corso'}",
                    QSystemTrayIcon.MessageIcon.Information,
                )
                # Resetta la cache anteprima: anche se il nome del lavoro è
                # identico al precedente (stessa stampa rilanciate), vogliamo
                # sempre scaricare l'anteprima aggiornata della nuova sessione.
                self._last_preview_task.pop(dev_id, None)
                self._preview_cache.pop(dev_id, None)
                # Pulisce anche l'anteprima visiva sulla card
                card = self.cards.get(dev_id)
                if card and card.preview_label:
                    card.preview_label.clear()
                    card.preview_label.setText(
                        card.PLACEHOLDER_TEXT() if callable(getattr(card, "PLACEHOLDER_TEXT", None))
                        else "Nessuna\nanteprima"
                    )

        self._last_print_state[dev_id] = curr

        # Rileva "Ristampa" avviata direttamente dal display della stampante:
        # in quel caso la stampante non passa per FINISH→IDLE→RUNNING (la
        # transizione non viene vista), ma il layer torna a 1 mentre la stampa
        # era già considerata finita o aveva un layer alto. Svuotiamo la cache
        # se il layer è tornato a ≤2 mentre eravamo convinti di avere un'anteprima.
        current_layer = getattr(status, "current_layer", None) or 0
        last_layer = self._last_layer.get(dev_id, 0)
        if (curr == "RUNNING" and current_layer <= 2 and last_layer > 10
                and dev_id in self._preview_cache):
            self._last_preview_task.pop(dev_id, None)
            self._preview_cache.pop(dev_id, None)
            card = self.cards.get(dev_id)
            if card and card.preview_label:
                card.preview_label.clear()
                card.preview_label.setText(
                    card.PLACEHOLDER_TEXT() if callable(getattr(card, "PLACEHOLDER_TEXT", None))
                    else "Nessuna\nanteprima"
                )
        # Aggiorna il layer tracciato SOLO in RUNNING: se lo aggiornassimo anche
        # in PREPARE/FINISH (dove il layer torna a 0), perderemmo l'evidenza
        # "last_layer > 10" prima che il check qui sopra possa scattare.
        if curr == "RUNNING":
            self._last_layer[dev_id] = current_layer

        if status.task_name and self._last_preview_task.get(dev_id) != status.task_name:
            self._last_preview_task[dev_id] = status.task_name
            if self.cloud_client and self.config.access_token:
                self.preview_fetcher.fetch_async(
                    self.cloud_client, self.config.access_token, dev_id,
                    status.task_name
                )

    def _notify(self, title: str, message: str,
                icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information) -> None:
        if self._tray and self._tray.isSystemTrayAvailable():
            self._tray.showMessage(title, message, icon, 6000)

    def _on_preview_ready(self, dev_id: str, image_bytes: bytes) -> None:
        self._preview_cache[dev_id] = image_bytes
        # Registra per quale task è stata scaricata questa anteprima
        self._preview_task_key[dev_id] = self._last_preview_task.get(dev_id, "")
        card = self.cards.get(dev_id)
        if card:
            card.set_preview_bytes(image_bytes)

    def _restore_previews(self) -> None:
        """Ripristina le anteprime nelle nuove card dopo un rebuild (es. cambio lingua)."""
        for dev_id, image_bytes in self._preview_cache.items():
            card = self.cards.get(dev_id)
            if card:
                card.set_preview_bytes(image_bytes)

    def _log_print_history(self, dev_id: str, printer_name: str, status, final_state: str) -> None:
        try:
            from config import get_config_dir
            history_file = get_config_dir() / "print_history.json"

            start_time = self._print_start_times.pop(dev_id, None)
            duration_mins = None
            if start_time:
                duration_mins = round((datetime.now() - start_time).total_seconds() / 60)

            # Peso filamento: prova più fonti.
            # 1) Campo diretto mc_print_weight (se presente nel payload)
            weight_g = status.print_weight

            # 2) Estrai dal nome del lavoro se contiene pattern tipo "1h_21g" o "21.5g"
            if weight_g is None and status.task_name:
                import re
                m = re.search(r'(\d+(?:\.\d+)?)g', status.task_name, re.IGNORECASE)
                if m:
                    try:
                        weight_g = float(m.group(1))
                    except ValueError:
                        pass

            # 3) Recupera dal cloud Bambu (ultima attività per questa stampante)
            if weight_g is None and self.cloud_client and self.config.access_token:
                try:
                    resp = self.cloud_client.session.get(
                        f"{self.cloud_client.base_url}/v1/user-service/my/tasks",
                        params={"deviceId": dev_id, "limit": 1},
                        headers={"Authorization": f"Bearer {self.config.access_token}"},
                        timeout=8,
                    )
                    if resp.status_code == 200:
                        hits = resp.json().get("hits") or resp.json().get("list") or []
                        if hits:
                            w = hits[0].get("weight") or hits[0].get("filament_used")
                            if w is not None:
                                weight_g = float(w)
                except Exception:
                    pass

            cost_per_g = self.config.filament_cost_per_kg / 1000.0
            cost_eur = round(weight_g * cost_per_g, 2) if weight_g else 0.0

            history_data = []
            if history_file.exists():
                try:
                    history_data = json.loads(history_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            item = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "printer_id": dev_id,
                "printer_name": printer_name,
                "task_name": status.task_name or "Sconosciuto",
                "duration_mins": duration_mins,
                "weight_g": weight_g,
                "cost_eur": cost_eur,
                "status": final_state,
            }
            history_data.append(item)
            history_file.write_text(
                json.dumps(history_data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as exc:
            print(f"Errore scrittura storico: {exc}")

    def _show_history(self) -> None:
        if hasattr(self, "history_tab") and self.history_tab:
            idx = self.tab_widget.indexOf(self.history_tab)
            if idx != -1:
                self.tab_widget.setCurrentIndex(idx)

    def _on_tab_changed(self, index: int) -> None:
        if hasattr(self, "history_tab") and self.history_tab:
            if self.tab_widget.widget(index) == self.history_tab:
                self.history_tab.refresh()



    def _disconnect_all(self) -> None:
        self._preview_retry_timer.stop()
        for conn in self.connections.values():
            conn.disconnect()
        self.connections.clear()

    def _retry_missing_previews(self) -> None:
        """Ogni 15 secondi: scarica o riscarica l'anteprima se:
        - La stampante è IN STAMPA
        - Non abbiamo ancora un'anteprima per questo task (incluso ristampa stesso file)
        - Il layer è ancora basso (≤ 10) — smette di riprovare a stampa avanzata"""
        if not self.cloud_client or not self.config.access_token:
            return
        for dev_id, state in list(self._last_print_state.items()):
            if state != "RUNNING":
                continue
            layer = self._last_layer.get(dev_id, 0)
            task = self._last_preview_task.get(dev_id, "")
            cached_task = self._preview_task_key.get(dev_id, "")
            # Ritenta se: nessuna anteprima, OPPURE il task è cambiato rispetto a quello cachato
            need_fetch = (dev_id not in self._preview_cache) or (task and task != cached_task)
            if need_fetch and layer <= 10:
                self.preview_fetcher.fetch_async(
                    self.cloud_client, self.config.access_token, dev_id, task
                )

    def _refresh_all(self) -> None:
        for conn in self.connections.values():
            conn.request_full_status()

    def _show_error(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)

    def closeEvent(self, event) -> None:
        if hasattr(self, "_allow_exit") and self._allow_exit:
            self._disconnect_all()
            if self._tray:
                self._tray.hide()
            event.accept()
        else:
            self.hide()
            event.ignore()
            self._notify(
                "Bambu Dashboard",
                "L'applicazione è ancora attiva in background nell'area delle notifiche.",
                QSystemTrayIcon.MessageIcon.Information
            )


class PrintHistoryWidget(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window

        layout = QVBoxLayout(self)

        from config import get_config_dir
        self.history_file = get_config_dir() / "print_history.json"
        
        # Configurazione del costo medio del filamento
        config_row = QHBoxLayout()
        cost_lbl = QLabel(tr("hist_cost_label"))
        cost_lbl.setStyleSheet("font-size: 16px;")
        config_row.addWidget(cost_lbl)
        self.cost_spin = QDoubleSpinBox()
        self.cost_spin.setRange(0.0, 150.0)
        self.cost_spin.setSingleStep(1.0)
        self.cost_spin.setValue(self.main_window.config.filament_cost_per_kg)
        self.cost_spin.setStyleSheet("font-size: 16px; padding: 4px;")
        self.cost_spin.valueChanged.connect(self._on_cost_changed)
        config_row.addWidget(self.cost_spin)
        config_row.addStretch()
        layout.addLayout(config_row)
        layout.addSpacing(6)

        # Statistiche
        stats_layout = QHBoxLayout()
        self.lbl_total = QLabel()
        self.lbl_completed = QLabel()
        self.lbl_weight = QLabel()
        self.lbl_cost = QLabel()
        
        for lbl in (self.lbl_total, self.lbl_completed, self.lbl_weight, self.lbl_cost):
            lbl.setStyleSheet(
                "QLabel { font-size: 17px; font-weight: bold; padding: 8px 16px; "
                "background-color: #2b2b2b; border-radius: 6px; color: #e0e0e0; }"
            )
            stats_layout.addWidget(lbl)
            
        layout.addLayout(stats_layout)
        layout.addSpacing(6)

        # Tabella
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            tr("hist_col_date"), tr("hist_col_printer"), tr("hist_col_job"), tr("hist_col_dur"), tr("hist_col_fil"), tr("hist_col_cost"), tr("hist_col_state")
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        # Font grande per leggibilità su 7 pollici
        from PySide6.QtGui import QFont
        table_font = QFont()
        table_font.setPointSize(13)
        self.table.setFont(table_font)
        header_font = QFont()
        header_font.setPointSize(13)
        header_font.setBold(True)
        self.table.horizontalHeader().setFont(header_font)
        self.table.verticalHeader().setDefaultSectionSize(36)
        layout.addWidget(self.table)

        # Pulsanti d'azione (Azzera, Esporta CSV)
        btn_box = QHBoxLayout()
        btn_clear = QPushButton(tr("hist_clear"))
        btn_clear.setStyleSheet(
            "QPushButton { background-color: #e53935; color: white; font-weight: bold; font-size: 15px; padding: 10px 18px; border-radius: 6px; border: none; }"
            "QPushButton:hover { background-color: #d32f2f; }"
        )
        btn_clear.clicked.connect(self._clear_history)
        
        btn_export = QPushButton(tr("hist_export"))
        btn_export.setStyleSheet("QPushButton { padding: 10px 20px; font-weight: bold; font-size: 15px; }")
        btn_export.clicked.connect(self._export_csv)
        
        btn_box.addWidget(btn_clear)
        btn_box.addStretch()
        btn_box.addWidget(btn_export)
        layout.addLayout(btn_box)

        self._update_stats_and_table()

    def refresh(self) -> None:
        self._update_stats_and_table()

    def _update_stats_and_table(self) -> None:
        history_data = []
        if self.history_file.exists():
            try:
                history_data = json.loads(self.history_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        filament_price_per_g = self.main_window.config.filament_cost_per_kg / 1000.0

        total_prints = len(history_data)
        completed_prints = sum(1 for x in history_data if x.get("status") == "Completata")
        total_weight = sum(x.get("weight_g", 0) for x in history_data)
        total_cost = sum(x.get("weight_g", 0) * filament_price_per_g for x in history_data)

        self.lbl_total.setText(f"{tr('hist_total')} {total_prints}")
        self.lbl_completed.setText(f"{tr('hist_completed')} {completed_prints}")
        self.lbl_weight.setText(f"{tr('hist_fil_label')}: {total_weight:.1f} g")
        self.lbl_cost.setText(f"{tr('hist_cost_spent')}: {total_cost:.2f} €")

        self.table.setRowCount(len(history_data))
        for r, item in enumerate(reversed(history_data)):
            self.table.setItem(r, 0, QTableWidgetItem(str(item.get("timestamp", ""))))
            self.table.setItem(r, 1, QTableWidgetItem(str(item.get("printer_name", ""))))
            self.table.setItem(r, 2, QTableWidgetItem(str(item.get("task_name", ""))))
            
            dur = item.get("duration_mins")
            dur_str = f"{dur} min" if dur is not None else "N/D"
            self.table.setItem(r, 3, QTableWidgetItem(dur_str))
            
            weight = item.get("weight_g", 0)
            weight_str = f"{weight:.1f} g" if weight else "N/D"
            self.table.setItem(r, 4, QTableWidgetItem(weight_str))
            
            cost = weight * filament_price_per_g
            cost_str = f"{cost:.2f} €" if weight else "—"
            self.table.setItem(r, 5, QTableWidgetItem(cost_str))
            
            status_val = item.get("status", "")
            status_item = QTableWidgetItem(status_val)
            if status_val == "Completata":
                status_item.setForeground(QColor("#19F01C"))
            else:
                status_item.setForeground(QColor("#e53935"))
            self.table.setItem(r, 6, status_item)

        self.table.resizeColumnsToContents()

    def _on_cost_changed(self, value: float) -> None:
        self.main_window.config.filament_cost_per_kg = value
        self.main_window._save_config()
        self._update_stats_and_table()

    def _clear_history(self) -> None:
        reply = QMessageBox.question(
            self, "Azzera Storico",
            "Sei sicuro di voler cancellare tutto lo storico delle stampe?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if self.history_file.exists():
                    self.history_file.unlink()
                self._update_stats_and_table()
            except Exception as exc:
                QMessageBox.critical(self, "Errore", f"Impossibile azzerare lo storico:\n{exc}")

    def _export_csv(self) -> None:
        import csv
        from PySide6.QtWidgets import QFileDialog

        history_data = []
        if self.history_file.exists():
            try:
                history_data = json.loads(self.history_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        if not history_data:
            QMessageBox.information(self, "Esporta", "Nessun dato da esportare nello storico.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Salva Storico in CSV", "", "File CSV (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Data/Ora", "Stampante", "Nome Lavoro", "Durata (min)", "Peso (g)", "Costo (Euro)", "Stato"])
                
                filament_price_per_g = self.main_window.config.filament_cost_per_kg / 1000.0
                for item in history_data:
                    weight = item.get("weight_g", 0)
                    cost = weight * filament_price_per_g
                    writer.writerow([
                        item.get("timestamp", ""),
                        item.get("printer_name", ""),
                        item.get("task_name", ""),
                        item.get("duration_mins", ""),
                        f"{weight:.1f}",
                        f"{cost:.2f}",
                        item.get("status", "")
                    ])
            QMessageBox.information(self, "Esporta", "Storico esportato con successo!")
        except Exception as exc:
            QMessageBox.critical(self, "Errore", f"Impossibile esportare il file CSV:\n{exc}")
