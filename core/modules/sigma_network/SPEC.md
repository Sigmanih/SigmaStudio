# Sigma Network — Specifica di Implementazione

Modulo `sigma_network`. Rete peer-to-peer che permette a un'istanza di Sigma
Studio di usare gli agenti e i modelli di un'altra istanza, con contabilità in
**AiloCoin**: chi mette a disposizione il proprio PC per fare inferenza agli
altri guadagna monete, chi consuma inferenza altrui le spende.

> Modulo distinto da `sigma_network_lab` (Network Explorer & Web Research), che
> resta invariato. Nessun file di `sigma_network_lab` va toccato.

---

## 1. Decisioni architetturali (non negoziabili)

**Trasporto.** Ogni istanza di Sigma Studio espone gia un server FastAPI. Il
peering e HTTP diretto fra queste istanze: nessuna libreria P2P, nessun relay.
Un peer e semplicemente `http://host:porta` che risponde su `/api/sigma_network/*`.

**Identita.** Ogni peer genera alla prima esecuzione una coppia di chiavi
Ed25519, salvata in `data/sigma_network/identity.json` con permessi ristretti.
Il `peer_id` e l'hex dei primi 16 byte dello SHA-256 della chiave pubblica.
La chiave privata non lascia mai il disco e non compare in nessuna risposta API.

**Scoperta.** Due vie, entrambe necessarie:
- broadcast UDP sulla porta `47777` con un annuncio JSON ogni 15 secondi;
- aggiunta manuale di un peer per `host:porta`.
Un peer scoperto non e automaticamente attendibile: entra in stato `discovered`
e serve un'azione esplicita dell'utente per passare a `trusted`.

**Contabilita.** AiloCoin e per ora un registro locale di ricevute firmate, non
una blockchain. Il provider emette una ricevuta firmata per il lavoro svolto, il
consumer la controfirma, entrambi la conservano. Il saldo e la somma delle
ricevute valide. Questo registro e progettato per essere regolato in seguito
sulla crypto AiloNetwork: ogni ricevuta ha percio un campo `settlement_ref`
inizialmente `null`.

**Tariffa.** `1 AiloCoin = 1000 token generati`, configurabile. Il costo si
calcola sui token realmente prodotti, non su quelli richiesti.

**Sicurezza — requisiti vincolanti.**
- Ogni richiesta entrante e firmata dal peer chiamante e la firma va verificata
  contro la chiave pubblica registrata. Firma non valida: `401`.
- Nessuna esecuzione di codice arbitrario. Il provider espone SOLO generazione
  di testo. Mai `terminal`, mai accesso al filesystem, mai i tool del Developer
  Studio.
- Limiti applicati lato provider e non negoziabili dal chiamante:
  `max_tokens <= 4096`, `max 3 richieste concorrenti per peer`,
  `max 60 richieste/ora per peer`.
- Il provider serve solo peer in stato `trusted`.
- Nessun segreto nei log: mai chiavi private, mai prompt completi a livello INFO.
- Timeout di 120 s su ogni chiamata uscente verso un peer.

---

## 2. File da creare

### Backend — `core/modules/sigma_network/`

| File | Responsabilita |
|---|---|
| `__init__.py` | esporta `router` e `register_mcp` |
| `manifest.json` | metadati modulo (schema sotto) |
| `identity.py` | generazione/caricamento chiavi, firma, verifica |
| `peer_registry.py` | peer noti, stato, capacita, heartbeat; persistenza JSON |
| `discovery.py` | broadcast e ascolto UDP, thread daemon avviabile/fermabile |
| `ailocoin.py` | ricevute firmate, saldo, storico transazioni |
| `provider.py` | serve richieste di inferenza in arrivo, applica i limiti |
| `inference_broker.py` | instrada una richiesta verso un peer e ne riceve lo stream |
| `handlers.py` | route FastAPI |
| `network_server.py` | server MCP che espone l'inferenza remota come tool |
| `requirements.txt` | `cryptography>=42` |

### Frontend — `sigma_studio/src/modules/sigma_network/`

| File | Responsabilita |
|---|---|
| `index.jsx` | `export { default } from './SigmaNetwork.jsx'` |
| `SigmaNetwork.jsx` | tab principale, navigazione fra i pannelli |
| `PeerList.jsx` | peer scoperti e fidati, stato, latenza, azioni |
| `WalletPanel.jsx` | saldo AiloCoin, storico ricevute, grafico guadagni |
| `ShareSettings.jsx` | cosa condivido, tariffa, limiti, interruttore generale |
| `RemoteInferencePanel.jsx` | prova un peer: prompt, modello, risposta in streaming |
| `styles/sigma-network.css` | stili del modulo |

### Test — `tests/test_sigma_network.py`

---

## 3. Contratti API

Prefisso: `/api/sigma_network`.

### Locali (usate dalla UI)

