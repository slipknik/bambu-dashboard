"""
gui/login_dialog.py
Login Bambu Lab con due modalità:
  - Email + password  (account nativi Bambu)
  - Codice via email  (account Google / Apple — stesso flow usato da ha-bambulab)
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QLabel, QHBoxLayout, QMessageBox, QComboBox, QTabWidget, QWidget, QCheckBox,
)

from bambu_cloud import BambuCloudClient, BambuVerificationRequired, BambuAuthError, LoginResult


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Accedi con il tuo account Bambu Lab")
        self.setMinimumWidth(400)

        self.result_login: LoginResult | None = None
        self._client: BambuCloudClient | None = None
        self._pw_awaiting_code = False
        self._pw_email = ""

        layout = QVBoxLayout(self)

        region_row = QHBoxLayout()
        region_row.addWidget(QLabel("Regione account:"))
        self.region_combo = QComboBox()
        self.region_combo.addItem("Internazionale (bambulab.com)", "us")
        self.region_combo.addItem("Cina (bambulab.cn)", "cn")
        region_row.addWidget(self.region_combo)
        layout.addLayout(region_row)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_password_tab(), "Email + Password")
        self.tabs.addTab(self._build_code_tab(),     "Google / Apple")
        layout.addWidget(self.tabs)

        self.remember_check = QCheckBox("Ricorda accesso su questo dispositivo")
        self.remember_check.setChecked(True)
        layout.addWidget(self.remember_check)

        note = QLabel(
            "Le credenziali vengono usate solo per autenticarti con i server\n"
            "ufficiali Bambu Lab. Non viene salvata la password, solo il token."
        )
        note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(note)

    # ── Tab 1: email + password ──────────────────────────────────────────
    def _build_password_tab(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 8, 0, 0)

        form = QFormLayout()
        self.email_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.twofa_label = QLabel("Codice verifica (email):")
        self.twofa_edit  = QLineEdit()
        self.twofa_label.setVisible(False)
        self.twofa_edit.setVisible(False)
        form.addRow("Email:", self.email_edit)
        form.addRow("Password:", self.password_edit)
        form.addRow(self.twofa_label, self.twofa_edit)
        vbox.addLayout(form)

        btn = QPushButton("Accedi")
        btn.clicked.connect(self._on_password_login)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn)
        vbox.addLayout(row)
        self._pw_btn = btn
        return w

    # ── Tab 2: codice email — per account Google / Apple ─────────────────
    def _build_code_tab(self) -> QWidget:
        w = QWidget()
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(0, 8, 0, 0)

        info = QLabel(
            "Se il tuo account Bambu Lab è collegato a Google, Apple o\n"
            "un altro provider, inserisci qui la tua email Bambu Lab.\n"
            "Riceverai un codice di accesso nella casella email."
        )
        info.setStyleSheet("color: #bbb; font-size: 12px;")
        vbox.addWidget(info)
        vbox.addSpacing(8)

        form = QFormLayout()
        self.code_email_edit = QLineEdit()
        self.code_code_label = QLabel("Codice ricevuto per email:")
        self.code_code_edit  = QLineEdit()
        self.code_code_label.setVisible(False)
        self.code_code_edit.setVisible(False)
        form.addRow("Email account:", self.code_email_edit)
        form.addRow(self.code_code_label, self.code_code_edit)
        vbox.addLayout(form)

        self._send_btn   = QPushButton("Invia codice via email")
        self._verify_btn = QPushButton("Accedi con il codice")
        self._verify_btn.setVisible(False)
        self._send_btn.clicked.connect(self._on_send_code)
        self._verify_btn.clicked.connect(self._on_verify_code)

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self._send_btn)
        row.addWidget(self._verify_btn)
        vbox.addLayout(row)
        vbox.addStretch()
        return w

    # ── Helpers ──────────────────────────────────────────────────────────
    def _get_client(self) -> BambuCloudClient:
        region = self.region_combo.currentData()
        if self._client is None or self._client.region != region:
            self._client = BambuCloudClient(region=region)
        return self._client

    # ── Slot tab password ────────────────────────────────────────────────
    def _on_password_login(self) -> None:
        client = self._get_client()
        if not self._pw_awaiting_code:
            self._pw_email = self.email_edit.text().strip()
            password = self.password_edit.text()
            if not self._pw_email or not password:
                QMessageBox.warning(self, "Dati mancanti", "Inserisci email e password.")
                return
            try:
                self.result_login = client.login(self._pw_email, password)
                self.accept()
            except BambuVerificationRequired:
                self._pw_awaiting_code = True
                self.twofa_label.setVisible(True)
                self.twofa_edit.setVisible(True)
                self._pw_btn.setText("Verifica codice")
                try:
                    client.request_verification_code(self._pw_email)
                except Exception:
                    pass
                QMessageBox.information(
                    self, "Codice richiesto",
                    "Bambu Lab ha inviato un codice alla tua email.\n"
                    "Inseriscilo qui sotto e clicca 'Verifica codice'."
                )
            except BambuAuthError as exc:
                QMessageBox.critical(self, "Login non riuscito", str(exc))
        else:
            code = self.twofa_edit.text().strip()
            if not code:
                QMessageBox.warning(self, "Codice mancante", "Inserisci il codice ricevuto.")
                return
            try:
                self.result_login = client.login_with_code(self._pw_email, code)
                self.accept()
            except BambuAuthError as exc:
                QMessageBox.critical(self, "Verifica non riuscita", str(exc))

    # ── Slot tab codice email ────────────────────────────────────────────
    def _on_send_code(self) -> None:
        email = self.code_email_edit.text().strip()
        if not email:
            QMessageBox.warning(self, "Email mancante",
                                "Inserisci l'indirizzo email del tuo account Bambu Lab.")
            return
        client = self._get_client()
        try:
            client.request_verification_code(email)
        except Exception as exc:
            QMessageBox.critical(self, "Errore invio codice",
                                 f"Impossibile inviare il codice:\n{exc}")
            return

        self.code_code_label.setVisible(True)
        self.code_code_edit.setVisible(True)
        self._send_btn.setText("Reinvia codice")
        self._verify_btn.setVisible(True)
        QMessageBox.information(
            self, "Codice inviato",
            f"Codice inviato a: {email}\n\n"
            "Controlla la casella email (anche spam) e inserisci il codice di 6 cifre."
        )

    def _on_verify_code(self) -> None:
        email = self.code_email_edit.text().strip()
        code  = self.code_code_edit.text().strip()
        if not code:
            QMessageBox.warning(self, "Codice mancante",
                                "Inserisci il codice ricevuto per email.")
            return
        client = self._get_client()
        try:
            self.result_login = client.login_with_code(email, code)
            self.accept()
        except BambuAuthError as exc:
            QMessageBox.critical(self, "Codice non valido", str(exc))

    def selected_region(self) -> str:
        return self.region_combo.currentData()

    @property
    def save_credentials(self) -> bool:
        return self.remember_check.isChecked()
