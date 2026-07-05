"""
translations.py
Sistema di traduzione per Bambu Dashboard.
Aggiungere qui tutte le stringhe visibili all'utente.
Per aggiungere una nuova lingua: aggiungere un blocco con lo stesso set di chiavi.
"""
from __future__ import annotations

# Lingua corrente (modificata da MainWindow al cambio lingua)
_current_lang: str = "it"


def set_language(lang: str) -> None:
    global _current_lang
    _current_lang = lang if lang in TRANSLATIONS else "it"


def get_language() -> str:
    return _current_lang


def tr(key: str) -> str:
    """Restituisce la stringa tradotta nella lingua corrente."""
    return TRANSLATIONS.get(_current_lang, TRANSLATIONS["it"]).get(key, key)


TRANSLATIONS: dict[str, dict[str, str]] = {
    # ── Italiano ──────────────────────────────────────────────────────────────
    "it": {
        # Toolbar
        "tb_login":        "Accedi",
        "tb_manage":       "Gestisci stampanti",
        "tb_refresh":      "Aggiorna stato",
        "tb_logout":       "Logout",
        "tb_autostart":    "Avvia con Windows",
        "tb_language":     "🌐 Lingua",
        "tray_show":       "Mostra Dashboard",
        "tray_exit":       "Esci dall'applicazione",

        # Dialogo selezione stampanti
        "pick_title":      "Scegli le stampanti da mostrare",
        "pick_label":      "Stampanti trovate sul tuo account Bambu Lab:",

        # Scheda Storico
        "tab_history":     "Storico",

        # Printer card — header
        "connected":       "Connessa",
        "disconnected":    "Disconnessa",
        "no_printer_cfg":  "Nessuna stampante configurata.\nUsa 'Gestisci stampanti' per aggiungerne una.",
        "no_job":          "Nessun lavoro in corso",
        "preview_none":    "Nessuna\nanteprima",

        # Printer card — temperature / ventole
        "nozzle":          "Ugello",
        "bed":             "Piatto",
        "chamber":         "Camera",
        "fan_cool":        "Cool",
        "fan_aux":         "Aux",
        "fan_cam":         "Cam",
        "light_on":        "Luce ON",
        "light_off":       "Luce OFF",

        # Printer card — progresso
        "layer":           "Layer",
        "finish":          "Fine",

        # Printer card — AMS
        "ams_not_found":   "AMS non rilevata",
        "external_spool":  "Bobina estern",
        "dryer":           "Essiccatore",

        # Printer card — controlli
        "pause":           "Pausa",
        "resume":          "Riprendi",
        "stop":            "Stop",
        "skip_label":      "Salta pezzo n.:",
        "skip_btn":        "Salta",
        "skip_note":       "Se rifiutato dalla stampante: serve il Developer Mode.",
        "confirm_stop":    "Confermi l'arresto?",
        "confirm_stop_q":  "Vuoi davvero interrompere la stampa su {name}?",

        # Stati stampante
        "state_idle":      "In attesa",
        "state_running":   "In stampa",
        "state_pause":     "In pausa",
        "state_finish":    "Completata",
        "state_failed":    "Errore",
        "state_prepare":   "Preparazione",
        "state_slicing":   "Slicing",
        "state_unknown":   "Sconosciuto",

        # Fasi di stampa (stg_cur)
        "stg_bed_level":   "Livellamento piatto",
        "stg_bed_preheat": "Preriscaldo piatto",
        "stg_vibration":   "Compensazione vibrazione",
        "stg_filament":    "Cambio filamento",
        "stg_m400":        "Pausa M400",
        "stg_runout":      "In pausa: filamento esaurito",
        "stg_hotend":      "Riscaldamento ugello",
        "stg_extrusion":   "Calibrazione estrusione",
        "stg_scan":        "Scansione superficie piatto",
        "stg_first_layer": "Ispezione primo layer",
        "stg_plate_type":  "Identificazione tipo di piatto",
        "stg_lidar":       "Calibrazione Micro Lidar",
        "stg_homing":      "Homing testina",
        "stg_clean":       "Pulizia ugello",
        "stg_temp_check":  "Controllo temperatura estrusore",
        "stg_user_pause":  "In pausa: intervento utente",
        "stg_door":        "In pausa: copertura anteriore aperta",
        "stg_flow":        "Calibrazione flusso estrusione",
        "stg_nozzle_fail": "In pausa: malfunzionamento temperatura ugello",
        "stg_bed_fail":    "In pausa: malfunzionamento temperatura piatto",

        # Fasi AMS (ams_status)
        "ams_preload":     "Cambio filamento: pre-carico",
        "ams_heat":        "Riscaldamento ugello",
        "ams_cut":         "Taglio filamento",
        "ams_pullback":    "Ritiro filamento corrente",
        "ams_push":        "Inserimento nuovo filamento",
        "ams_occlusion":   "Verifica estrusione",
        "ams_purge":       "Spurgo filamento precedente",
        "ams_check_loc":   "Verifica posizione filamento",
        "ams_step_n":      "Cambio filamento (step {})",
        "ams_rfid":        "Lettura RFID filamento",
        "ams_calib_pipe":  "Calibrazione AMS: tubo",
        "ams_calib_multi": "Calibrazione AMS: multi-unità",
        "ams_calib":       "Calibrazione AMS",
        "ams_selftest":    "AMS: autotest",

        # Velocità
        "speed_silent":    "Silenzioso",
        "speed_standard":  "Standard",
        "speed_sport":     "Sport",
        "speed_ludicrous": "Ludicrous",

        # Storico
        "hist_title":      "Storico stampe",
        "hist_total":      "Stampe totali:",
        "hist_completed":  "Completate:",
        "hist_failed":     "Fallite:",
        "hist_fil_label":  "Filamento",
        "hist_cost_spent": "Spesa",
        "hist_col_date":   "Data/Ora",
        "hist_col_printer":"Stampante",
        "hist_col_job":    "Nome Lavoro",
        "hist_col_dur":    "Durata",
        "hist_col_fil":    "Filamento",
        "hist_col_cost":   "Costo",
        "hist_col_state":  "Stato",
        "hist_completed_s":"Completata",
        "hist_failed_s":   "Fallita",
        "hist_cost_label": "Costo medio filamento al kg (€):",
        "hist_nd":         "N/D",
        "hist_export":     "Esporta CSV",
        "hist_clear":      "Azzera Storico",

        # Messaggi errore / stato
        "login_required":  "Devi prima accedere con il tuo account Bambu Lab.",
        "no_printers":     "Non risultano stampanti associate al tuo account.",
        "conn_incomplete": "Impossibile collegarsi alle stampanti: dati di accesso incompleti. Prova a rifare il login.",
        "autostart_on":    "Avvio automatico con Windows attivato.",
        "autostart_off":   "Avvio automatico con Windows disattivato.",

        # Notifiche
        "notif_started":   "Stampa avviata",
        "notif_done":      "Stampa completata ✓",
        "notif_failed":    "Errore stampa",
        "notif_failed_msg":"la stampa è fallita",
        "notif_done_msg":  "lavoro terminato",
    },

    # ── English ───────────────────────────────────────────────────────────────
    "en": {
        # Toolbar
        "tb_login":        "Login",
        "tb_manage":       "Manage printers",
        "tb_refresh":      "Refresh status",
        "tb_logout":       "Logout",
        "tb_autostart":    "Start with Windows",
        "tb_language":     "🌐 Language",
        "tray_show":       "Show Dashboard",
        "tray_exit":       "Quit application",

        # Printer picker dialog
        "pick_title":      "Choose printers to display",
        "pick_label":      "Printers found on your Bambu Lab account:",

        # History tab
        "tab_history":     "History",

        # Printer card — header
        "connected":       "Connected",
        "disconnected":    "Disconnected",
        "no_printer_cfg":  "No printer configured.\nUse 'Manage printers' to add one.",
        "no_job":          "No job in progress",
        "preview_none":    "No\npreview",

        # Printer card — temperatures / fans
        "nozzle":          "Nozzle",
        "bed":             "Bed",
        "chamber":         "Chamber",
        "fan_cool":        "Cool",
        "fan_aux":         "Aux",
        "fan_cam":         "Cam",
        "light_on":        "Light ON",
        "light_off":       "Light OFF",

        # Printer card — progress
        "layer":           "Layer",
        "finish":          "End",

        # Printer card — AMS
        "ams_not_found":   "No AMS detected",
        "external_spool":  "External spool",
        "dryer":           "Dryer",

        # Printer card — controls
        "pause":           "Pause",
        "resume":          "Resume",
        "stop":            "Stop",
        "skip_label":      "Skip object n.:",
        "skip_btn":        "Skip",
        "skip_note":       "If rejected by printer: Developer Mode is required.",
        "confirm_stop":    "Confirm stop?",
        "confirm_stop_q":  "Do you really want to stop the print on {name}?",

        # Printer states
        "state_idle":      "Idle",
        "state_running":   "Printing",
        "state_pause":     "Paused",
        "state_finish":    "Completed",
        "state_failed":    "Error",
        "state_prepare":   "Preparing",
        "state_slicing":   "Slicing",
        "state_unknown":   "Unknown",

        # Print stages (stg_cur)
        "stg_bed_level":   "Bed leveling",
        "stg_bed_preheat": "Heatbed preheating",
        "stg_vibration":   "Vibration compensation",
        "stg_filament":    "Changing filament",
        "stg_m400":        "M400 pause",
        "stg_runout":      "Paused: filament runout",
        "stg_hotend":      "Heating nozzle",
        "stg_extrusion":   "Calibrating extrusion",
        "stg_scan":        "Scanning bed surface",
        "stg_first_layer": "Inspecting first layer",
        "stg_plate_type":  "Identifying build plate type",
        "stg_lidar":       "Calibrating Micro Lidar",
        "stg_homing":      "Homing toolhead",
        "stg_clean":       "Cleaning nozzle tip",
        "stg_temp_check":  "Checking extruder temperature",
        "stg_user_pause":  "Paused: user intervention",
        "stg_door":        "Paused: front cover open",
        "stg_flow":        "Calibrating extrusion flow",
        "stg_nozzle_fail": "Paused: nozzle temperature malfunction",
        "stg_bed_fail":    "Paused: bed temperature malfunction",

        # AMS stages (ams_status)
        "ams_preload":     "Filament change: pre-load",
        "ams_heat":        "Heating nozzle",
        "ams_cut":         "Cutting filament",
        "ams_pullback":    "Pulling back current filament",
        "ams_push":        "Pushing new filament",
        "ams_occlusion":   "Checking filament extrusion",
        "ams_purge":       "Purging old filament",
        "ams_check_loc":   "Checking filament location",
        "ams_step_n":      "Changing filament (step {})",
        "ams_rfid":        "Reading filament RFID",
        "ams_calib_pipe":  "AMS calibration: pipe",
        "ams_calib_multi": "AMS calibration: multi-unit",
        "ams_calib":       "AMS calibration",
        "ams_selftest":    "AMS self-test",

        # Speed
        "speed_silent":    "Silent",
        "speed_standard":  "Standard",
        "speed_sport":     "Sport",
        "speed_ludicrous": "Ludicrous",

        # History
        "hist_title":      "Print history",
        "hist_total":      "Total prints:",
        "hist_completed":  "Completed:",
        "hist_failed":     "Failed:",
        "hist_fil_label":  "Filament",
        "hist_cost_spent": "Cost",
        "hist_col_date":   "Date/Time",
        "hist_col_printer":"Printer",
        "hist_col_job":    "Job name",
        "hist_col_dur":    "Duration",
        "hist_col_fil":    "Filament",
        "hist_col_cost":   "Cost",
        "hist_col_state":  "Status",
        "hist_completed_s":"Completed",
        "hist_failed_s":   "Failed",
        "hist_cost_label": "Average filament cost per kg (€):",
        "hist_nd":         "N/A",
        "hist_export":     "Export CSV",
        "hist_clear":      "Clear History",

        # Error / status messages
        "login_required":  "You must first log in with your Bambu Lab account.",
        "no_printers":     "No printers found on your account.",
        "conn_incomplete": "Cannot connect to printers: incomplete credentials. Please log in again.",
        "autostart_on":    "Start with Windows enabled.",
        "autostart_off":   "Start with Windows disabled.",

        # Notifications
        "notif_started":   "Print started",
        "notif_done":      "Print completed ✓",
        "notif_failed":    "Print error",
        "notif_failed_msg":"the print has failed",
        "notif_done_msg":  "job finished",
    },
}
