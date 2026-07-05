"""
config.py
Gestisce il file di configurazione locale dell'app (account, stampanti, preferenze).
Il file viene salvato in %APPDATA%/BambuDashboard/config.json su Windows
(o ~/.bambu_dashboard/config.json su altri OS, utile per testare su Linux/Mac).

Nessun dato viene mai inviato a server diversi da quelli ufficiali Bambu Lab:
questo file resta sempre solo sul disco locale dell'utente.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


APP_DIR_NAME = "BambuDashboard"

# Le 6 informazioni che l'utente ha scelto di vedere. Tenerle qui come
# costanti centralizza la "personalizzazione": per aggiungerne altre in
# futuro basta aggiungere una voce qui e il relativo widget nella GUI.
DEFAULT_WIDGETS = {
    "progress": True,        # stato, progresso, tempo rimanente
    "temperatures": True,    # ugello/piatto + ventole
    "ams": True,             # stato AMS (materiali, colori, umidita')
    "finish_time": True,     # ora stimata di fine stampa
    "plate_preview": True,   # immagine di anteprima del piatto
}


def get_config_dir() -> Path:
    """Restituisce la cartella dati dell'app, separata per ogni utente Windows.
    Usa sempre APPDATA/BambuDashboard (es. C:/Users/Mario/AppData/Roaming/BambuDashboard)
    cosi' condividere l'exe non porta mai con se' le credenziali di un altro utente.
    La cartella data/ accanto all'exe viene migrata automaticamente se trovata."""
    import sys, shutil

    if os.name == "nt":
        base = os.environ.get("APPDATA", str(Path.home()))
        appdata_dir = Path(base) / APP_DIR_NAME
    else:
        appdata_dir = Path.home() / f".{APP_DIR_NAME.lower()}"

    appdata_dir.mkdir(parents=True, exist_ok=True)

    # Migrazione dalla vecchia posizione (data/ accanto all'exe) se non ancora fatto
    if not (appdata_dir / "config.json").exists():
        try:
            if getattr(sys, "frozen", False):
                old_dir = Path(sys.executable).parent / "data"
            else:
                old_dir = Path(__file__).parent / "data"
            old_config = old_dir / "config.json"
            if old_config.exists():
                # Copia tutti i file dalla vecchia cartella
                for f in old_dir.iterdir():
                    dest = appdata_dir / f.name
                    if not dest.exists():
                        shutil.copy2(f, dest)
        except Exception:
            pass

    return appdata_dir


def get_config_path() -> Path:
    return get_config_dir() / "config.json"


@dataclass
class PrinterConfig:
    """Configurazione di una singola stampante (es. A1, e poi la seconda)."""
    dev_id: str            # serial number Bambu
    name: str              # nome leggibile scelto dall'utente
    model: str = ""        # es. "A1", "P1S", ... (informativo)
    ip: str = ""           # IP locale (opzionale per webcam/LAN)
    access_code: str = ""  # Codice accesso LAN (opzionale per webcam/LAN)


@dataclass
class AppConfig:
    # Token di sessione cloud Bambu (NON la password: la password non viene
    # mai salvata su disco, solo il token ottenuto dopo il login).
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    account_uid: Optional[str] = None
    region: str = "us"  # "us" oppure "cn" in base all'account Bambu
    filament_cost_per_kg: float = 20.0  # Costo medio personalizzabile per calcolare la spesa
    language: str = "it"  # "it" = Italiano, "en" = English

    printers: list[PrinterConfig] = field(default_factory=list)
    widgets: dict = field(default_factory=lambda: dict(DEFAULT_WIDGETS))

    def add_printer(self, dev_id: str, name: str, model: str = "", ip: str = "", access_code: str = "") -> None:
        for p in self.printers:
            if p.dev_id == dev_id:
                p.name = name
                p.model = model or p.model
                p.ip = ip or p.ip
                p.access_code = access_code or p.access_code
                return
        self.printers.append(PrinterConfig(dev_id=dev_id, name=name, model=model, ip=ip, access_code=access_code))

    def remove_printer(self, dev_id: str) -> None:
        self.printers = [p for p in self.printers if p.dev_id != dev_id]


def load_config() -> AppConfig:
    path = get_config_path()
    if not path.exists():
        return AppConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return AppConfig()

    printers = []
    for p in raw.get("printers", []):
        printers.append(PrinterConfig(
            dev_id=p.get("dev_id"),
            name=p.get("name"),
            model=p.get("model", ""),
            ip=p.get("ip", ""),
            access_code=p.get("access_code", "")
        ))
    widgets = dict(DEFAULT_WIDGETS)
    widgets.update(raw.get("widgets", {}))

    return AppConfig(
        access_token=raw.get("access_token"),
        refresh_token=raw.get("refresh_token"),
        account_uid=raw.get("account_uid"),
        region=raw.get("region", "us"),
        filament_cost_per_kg=raw.get("filament_cost_per_kg", 20.0),
        language=raw.get("language", "it"),
        printers=printers,
        widgets=widgets,
    )


def save_config(cfg: AppConfig) -> None:
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    get_config_path().write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
