"""
bambu_mqtt.py
Gestisce la connessione MQTT verso il broker cloud di Bambu Lab per una
singola stampante: riceve i messaggi di stato (topic "device/<id>/report")
e può inviare comandi di controllo (topic "device/<id>/request").

Usiamo PySide6 Signal per passare i dati dal thread di rete di paho-mqtt
alla GUI in modo sicuro (mai toccare widget Qt da un thread diverso da
quello principale).
"""
from __future__ import annotations

import json
import ssl
import time
import uuid
from typing import Optional

import paho.mqtt.client as mqtt
from PySide6.QtCore import QObject, Signal

from models import PrinterStatus

MQTT_PORT = 8883


def deep_merge(base: dict, update: dict) -> dict:
    """Fonde 'update' dentro 'base', ricorsivamente per i dizionari annidati.

    Necessario perché la A1 (come tutta la serie P1) invia via MQTT solo i
    campi CAMBIATI rispetto al messaggio precedente, non lo stato completo
    ogni volta (a differenza della serie X1). Senza questo merge, ogni
    messaggio "parziale" farebbe sparire tutti i dati non presenti in quel
    singolo messaggio, dando l'effetto di dati incompleti e "a singhiozzo".
    """
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        elif isinstance(base.get(key), list) and not isinstance(value, (list, dict)):
            # Protezione: se abbiamo già una lista "buona" per questa chiave
            # e arriva un valore di tipo diverso (stringa/numero), lo
            # IGNORIAMO invece di sovrascrivere. Senza questa protezione,
            # un singolo messaggio malformato/parziale corromperebbe la
            # lista per sempre (i messaggi successivi erediterebbero il
            # dato sporco dal merge cumulativo), causando crash come 'str'
            # object has no attribute 'get' quando il codice si aspetta
            # dizionari al suo interno.
            pass
        else:
            base[key] = value
    return base


