"""
bambu_cloud.py
Gestisce il login con l'account Bambu Lab (lo stesso usato in Bambu Handy)
e le chiamate REST necessarie per ottenere:
  - il token usato poi per autenticarsi sul broker MQTT cloud
  - la lista delle stampanti associate al tuo account
  - (best effort) l'immagine di anteprima del piatto del lavoro corrente

ATTENZIONE: questi endpoint NON sono documentati ufficialmente da Bambu Lab.
Sono stati ricavati dalla community (progetti open source come ha-bambulab)
osservando il traffico di Bambu Handy/Studio. Bambu Lab può cambiarli in
qualunque momento senza preavviso: se il login smette di funzionare, è
molto probabile che sia cambiato qualcosa qui, non un bug del resto del
programma. Questo file è isolato apposta, così se serve un fix in futuro
si tocca solo questo modulo.
"""
from __future__ import annotations

import base64
import json
import requests
from dataclasses import dataclass
from typing import Optional


REGION_HOSTS = {
    "us": "https://api.bambulab.com",
    "cn": "https://api.bambulab.cn",
}

REGION_MQTT_HOSTS = {
    "us": "us.mqtt.bambulab.com",
    "cn": "cn.mqtt.bambulab.com",
}


class BambuAuthError(Exception):
    """Errore di autenticazione (credenziali errate, 2FA richiesto, ecc.)."""


class BambuVerificationRequired(BambuAuthError):
    """Bambu richiede un codice di verifica inviato per email (2FA)."""


