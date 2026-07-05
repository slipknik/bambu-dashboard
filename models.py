"""
models.py
Rappresenta lo stato di una stampante Bambu Lab, partendo dai messaggi
JSON che la stampante pubblica periodicamente su MQTT (topic "device/<id>/report").

NOTA IMPORTANTE: questo e' un protocollo NON ufficiale, documentato dalla
community (es. progetti come ha-bambulab, OpenBambuAPI). Bambu Lab non
pubblica uno schema garantito e i nomi dei campi possono cambiare con
gli aggiornamenti firmware. Per questo motivo ogni campo viene letto in
modo "defensivo" (.get con default), cosi' se un campo manca o cambia
nome il programma non si rompe: mostra semplicemente "N/D" per quel dato.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from translations import tr


SPEED_LABELS = {
    1: "Silenzioso",
    2: "Standard",
    3: "Sport",
    4: "Ludicrous",
}

# Mappa da dev_model_name (codice Bambu) a nome leggibile e capabilities.
# I codici sono quelli restituiti dall'API cloud nella lista stampanti.
# Fonte: community reverse engineering + wiki ufficiale Bambu Lab.
PRINTER_MODEL_NAMES = {
    # A Series
    "N1":       "A1 Mini",
    "N2S":      "A1",
    "N2":       "A1 (no AMS)",
    # P Series
    "C11":      "P1P",
    "C12":      "P1S",
    "C13":      "P2S",
    # X Series
    "BL-P001":  "X1C",
    "BL-P002":  "X1E",
    "X2D":      "X2D",
    # H Series
    "H2S":      "H2S",
    "H2D":      "H2D",
    "H2D-Pro":  "H2D Pro",
    "H2C":      "H2C (Vortek)",
}

# Modelli con due ugelli indipendenti (dual-nozzle).
# H2D, H2D Pro, X2D hanno due estrusori fisici.
# H2C ne ha fino a 7 via Vortek ma usa comunque nozzle_temper / nozzle_temper_2
# per gli ugelli sinistro e destro.
DUAL_NOZZLE_MODELS = {"H2D", "H2D-Pro", "X2D", "H2C"}

# Modelli con camera chiusa riscaldata (rilevante per visualizzare
# la temperatura camera come dato significativo, non solo ambientale).
HEATED_CHAMBER_MODELS = {"C12", "C13", "BL-P001", "BL-P002", "H2S", "H2D", "H2D-Pro", "H2C", "X2D"}

# Modelli con lidar integrato (calibrazioni lidar hanno senso da mostrare).
LIDAR_MODELS = {"BL-P001", "BL-P002"}

# Modelli con supporto modulo laser.
LASER_MODELS = {"H2D", "H2D-Pro", "H2C"}

def model_display_name(dev_model_name: str) -> str:
    """Restituisce il nome leggibile del modello dal codice interno Bambu."""
    return PRINTER_MODEL_NAMES.get(dev_model_name, dev_model_name or "Sconosciuto")


STATE_LABELS = {
    "IDLE":    "In attesa",
    "RUNNING": "In stampa",
    "PAUSE":   "In pausa",
    "FINISH":  "Completata",
    "FAILED":  "Errore",
    "PREPARE": "Preparazione",
    "SLICING": "Slicing",
}

SUB_STAGE_LABELS = {
    # Diciture ufficiali di Bambu Connect, tradotte in italiano.
    1:  "Livellamento piatto",
    2:  "Preriscaldo piatto",
    3:  "Compensazione vibrazione",
    4:  "Cambio filamento",
    5:  "Pausa M400",
    6:  "In pausa: filamento esaurito",
    7:  "Riscaldamento ugello",
    8:  "Calibrazione estrusione",
    9:  "Scansione superficie piatto",
    10: "Ispezione primo layer",
    11: "Identificazione tipo di piatto",
    12: "Calibrazione Micro Lidar",
    13: "Homing testina",
    14: "Pulizia ugello",
    15: "Controllo temperatura estrusore",
    16: "In pausa: intervento utente",
    17: "In pausa: copertura anteriore aperta",
    18: "Calibrazione Micro Lidar",
    19: "Calibrazione flusso estrusione",
    20: "In pausa: malfunzionamento temperatura ugello",
    21: "In pausa: malfunzionamento temperatura piatto",
}

# Fasi operative dell'AMS ricavate dal codice di Bambu Connect.
# Il campo ams_status è un intero a 16 bit: byte alto = fase, byte basso = step.
# Le fasi principali:
#   0x00XX = Idle/nessuna operazione
#   0x01XX = Pausa operazione AMS
#   0x02XX = Operazione in corso (XX = step)
#   0x04XX = Filament change (XX = step)
# Mappa ufficiale degli stati AMS estratta dal codice JavaScript di Bambu Connect.
#
# ams_status è un intero a 16 bit:
#   major = (value >> 8) & 0xFF   ← categoria dell'operazione
#   minor = value & 0xFF          ← passo specifico dentro la categoria
#
# major values (enum sN dal sorgente Bambu Connect):
#   0=idle, 1=filamentChanging, 2=rfidIdentify, 3=assist, 4=calibration
#   16=selfTest, 32=debug
#
# minor values per major=1 (filamentChanging), enum i0:
#   0=idle/preload, 2=hotendHeating, 3=cutFilament, 4=pullback
#   5=push, 6=occlusion, 7=purge, 8=checkFilamentLoc

def ams_status_label(ams_status: Optional[int]) -> str:
    """Converte ams_status nella descrizione testuale mostrata da Bambu Connect.
    Logica estratta direttamente dal codice JS di Bambu Connect (router-*.js):
    major = (value >> 8) & 0xFF,  minor = value & 0xFF."""
    if ams_status is None or ams_status == 0:
        return ""
    major = (ams_status >> 8) & 0xFF
    minor = ams_status & 0xFF

    if major == 0:
        return ""

    if major == 1:  # filamentChanging
        _steps = {
            0: "",
            1: tr("ams_preload"),
            2: tr("ams_heat"),
            3: tr("ams_cut"),
            4: tr("ams_pullback"),
            5: tr("ams_push"),
            6: tr("ams_occlusion"),
            7: tr("ams_purge"),
            8: tr("ams_check_loc"),
        }
        return _steps.get(minor, tr("ams_step_n").format(minor))

    if major == 2:  # rfidIdentify
        return tr("ams_rfid")

    if major == 3:  # assist — stato interno continuo, non significativo da mostrare
        return ""

    if major == 4:  # calibration
        if minor == 0:
            return tr("ams_calib_pipe")
        if minor == 1:
            return tr("ams_calib_multi")
        return tr("ams_calib")

    if major == 16:  # selfTest
        return tr("ams_selftest")

    if major == 32:  # debug
        return ""

    return ""


@dataclass
class AmsTray:
    slot_id: str
    material: str = "N/D"
    color_hex: str = "#999999"
    is_empty: bool = True
    state: int = 0  # valore raw dal firmware; bit 4 (=16) = slot attivo (rilevato su P2S)


@dataclass
class AmsUnit:
    unit_id: str
    humidity: Optional[int] = None       # percentuale reale (humidity_raw)
    temperature: Optional[float] = None
    trays: list[AmsTray] = field(default_factory=list)
    is_external: bool = False            # True per unità con id >= 128 (AMS HT, essiccatori)
    dry_temp: Optional[float] = None    # temperatura essiccazione attiva
    dry_time: Optional[int] = None      # minuti rimanenti essiccazione


@dataclass
class PrinterStatus:
    dev_id: str
    name: str = ""
    model: str = ""

    online: bool = False
    raw_state: str = "IDLE"

    progress_percent: Optional[int] = None
    remaining_minutes: Optional[int] = None
    current_layer: Optional[int] = None
    total_layers: Optional[int] = None
    task_name: str = ""

    nozzle_temp: Optional[float] = None
    nozzle_target: Optional[float] = None
    bed_temp: Optional[float] = None
    bed_target: Optional[float] = None
    cooling_fan_percent: Optional[int] = None
    aux_fan_percent: Optional[int] = None

    chamber_temp: Optional[float] = None
    print_speed: Optional[int] = None       # 1=Silenzioso 2=Standard 3=Sport 4=Ludicrous
    nozzle_diameter: Optional[str] = None   # es. "0.4"
    nozzle_type: Optional[str] = None       # "hardened_steel", "stainless_steel", ecc.
    nozzle2_temp: Optional[float] = None    # secondo ugello (H2D, X2D, H2C) - None su single-nozzle
    nozzle2_target: Optional[float] = None
    nozzle2_diameter: Optional[str] = None  # diametro ugello sinistro/secondo
    nozzle2_type: Optional[str] = None      # tipo ugello sinistro/secondo
    print_weight: Optional[float] = None    # grammi stimati (mc_print_weight)
    wifi_signal: Optional[str] = None       # es. "-55dBm"
    chamber_light_on: Optional[bool] = None
    sd_free_kb: Optional[int] = None
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    pos_z: Optional[float] = None
    chamber_fan_percent: Optional[int] = None
    heatbreak_fan_percent: Optional[int] = None  # ventola heatbreak (presente nel log A1)

    ams_units: list[AmsUnit] = field(default_factory=list)
    ams_tray_now: Optional[int] = None
    ams_external_active: bool = False
    vt_tray: Optional[AmsTray] = None
    ams_status: Optional[int] = None        # stato operativo AMS (vedi ams_status_label)

    print_sub_stage: Optional[int] = None  # sotto-stato durante la stampa

    plate_preview_b64: Optional[str] = None

    last_error: Optional[str] = None

    @property
    def state_label(self) -> str:
        _map = {
            "IDLE":    tr("state_idle"),
            "RUNNING": tr("state_running"),
            "PAUSE":   tr("state_pause"),
            "FINISH":  tr("state_finish"),
            "FAILED":  tr("state_failed"),
            "PREPARE": tr("state_prepare"),
            "SLICING": tr("state_slicing"),
        }
        return _map.get(self.raw_state, self.raw_state or tr("state_unknown"))

    @property
    def model_display_name(self) -> str:
        """Nome leggibile del modello (es. 'A1', 'P1S', 'H2D')."""
        return model_display_name(self.model)

    @property
    def is_dual_nozzle(self) -> bool:
        """True su H2D, H2D Pro, X2D, H2C — hanno due ugelli fisici indipendenti."""
        return self.model in DUAL_NOZZLE_MODELS

    @property
    def has_heated_chamber(self) -> bool:
        """True su modelli con camera chiusa riscaldata (P1S, X1C, H2D, ecc.)"""
        return self.model in HEATED_CHAMBER_MODELS

    @property
    def has_lidar(self) -> bool:
        """True su X1C e X1E che hanno il Micro Lidar integrato."""
        return self.model in LIDAR_MODELS

    @property
    def has_vortek(self) -> bool:
        """True su H2C che usa il sistema Vortek con fino a 7 ugelli intercambiabili."""
        return self.model == "H2C"

    @property
    def speed_label(self) -> str:
        if self.print_speed is None:
            return ""
        _speed_map = {
            1: tr("speed_silent"),
            2: tr("speed_standard"),
            3: tr("speed_sport"),
            4: tr("speed_ludicrous"),
        }
        return _speed_map.get(self.print_speed, f"Speed {self.print_speed}")

    @property
    def sub_stage_label(self) -> str:
        if self.print_sub_stage is None or self.print_sub_stage in (0, 255):
            return ""
        if self.raw_state not in ("RUNNING", "PREPARE"):
            return ""
        if self.print_sub_stage in (1, 2):
            layer = self.current_layer or 0
            if layer >= 1:
                return ""
        _stage_map = {
            1:  tr("stg_bed_level"),
            2:  tr("stg_bed_preheat"),
            3:  tr("stg_vibration"),
            4:  tr("stg_filament"),
            5:  tr("stg_m400"),
            6:  tr("stg_runout"),
            7:  tr("stg_hotend"),
            8:  tr("stg_extrusion"),
            9:  tr("stg_scan"),
            10: tr("stg_first_layer"),
            11: tr("stg_plate_type"),
            12: tr("stg_lidar"),
            13: tr("stg_homing"),
            14: tr("stg_clean"),
            15: tr("stg_temp_check"),
            16: tr("stg_user_pause"),
            17: tr("stg_door"),
            19: tr("stg_flow"),
            20: tr("stg_nozzle_fail"),
            21: tr("stg_bed_fail"),
        }
        return _stage_map.get(self.print_sub_stage, f"Stage {self.print_sub_stage}")

    @property
    def estimated_finish_time(self) -> Optional[datetime]:
        if self.remaining_minutes is None:
            return None
        return datetime.now() + timedelta(minutes=self.remaining_minutes)

    @classmethod
    def from_mqtt_payload(cls, dev_id: str, name: str, payload: dict, model: str = "") -> "PrinterStatus":
        """Crea/aggiorna uno stato a partire da un messaggio 'report' MQTT.

        Il messaggio reale ha tipicamente la forma:
        {"print": {"gcode_state": "RUNNING", "mc_percent": 42, ...}}
        """
        status = cls(dev_id=dev_id, name=name, model=model, online=True)
        p = payload.get("print", payload)  # alcuni firmware annidano sotto "print"

        status.raw_state = p.get("gcode_state", status.raw_state)
        status.progress_percent = _safe_int(p.get("mc_percent"))
        status.remaining_minutes = _safe_int(p.get("mc_remaining_time"))
        status.current_layer = _safe_int(p.get("layer_num"))
        status.total_layers = _safe_int(p.get("total_layer_num"))
        status.task_name = p.get("subtask_name") or p.get("gcode_file") or ""

        status.nozzle_temp = _safe_float(p.get("nozzle_temper"))
        status.nozzle_target = _safe_float(p.get("nozzle_target_temper"))
        status.bed_temp = _safe_float(p.get("bed_temper"))
        status.bed_target = _safe_float(p.get("bed_target_temper"))
        status.cooling_fan_percent = _fan_to_percent(p.get("cooling_fan_speed"))
        status.aux_fan_percent = _fan_to_percent(p.get("big_fan1_speed"))
        status.chamber_fan_percent = _fan_to_percent(p.get("big_fan2_speed"))
        status.heatbreak_fan_percent = _fan_to_percent(p.get("heatbreak_fan_speed"))
        status.chamber_temp = _safe_float(p.get("chamber_temper"))
        status.print_speed = _safe_int(p.get("spd_lvl") or p.get("printing_speed"))
        status.nozzle_diameter = p.get("nozzle_diameter") or None
        status.nozzle_type = p.get("nozzle_type") or None
        status.print_weight = _safe_float(p.get("mc_print_weight"))
        # Secondo ugello: presente su H2D, H2D Pro, X2D, H2C.
        # Il nome esatto del campo varia col firmware; proviamo tutte le
        # varianti note dalla community. Su stampanti single-nozzle questi
        # campi non esistono → restano None (nessun crash, nessuna visualizzazione).
        status.nozzle2_temp = _safe_float(
            p.get("nozzle_temper_2")      # variante più comune (H2D firmware)
            or p.get("nozzle2_temper")    # variante alternativa
            or p.get("left_nozzle_temper") # H2C: ugello sinistro fisso
        )
        status.nozzle2_target = _safe_float(
            p.get("nozzle_target_temper_2")
            or p.get("nozzle2_target_temper")
            or p.get("left_nozzle_target_temper")
        )
        # Diametro e tipo ugello destro (H2D/H2C hanno due ugelli distinti)
        status.nozzle2_diameter = p.get("nozzle_diameter_2") or p.get("left_nozzle_diameter") or None
        status.nozzle2_type = p.get("nozzle_type_2") or p.get("left_nozzle_type") or None

        ams_raw = p.get("ams")
        status.ams_units = _parse_ams(ams_raw)
        # Cerca ams_tray_now (vassoio attivo) prima dentro il blocco ams, poi al livello root
        tray_now_raw = None
        if isinstance(ams_raw, dict):
            tray_now_raw = ams_raw.get("tray_now")
        if tray_now_raw is None:
            tray_now_raw = p.get("tray_now")
        
        tray_now_val = _safe_int(tray_now_raw)
        if tray_now_val is not None:
            if tray_now_val == 254:
                status.ams_external_active = True
                status.ams_tray_now = None
            elif tray_now_val == 255:
                status.ams_external_active = False
                status.ams_tray_now = None
            else:
                status.ams_external_active = False
                status.ams_tray_now = tray_now_val
        else:
            # Fallback se non stampiamo o il valore non è fornito
            status.ams_external_active = False
            status.ams_tray_now = None

        # vt_tray (bobina esterna / virtual tray): su alcuni firmware è al livello root, su altri dentro ams
        vt_raw = p.get("vt_tray") or p.get("tray")
        if not isinstance(vt_raw, dict) and isinstance(ams_raw, dict):
            vt_raw = ams_raw.get("vt_tray") or ams_raw.get("tray")
        if isinstance(vt_raw, dict):
            vt_color = (vt_raw.get("tray_color") or "999999FF")[:6] or "999999"
            vt_material = vt_raw.get("tray_type") or ""
            status.vt_tray = AmsTray(
                slot_id="vt",
                material=vt_material,
                color_hex=f"#{vt_color}",
                is_empty=not bool(vt_material),
            )

        # stg_cur è il campo che usa Bambu Connect per mostrare la fase corrente
        stg_cur = _safe_int(p.get("stg_cur"))
        mc_sub = _safe_int(p.get("mc_print_sub_stage"))
        status.print_sub_stage = stg_cur if stg_cur is not None else mc_sub

        # ams_status: stato operativo dell'AMS (cambio filamento, carico, scarico, ecc.)
        # Presente nel payload solo quando l'AMS sta facendo qualcosa
        status.ams_status = _safe_int(p.get("ams_status"))

        # Parsing dei nuovi campi avanzati
        status.wifi_signal = p.get("wifi_signal")
        
        # Luce camera
        lights = p.get("lights_report")
        if isinstance(lights, list):
            for l in lights:
                if l.get("node") == "chamber_light":
                    status.chamber_light_on = (l.get("mode") == "on")
        
        # Ventola camera (Chamber Fan)
        status.chamber_fan_percent = _fan_to_percent(p.get("big_fan2_speed"))
        
        # Dati dispositivo (SD, Coordinate)
        dev = p.get("device")
        if isinstance(dev, dict):
            # Spazio libero scheda SD (in MB/GB)
            cam_data = dev.get("cam") or dev.get("ipcam")
            if isinstance(cam_data, dict):
                status.sd_free_kb = _safe_int(cam_data.get("tl_external_free_kb"))
            # Coordinate spaziali estrusore
            tool = dev.get("toolhead")
            if isinstance(tool, dict):
                status.pos_x = _safe_float(tool.get("pos_x"))
                status.pos_y = _safe_float(tool.get("pos_y"))
                status.pos_z = _safe_float(tool.get("pos_z"))

        err = p.get("print_error")
        status.last_error = str(err) if err else None

        return status


def _safe_int(value) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_float(value) -> Optional[float]:
    try:
        if value is None:
            return None
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


def _fan_to_percent(value) -> Optional[int]:
    """La stampante riporta spesso le ventole su scala 0-15 (gcode fan speed).
    Le normalizziamo a 0-100% per la GUI."""
    raw = _safe_int(value)
    if raw is None:
        return None
    if raw <= 15:
        return round((raw / 15) * 100)
    return min(raw, 100)


def _parse_ams(ams_payload) -> list[AmsUnit]:
    units: list[AmsUnit] = []
    if not ams_payload:
        return units

    ams_list = ams_payload.get("ams") if isinstance(ams_payload, dict) else ams_payload
    if not ams_list:
        return units

    # Difesa contro messaggi MQTT parziali/malformati: a volte il campo
    # "ams" (normalmente una lista di unità, ognuna un dizionario) arriva
    # temporaneamente come qualcos'altro (es. una stringa di bitmask tipo
    # "ams_exist_bits") a causa di come la stampante invia aggiornamenti
    # parziali. Se non è una lista, la ignoriamo per questo messaggio
    # invece di andare in crash: il prossimo messaggio valido la
    # ripopolerà correttamente.
    if not isinstance(ams_list, list):
        return units

    for unit_raw in ams_list:
        if not isinstance(unit_raw, dict):
            continue
        unit_id = str(unit_raw.get("id", "?"))
        try:
            is_external = int(unit_id) >= 128
        except (ValueError, TypeError):
            is_external = False

        # humidity_raw = percentuale reale; humidity = livello 1-5 (fallback)
        humidity = _safe_int(unit_raw.get("humidity_raw")) or _safe_int(unit_raw.get("humidity"))

        dry_setting = unit_raw.get("dry_setting") or {}
        if not isinstance(dry_setting, dict):
            dry_setting = {}
        unit = AmsUnit(
            unit_id=unit_id,
            humidity=humidity,
            temperature=_safe_float(unit_raw.get("temp")),
            is_external=is_external,
            dry_temp=_safe_float(dry_setting.get("dry_temperature")) if dry_setting.get("dry_temperature", -1) != -1 else None,
            dry_time=_safe_int(unit_raw.get("dry_time")) if unit_raw.get("dry_time", 0) > 0 else None,
        )
        tray_list = unit_raw.get("tray", [])
        if not isinstance(tray_list, list):
            tray_list = []
        for tray_raw in tray_list:
            if not isinstance(tray_raw, dict):
                continue
            raw_color = tray_raw.get("tray_color") or "999999FF"
            color = (raw_color[:6] if isinstance(raw_color, str) else None) or "999999"
            material = tray_raw.get("tray_type") or ""
            unit.trays.append(
                AmsTray(
                    slot_id=str(tray_raw.get("id", "?")),
                    material=material,
                    color_hex=f"#{color}",
                    is_empty=not bool(material),
                    state=_safe_int(tray_raw.get("state")) or 0,
                )
            )
        units.append(unit)
    return units
