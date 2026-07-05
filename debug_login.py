"""
debug_login.py
Script diagnostico USA E GETTA. Fa login con il tuo account Bambu e
stampa la STRUTTURA (nomi dei campi, tipi, lunghezze) delle risposte
del server, senza mai mostrare il valore di token o password.

Eseguilo con: python debug_login.py
Poi copia e incollami tutto l'output: è sicuro da condividere, non
contiene il token vero né la password (solo lunghezze e nomi di campo).
"""
from __future__ import annotations

import getpass
import json

from bambu_cloud import BambuCloudClient, BambuAuthError


def redact(value, _depth=0):
    """Sostituisce valori 'lunghi' (probabili token/segreti) con un
    segnaposto che mostra solo lunghezza e quanti punti contiene
    (utile per capire se è un JWT, che ha 2 punti)."""
    if _depth > 4:
        return "<troppo annidato>"
    if isinstance(value, dict):
        return {k: redact(v, _depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, _depth + 1) for v in value[:3]] + (
            [f"... e altri {len(value) - 3}"] if len(value) > 3 else []
        )
    if isinstance(value, str):
        if len(value) > 40:
            return f"<stringa lunga: {len(value)} caratteri, {value.count('.')} punti>"
        return value
    return value


def main() -> None:
    print("=== Diagnostica login Bambu Lab ===")
    region = input("Regione account (us/cn) [us]: ").strip() or "us"
    email = input("Email Bambu Lab: ").strip()
    password = getpass.getpass("Password (non verrà mostrata): ")

    client = BambuCloudClient(region=region)

    try:
        raw_login = client.login_raw(email, password)
    except BambuAuthError as exc:
        print(f"\nLOGIN FALLITO: {exc}")
        return

    if raw_login.get("loginType") in ("verifyCode", "tfa"):
        try:
            client.request_verification_code(email)
        except Exception:
            pass
        code = input("Bambu ha inviato un codice via email. Inseriscilo qui: ").strip()
        resp = client.session.post(
            f"{client.base_url}/v1/user-service/user/login",
            json={"account": email, "code": code},
            timeout=15,
        )
        try:
            raw_login = resp.json()
        except ValueError:
            raw_login = {"errore": "risposta non JSON"}

    print("\n--- Risposta GREZZA E COMPLETA del login (valori lunghi censurati) ---")
    print(json.dumps(redact(raw_login), indent=2, ensure_ascii=False))

    access_token = raw_login.get("accessToken")
    if not access_token:
        print("\nNessun accessToken trovato nella risposta. Mi fermo qui.")
        return

    print("\n--- Risposta GREZZA E COMPLETA della lista stampanti ---")
    try:
        raw_bind = client.get_bound_printers_raw(access_token)
        print(json.dumps(redact(raw_bind), indent=2, ensure_ascii=False))
    except BambuAuthError as exc:
        print(f"Errore nel recuperare le stampanti: {exc}")

    print("\n--- Tentativo di endpoint candidati per trovare lo uid ---")
    candidate_results = client.try_candidate_info_endpoints(access_token)
    for path, outcome in candidate_results.items():
        print(f"\n{path} -> status {outcome['status']}")
        print(json.dumps(redact(outcome["body"]), indent=2, ensure_ascii=False)[:1500])

    print("\n=== Fine diagnostica: copia e incolla tutto questo output ===")


if __name__ == "__main__":
    main()