```
GET  /identity          -> {peer_id, public_key, name, version}
GET  /peers             -> {peers: [Peer]}
POST /peers/add         {host, port}            -> {peer: Peer}
POST /peers/trust       {peer_id, trusted: bool} -> {peer: Peer}
DELETE /peers/{peer_id}                          -> {removed: bool}
GET  /wallet            -> {balance, earned, spent, receipts: [Receipt]}
GET  /settings          -> Settings
POST /settings          Settings                 -> Settings
POST /discovery/start                            -> {running: true}
POST /discovery/stop                             -> {running: false}
POST /inference/remote  {peer_id, prompt, model, max_tokens} -> SSE
```

### Peer-to-peer (esposte agli altri peer, tutte firmate)

```
GET  /p2p/hello         -> {peer_id, name, version, models: [...], accepting: bool}
POST /p2p/infer         {request_id, prompt, model, max_tokens, signature} -> SSE
POST /p2p/receipt       Receipt                  -> {countersigned: Receipt}
```

### Forme dei dati

```jsonc
// Peer
{
  "peer_id": "a1b2c3...",
  "name": "Workstation di Riccardo",
  "host": "192.168.1.40",
  "port": 8000,
  "public_key": "base64...",
  "state": "discovered" | "trusted" | "blocked",
  "models": ["Qwen/Qwen3.8-27B-GGUF-Q4_K_S"],
  "accepting": true,
  "last_seen": 1788042809.0,
  "latency_ms": 42
}

// Receipt
{
  "receipt_id": "uuid",
  "request_id": "uuid",
  "provider_id": "peer_id del fornitore",
  "consumer_id": "peer_id del consumatore",
  "model": "Qwen/...",
  "tokens": 1450,
  "amount": 1.45,          // tokens / rate
  "created_at": 1788042809.0,
  "provider_signature": "base64...",
  "consumer_signature": "base64..." | null,
  "settlement_ref": null   // riservato ad AiloNetwork
}

// Settings
{
  "sharing_enabled": false,     // default: NON condivido
  "shared_models": [],
  "rate_tokens_per_coin": 1000,
  "max_tokens_per_request": 4096,
  "max_concurrent": 3,
  "max_requests_per_hour": 60,
  "display_name": "Sigma Peer"
}
```

Persistenza: `data/sigma_network/peers.json`, `wallet.json`, `settings.json`,
`identity.json`. Scritture atomiche (file temporaneo + `os.replace`).

---

## 4. Requisiti di qualita — su questi il lavoro viene valutato

**Codice.** Type hints su ogni funzione pubblica. Docstring che spiegano il
*perche*, non il *cosa*. Nessun `except: pass` silenzioso: ogni eccezione o e
gestita o e loggata. Nessun import inutilizzato. Nessun valore hard-coded che
appartiene a `settings.json`.

**Concorrenza.** `peer_registry` e `ailocoin` sono letti dalle route HTTP e
scritti dai thread di discovery: ogni stato condiviso va protetto da un lock.

**Interfaccia.** Deve essere adattabile a qualsiasi schermo: layout in
flex/grid, nessuna larghezza fissa in pixel sui contenitori, tabelle con
`overflow-x: auto`. Deve rispettare tema chiaro e scuro usando le variabili CSS
gia presenti nel progetto — leggerle da `sigma_studio/src/styles/`, non
inventare colori. Ogni stato va rappresentato: caricamento, vuoto, errore,
popolato. Nessun pulsante senza feedback.

**Test.** `tests/test_sigma_network.py` deve coprire almeno:
- generazione identita e stabilita del `peer_id` fra due caricamenti;
- firma e verifica, incluso il caso di firma non valida;
- calcolo del saldo da una lista di ricevute;
- rifiuto di una richiesta da un peer non `trusted`;
- clamp di `max_tokens` oltre il limite;
- round-trip di persistenza del registro peer.
I test non devono aprire socket reali ne dipendere dalla rete.

---

## 5. Ordine di esecuzione

I task vanno svolti in questo ordine: ognuno dipende dal precedente.

1. `identity.py` + test di identita e firma.
2. `peer_registry.py` + `manifest.json` + test di persistenza.
3. `ailocoin.py` + test di saldo e ricevute.
4. `provider.py` + `inference_broker.py` + test dei limiti.
5. `discovery.py`.
6. `handlers.py` + `__init__.py` + registrazione route in `core/fastapi_app.py`.
7. `network_server.py` (MCP).
8. Frontend: `SigmaNetwork.jsx` e i quattro pannelli + CSS.
9. Registrazione della tab: aggiungere `sigma_network: 'sigma_network'` a
   `TAB_TO_FOLDER` in `sigma_studio/src/modules/registry.js`.
10. Passata finale: eseguire i test, correggere, verificare che il server parta.

Dopo ogni task: eseguire `python -m pytest tests/test_sigma_network.py -q` e
proseguire solo se passa.