class PrinterConnection(QObject):
    status_updated = Signal(object)     # emette un PrinterStatus
    connection_changed = Signal(bool)   # True = connesso, False = disconnesso
    command_error = Signal(str)         # messaggio di errore leggibile

    def __init__(self, mqtt_host: str, account_uid: str, access_token: str,
                 dev_id: str, name: str, model: str = "", parent: Optional[QObject] = None):
        super().__init__(parent)
        self.mqtt_host = mqtt_host
        self.account_uid = account_uid
        self.access_token = access_token
        self.dev_id = dev_id
        self.name = name
        self.model = model

        self._report_topic = f"device/{dev_id}/report"
        self._request_topic = f"device/{dev_id}/request"

        # Stato cumulativo: la A1 invia spesso solo i campi cambiati, quindi
        # accumuliamo qui tutto quello che sappiamo finora su questa stampante.
        self._latest_print_state: dict = {}

        # "mc_print_sub_stage" segnala fasi transitorie (preriscaldo, calibrazioni,
        # cambio filamento). Il problema: a volte la stampante non manda mai un
        # messaggio esplicito che dica "fase finita, torno a 0" - quindi il merge
        # cumulativo sopra lascerebbe il valore bloccato per sempre. Per evitarlo,
        # teniamo traccia di QUANDO e A CHE LAYER è iniziata una fase speciale, e la
        # consideriamo automaticamente finita se: (a) il layer è avanzato da allora
        # (durante una fase speciale la stampa è ferma, quindi se il layer avanza la
        # fase è finita per certo), oppure (b) è passato troppo tempo (rete di sicurezza
        # nel caso il layer non cambi per altri motivi).
        self._sub_stage_baseline_layer: Optional[int] = None
        self._sub_stage_started_at: Optional[float] = None
        self._SUB_STAGE_TIMEOUT_SECONDS = 90
        self._ams_status_started_at: Optional[float] = None

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"bambu-dashboard-{uuid.uuid4().hex[:8]}",
        )
        self._client.username_pw_set(f"u_{account_uid}", access_token)
        self._client.tls_set(cert_reqs=ssl.CERT_NONE)  # come Bambu Handy/Studio
        self._client.tls_insecure_set(True)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    # ------------------------------------------------------------------
    def connect(self) -> None:
        self._client.connect_async(self.mqtt_host, MQTT_PORT, keepalive=30)
        self._client.loop_start()

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    # ------------------------------------------------------------------
    # Comandi di controllo
    # ------------------------------------------------------------------
    def request_full_status(self) -> None:
        self._publish({"pushing": {"sequence_id": self._seq(), "command": "pushall"}})

    def pause_print(self) -> None:
        self._publish({"print": {"sequence_id": self._seq(), "command": "pause"}})

    def resume_print(self) -> None:
        self._publish({"print": {"sequence_id": self._seq(), "command": "resume"}})

    def stop_print(self) -> None:
        self._publish({"print": {"sequence_id": self._seq(), "command": "stop"}})

    def skip_object(self, object_id: int) -> None:
        """Salta un singolo pezzo sul piatto durante la stampa.

        NOTA: questo è un comando di CONTROLLO. Sul firmware con il sistema
        di autorizzazione attivo, la stampante può rifiutarlo con l'errore
        "MQTT command verification failed" se non arriva da Bambu Studio/Handy
        firmati, a meno che il Developer Mode non sia attivo sulla stampante.
        Non è un bug di questo programma: è una restrizione imposta dal
        firmware Bambu Lab.
        """
        self._publish({
            "print": {
                "sequence_id": self._seq(),
                "command": "skip_objects",
                "obj_list": [object_id],
            }
        })

    def set_light(self, on: bool) -> None:
        self._publish({
            "system": {
                "sequence_id": self._seq(),
                "command": "ledctrl",
                "led_node": "chamber_light",
                "led_mode": "on" if on else "off",
            }
        })

    def pause_print(self) -> None:
        self._publish({
            "print": {
                "sequence_id": self._seq(),
                "command": "pause",
            }
        })

    def resume_print(self) -> None:
        self._publish({
            "print": {
                "sequence_id": self._seq(),
                "command": "resume",
            }
        })

    def stop_print(self) -> None:
        self._publish({
            "print": {
                "sequence_id": self._seq(),
                "command": "stop",
            }
        })

    def set_speed_level(self, level: int) -> None:
        # level: 1=Silent, 2=Standard, 3=Sport, 4=Ludicrous
        self._publish({
            "print": {
                "sequence_id": self._seq(),
                "command": "print_speed",
                "param": str(level),
            }
        })

    # ------------------------------------------------------------------
    def _publish(self, payload: dict) -> None:
        result = self._client.publish(self._request_topic, json.dumps(payload), qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            self.command_error.emit(
                f"Impossibile inviare il comando a {self.name}: errore MQTT {result.rc}"
            )

    @staticmethod
    def _seq() -> str:
        return str(uuid.uuid4().int % 100000)

    # ------------------------------------------------------------------
    # Callback paho-mqtt (eseguite sul thread di rete)
    # ------------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0 or str(reason_code) == "Success":
            client.subscribe(self._report_topic, qos=1)
            self.connection_changed.emit(True)
            self.request_full_status()
        else:
            self.connection_changed.emit(False)
            self.command_error.emit(
                f"Connessione MQTT a {self.name} fallita: {reason_code}"
            )

    def _on_disconnect(self, client, userdata, flags=None, reason_code=None, properties=None):
        self.connection_changed.emit(False)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return

        print_delta = payload.get("print")
        if not isinstance(print_delta, dict):
            if "command" in payload or "sequence_id" in payload:
                print_delta = payload

        if isinstance(print_delta, dict):
            if print_delta.get("result") == "fail" and print_delta.get("command"):
                self.command_error.emit(
                    f"{self.name}: comando '{print_delta['command']}' rifiutato dalla "
                    f"stampante (verifica se serve il Developer Mode)."
                )
            # Normalizzazione: a volte il firmware manda il campo "ams" del
            # messaggio come lista pura invece che come oggetto {"ams": [...],
            # "tray_now": ...}.
            if isinstance(print_delta.get("ams"), list):
                print_delta = dict(print_delta)
                print_delta["ams"] = {"ams": print_delta["ams"]}

            deep_merge(self._latest_print_state, print_delta)
            self._unstick_sub_stage()
            self._unstick_ams_status()

            # Log diagnostico: salvato DOPO il merge cosi' contiene lo stato
            # cumulativo reale. Si attiva al primo messaggio con gcode_state
            # (pushall completo), non ai messaggi parziali iniziali.
            if not hasattr(self, "_debug_logged") and "gcode_state" in self._latest_print_state:
                self._debug_logged = True
                try:
                    from config import get_config_dir
                    import datetime as _dt
                    log_dir = get_config_dir()
                    log_dir.mkdir(parents=True, exist_ok=True)
                    log_path = log_dir / f"mqtt_debug_{self.dev_id[-6:]}.json"
                    log_data = {
                        "_meta": {
                            "dev_id": self.dev_id,
                            "name": self.name,
                            "timestamp": _dt.datetime.now().isoformat(),
                            "note": "Stato cumulativo completo - utile per debug multi-modello"
                        },
                        **self._latest_print_state
                    }
                    log_path.write_text(
                        json.dumps(log_data, indent=2, ensure_ascii=False),
                        encoding="utf-8"
                    )
                except Exception:
                    pass

        if self._latest_print_state:
            status = PrinterStatus.from_mqtt_payload(
                self.dev_id, self.name, {"print": self._latest_print_state}, model=self.model
            )
            self.status_updated.emit(status)

    def _unstick_sub_stage(self) -> None:
        """Sblocca automaticamente 'mc_print_sub_stage' se è rimasto bloccato
        su una fase speciale (vedi commento nel costruttore)."""
        raw = self._latest_print_state.get("mc_print_sub_stage")
        try:
            sub_stage = int(raw) if raw is not None else None
        except (TypeError, ValueError):
            sub_stage = None

        raw_layer = self._latest_print_state.get("layer_num")
        try:
            layer = int(raw_layer) if raw_layer is not None else None
        except (TypeError, ValueError):
            layer = None

        if sub_stage in (None, 0):
            self._sub_stage_baseline_layer = None
            self._sub_stage_started_at = None
            return

        now = time.monotonic()
        if self._sub_stage_started_at is None:
            # Prima volta che vediamo questa fase speciale: salviamo il
            # layer e l'orario di riferimento.
            self._sub_stage_baseline_layer = layer
            self._sub_stage_started_at = now
            return

        # Se il layer è TORNATO INDIETRO rispetto al riferimento (es. da 25
        # a 0/1), vuol dire che è iniziato un lavoro NUOVO: il confronto
        # "è avanzato?" non funzionerebbe più (0 non è "più avanti" di 25).
        # Ripartiamo da un nuovo riferimento sul lavoro corrente, senza
        # cancellare forzatamente il valore: se è una fase reale del nuovo
        # lavoro resta visibile, altrimenti verrà comunque sbloccata dal
        # prossimo avanzamento di layer o dal timeout, ma misurati da qui.
        if (
            layer is not None
            and self._sub_stage_baseline_layer is not None
            and layer < self._sub_stage_baseline_layer
        ):
            self._sub_stage_baseline_layer = layer
            self._sub_stage_started_at = now
            return

        layer_advanced = (
            layer is not None
            and self._sub_stage_baseline_layer is not None
            and layer > self._sub_stage_baseline_layer
        )
        timed_out = (now - self._sub_stage_started_at) > self._SUB_STAGE_TIMEOUT_SECONDS

        if layer_advanced or timed_out:
            self._latest_print_state["mc_print_sub_stage"] = 0
            self._sub_stage_baseline_layer = None
            self._sub_stage_started_at = None

    def _unstick_ams_status(self) -> None:
        """Azzera ams_status se rimasto bloccato per più di 60 secondi.
        La lettura RFID e altre operazioni AMS durano pochi secondi:
        se ams_status != 0 per più di 60s è quasi certamente un valore
        residuo bloccato nel merge cumulativo."""
        ams_st = self._latest_print_state.get("ams_status")
        try:
            ams_st_val = int(ams_st) if ams_st is not None else 0
        except (TypeError, ValueError):
            ams_st_val = 0

        now = time.monotonic()
        if ams_st_val != 0:
            if self._ams_status_started_at is None:
                self._ams_status_started_at = now
            elif (now - self._ams_status_started_at) > 60:
                self._latest_print_state["ams_status"] = 0
                self._ams_status_started_at = None
        else:
            self._ams_status_started_at = None