def decode_jwt_uid(token: str) -> Optional[str]:
    """Estrae lo user id ('uid') dal token JWT restituito dal login.

    Il login Bambu Lab NON restituisce un campo 'uid' separato nella
    risposta JSON: lo user id è incluso solo dentro al token stesso
    (come claim del JWT). Va quindi decodificato qui per poterlo usare
    come username MQTT ("u_<uid>"). Questa funzione non verifica la
    firma del token (non serve: lo stiamo solo leggendo, non validando),
    quindi non richiede librerie esterne.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_bytes)
        uid = payload.get("uid") or payload.get("user_id") or payload.get("sub")
        return str(uid) if uid is not None else None
    except Exception:
        return None


@dataclass
class LoginResult:
    access_token: str
    refresh_token: Optional[str]
    account_uid: Optional[str]


class BambuCloudClient:
    def __init__(self, region: str = "us"):
        self.region = region if region in REGION_HOSTS else "us"
        self.base_url = REGION_HOSTS[self.region]
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "BambuDashboard/1.0"})

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    def login_raw(self, email: str, password: str) -> dict:
        """Come login(), ma restituisce il dizionario JSON grezzo e completo
        restituito dal server, senza filtrare alcun campo. Utile in fase di
        diagnostica per scoprire nomi di campo non documentati."""
        resp = self.session.post(
            f"{self.base_url}/v1/user-service/user/login",
            json={"account": email, "password": password},
            timeout=15,
        )
        return self._parse_response(resp)

    def get_bound_printers_raw(self, access_token: str) -> dict:
        """Come get_bound_printers(), ma restituisce l'intero dizionario
        di risposta (non solo la lista 'devices'), per vedere se ci sono
        altri campi a livello root (es. un uid dell'account)."""
        resp = self.session.get(
            f"{self.base_url}/v1/iot-service/api/user/bind",
            headers=self._auth_headers(access_token),
            timeout=15,
        )
        return self._parse_response(resp)

    def try_candidate_info_endpoints(self, access_token: str) -> dict:
        """Prova alcuni endpoint 'candidati' (noti da progetti community
        come ha-bambulab) che potrebbero restituire l'uid dell'account.
        Ogni esito (successo o errore) viene riportato, nulla viene
        lanciato come eccezione: serve solo per la diagnostica."""
        candidates = [
            "/v1/user-service/my/info",
            "/v1/user-service/my/preference",
            "/v1/iot-service/api/user/info",
            "/v1/design-user-service/my/info",
        ]
        results = {}
        for path in candidates:
            try:
                resp = self.session.get(
                    f"{self.base_url}{path}",
                    headers=self._auth_headers(access_token),
                    timeout=10,
                )
                try:
                    body = resp.json()
                except ValueError:
                    body = resp.text[:200]
                results[path] = {"status": resp.status_code, "body": body}
            except Exception as exc:
                results[path] = {"status": "errore", "body": str(exc)}
        return results

    def get_account_uid(self, access_token: str) -> Optional[str]:
        """Ottiene lo uid del tuo account Bambu Lab, necessario come username
        per il broker MQTT cloud ("u_<uid>"). L'endpoint corretto (confermato
        da diversi progetti community, es. ha-bambulab e bambu-farm) è
        /v1/design-user-service/my/preference, che restituisce un campo 'uid'."""
        try:
            resp = self.session.get(
                f"{self.base_url}/v1/design-user-service/my/preference",
                headers=self._auth_headers(access_token),
                timeout=10,
            )
            data = self._parse_response(resp)
            uid = data.get("uid")
            return str(uid) if uid is not None else None
        except Exception:
            return None

    def login(self, email: str, password: str) -> LoginResult:
        """Primo step di login. Può richiedere un codice di verifica
        (BambuVerificationRequired) se l'account ha la 2FA via email."""
        data = self.login_raw(email, password)

        login_type = data.get("loginType")
        if login_type in ("verifyCode", "tfa"):
            raise BambuVerificationRequired(
                "Bambu Lab richiede un codice di verifica inviato per email."
            )

        token = data.get("accessToken")
        if not token:
            raise BambuAuthError(f"Login non riuscito: risposta inattesa {data}")

        uid = data.get("uid") or self.get_account_uid(token) or decode_jwt_uid(token)
        return LoginResult(
            access_token=token,
            refresh_token=data.get("refreshToken"),
            account_uid=str(uid) if uid else None,
        )

    def login_with_code(self, email: str, code: str) -> LoginResult:
        """Secondo step se l'account richiede un codice di verifica."""
        resp = self.session.post(
            f"{self.base_url}/v1/user-service/user/login",
            json={"account": email, "code": code, "loginType": "verifyCode"},
            timeout=15,
        )
        data = self._parse_response(resp)
        token = data.get("accessToken")
        if not token:
            raise BambuAuthError(f"Verifica codice non riuscita: {data}")

        uid = data.get("uid") or self.get_account_uid(token) or decode_jwt_uid(token)
        return LoginResult(
            access_token=token,
            refresh_token=data.get("refreshToken"),
            account_uid=str(uid) if uid else None,
        )

    def request_verification_code(self, email: str) -> None:
        self.session.post(
            f"{self.base_url}/v1/user-service/user/sendemail/code",
            json={"email": email, "type": "codeLogin"},
            timeout=15,
        )

    # ------------------------------------------------------------------
    # Stampanti associate all'account
    # ------------------------------------------------------------------
    def get_bound_printers(self, access_token: str) -> list[dict]:
        """Ritorna la lista di stampanti legate al tuo account Bambu.
        Ogni elemento contiene almeno 'dev_id', 'name', 'dev_model_name', 'online'."""
        resp = self.session.get(
            f"{self.base_url}/v1/iot-service/api/user/bind",
            headers=self._auth_headers(access_token),
            timeout=15,
        )
        data = self._parse_response(resp)
        return data.get("devices", [])

    # ------------------------------------------------------------------
    # Anteprima del piatto (best effort)
    # ------------------------------------------------------------------
    def get_current_task_cover_url(self, access_token: str, dev_id: str, task_name: Optional[str] = None) -> Optional[str]:
        """Cerca, tra le ultime attività dell'account, l'anteprima del lavoro
        attualmente associato a questa stampante. Ritorna None se non trovata."""
        try:
            resp = self.session.get(
                f"{self.base_url}/v1/user-service/my/tasks",
                params={"deviceId": dev_id, "limit": 20},
                headers=self._auth_headers(access_token),
                timeout=10,
            )
            data = self._parse_response(resp)
            hits = data.get("hits") or data.get("list") or []
            if not hits:
                return None

            def _extract_dev_id(h_dict):
                return str(h_dict.get("deviceId") or h_dict.get("dev_id") or h_dict.get("device_id") or h_dict.get("devId") or "")

            def _safe_int_val(v):
                try:
                    return int(v) if v is not None else 0
                except (ValueError, TypeError):
                    return 0

            # Filtra rigorosamente i task appartenenti a questa specifica stampante
            dev_hits = [h for h in hits if _extract_dev_id(h) == dev_id]
            if not dev_hits:
                dev_hits = hits

            # Ordina i task dal più recente al più vecchio (id decrescente)
            dev_hits.sort(key=lambda x: _safe_int_val(x.get("id")), reverse=True)

            def _clean_title(s):
                if not s:
                    return ""
                s = s.lower().replace(".gcode", "").replace(".3mf", "").replace("_", " ").replace("-", " ")
                import re
                return re.sub(r'[^\w\s]', '', s).strip()

            # 1. Priorità assoluta al task ATTUALMENTE IN STAMPA (status 1 = running, 4 = prepare)
            if task_name:
                tn_clean = _clean_title(task_name)
                tn_words = set(tn_clean.split())
                for h in dev_hits:
                    if h.get("status") in (1, 4):
                        title_raw = str(h.get("title") or h.get("subtaskName") or h.get("gcodeFileName") or h.get("modelName") or "")
                        h_clean = _clean_title(title_raw)
                        if h_clean and tn_clean and (h_clean in tn_clean or tn_clean in h_clean or len(set(h_clean.split()).intersection(tn_words)) > 0):
                            cover = h.get("cover")
                            if cover:
                                return cover

            for h in dev_hits:
                if h.get("status") in (1, 4):
                    cover = h.get("cover")
                    if cover:
                        return cover

            # 2. Corrispondenza per titolo o subtask su tutti i task recenti della stampante
            if task_name:
                tn_clean = _clean_title(task_name)
                tn_words = set(tn_clean.split())
                best_cover = None
                best_score = 0

                for h in dev_hits:
                    title_raw = str(h.get("title") or h.get("subtaskName") or h.get("gcodeFileName") or h.get("modelName") or "")
                    h_clean = _clean_title(title_raw)
                    h_words = set(h_clean.split())

                    if h_clean and tn_clean:
                        if h_clean in tn_clean or tn_clean in h_clean:
                            cover = h.get("cover")
                            if cover:
                                return cover
                        overlap = len(h_words.intersection(tn_words))
                        if overlap > best_score:
                            best_score = overlap
                            best_cover = h.get("cover")

                if best_cover and best_score > 0:
                    return best_cover

            # Se il lavoro è stato avviato dallo schermo della stampante (da SD card / memoria interna),
            # non esiste un task Cloud corrispondente. Non restituiamo le anteprime di vecchi task completati!
            return None
        except Exception:
            return None
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def mqtt_host(self) -> str:
        return REGION_MQTT_HOSTS[self.region]

    @staticmethod
    def _auth_headers(access_token: str) -> dict:
        return {"Authorization": f"Bearer {access_token}"}

    @staticmethod
    def _parse_response(resp: requests.Response) -> dict:
        try:
            data = resp.json()
        except ValueError:
            raise BambuAuthError(f"Risposta non valida dal server Bambu (HTTP {resp.status_code})")

        if resp.status_code >= 400:
            message = data.get("message") or data.get("error") or str(data)
            raise BambuAuthError(f"Bambu ha risposto con un errore: {message}")

        return data
