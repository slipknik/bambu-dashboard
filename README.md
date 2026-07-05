# Bambu Dashboard personale

Una dashboard Windows personalizzata per le tue stampanti Bambu Lab (A1 +
una futura seconda stampante), con **solo** le informazioni che ti
servono davvero — senza passare da piattaforme terze come BambuHelper,
SimplyPrint, OctoEverywhere, ecc. Il programma parla direttamente con i
server ufficiali Bambu Lab (gli stessi di Bambu Handy) e con le tue
stampanti via MQTT.

## Cosa mostra

- Stato, progresso e tempo rimanente
- Temperature ugello/piatto e velocità ventole
- Stato AMS (materiali, colori, umidità)
- Ora stimata di fine stampa
- Anteprima del piatto in stampa (quando disponibile)
- Pulsante per saltare un pezzo durante la stampa (skip object)

## Installazione (Windows)

1. Installa **Python 3.10 o superiore** da [python.org](https://www.python.org/downloads/)
   (durante l'installazione spunta "Add Python to PATH").
2. Apri il **Prompt dei comandi** nella cartella del progetto ed esegui:

   ```
   pip install -r requirements.txt
   ```

3. Avvia il programma:

   ```
   python main.py
   ```

4. Al primo avvio ti verrà chiesto di accedere con il tuo **account Bambu
   Lab** (lo stesso di Bambu Handy). La password non viene mai salvata su
   disco: solo il token di sessione, in `%APPDATA%\BambuDashboard\config.json`.
5. Dopo il login, scegli quali stampanti dell'account mostrare. Quando
   acquisterai la seconda stampante, basterà associarla al tuo account
   Bambu (come fai normalmente con Bambu Handy) e poi cliccare
   "Gestisci stampanti" nella dashboard per aggiungerla.

## Personalizzazione

Le informazioni mostrate sono controllate da `config.py` →
`DEFAULT_WIDGETS` e salvate per ogni utente in `config.json` (chiave
`"widgets"`). Per nascondere una sezione che non ti interessa più, basta
impostarla su `false` nel file di configurazione, ad esempio:

```json
"widgets": {
  "progress": true,
  "temperatures": true,
  "ams": true,
  "finish_time": true,
  "skip_object": false,
  "plate_preview": true
}
```

## Nota importante sul comando "salta pezzo"

Dal 2025 Bambu Lab ha introdotto un sistema di verifica della firma per i
comandi di **controllo** (skip object, pausa via terze parti su firmware
recenti, movimento assi, temperature, AMS, calibrazioni). Le letture di
stato (tutto il resto della dashboard) non sono toccate da questa
restrizione e funzionano sempre.

Se premendo "Salta" vedi un errore tipo *"MQTT command verification
failed"* nella barra di stato della finestra, non è un bug di questo
programma: è il firmware della stampante che rifiuta comandi di
controllo non firmati da Bambu Studio/Handy. L'unico modo per renderlo
affidabile al 100% è attivare il **Developer Mode** sulla stampante
(menu LAN-only Mode), che però disattiva il collegamento al cloud Bambu
per quella stampante. È una scelta che puoi fare in futuro, in modo
indipendente dal resto della dashboard.

## Architettura del codice

- `bambu_cloud.py` — login e chiamate REST verso l'account Bambu
  (isolato apposta: se Bambu cambia gli endpoint, si aggiorna solo qui)
- `bambu_mqtt.py` — connessione MQTT per ricevere stato e inviare comandi
- `models.py` — interpretazione "defensiva" dei messaggi della stampante
  (se un campo cambia nome con un aggiornamento firmware, il programma
  non si rompe: mostra "N/D" per quel singolo dato)
- `config.py` — configurazione locale (stampanti, preferenze, token)
- `gui/` — interfaccia PySide6 (login, finestra principale, card per
  stampante)

## Estendere in futuro

Per aggiungere una nuova informazione alla dashboard:
1. Aggiungi il campo a `PrinterStatus` in `models.py` e leggilo dal
   payload MQTT in `from_mqtt_payload`.
2. Aggiungi una voce a `DEFAULT_WIDGETS` in `config.py`.
3. Aggiungi il relativo widget in `gui/printer_card.py`.

## Avvertenza

Il protocollo usato (login cloud + MQTT) non è documentato
ufficialmente da Bambu Lab ed è stato ricostruito dalla community.
Bambu Lab può modificarlo in qualsiasi momento; in tal caso potrebbe
essere necessario aggiornare `bambu_cloud.py` o `bambu_mqtt.py`.
