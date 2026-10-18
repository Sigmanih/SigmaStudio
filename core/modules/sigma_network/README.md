# Sigma Network

Rete peer-to-peer di Sigma Studio per l'inferenza distribuita, con contabilità
AiloCoin. Specifica completa del lato P2P in [`SPEC.md`](SPEC.md) (nel kernel:
`core/modules/sigma_network/SPEC.md`).

## Rete AiLo (AiloCoin ALC + inferenza distribuita)

Il coordinatore AiLo originale ([ailo-network](https://github.com/xxrickyxx/ailo-network),
`ailo.site`) è **dismesso**: la sua infrastruttura ora vive dentro Sigma
Studio. Un'istanza attiva l'**hub AiLo** e diventa il coordinatore della rete;
le altre istanze vi si collegano come prima facevano con `ailo.site`.
Tutto dalla tab **Rete AiLo** di Sigma Network.

### Hub AiLo (`ailo_hub.py`)

| Parte | Cosa fa |
|---|---|
| Registro AiloCoin | SQLite in `data/sigma_network/ailo_hub.db`, stesso schema `users`/`transactions` del vecchio server. Saldi definitivi, hash per ogni transazione, supply = somma dei saldi. |
| Account | Registrazione e login con lo stesso hash scrypt del coordinatore Node: gli account migrati entrano con la loro vecchia password. |
| Trasferimenti | Solo con password; importi positivi; niente auto-trasferimenti; controllo del saldo atomico (due invii concorrenti non spendono la stessa moneta); commissione minima su `/api/ledger/transfer`. |
| Nodi di inferenza | WebSocket `/ws/gpu-inference` (protocollo del client CUDA AiLo). Le richieste vanno al nodo libero usato meno di recente; ogni risposta paga 0,05 ALC al nodo, al massimo 20 volte l'ora per wallet. |
| Migrazione | Import di un `ailo.db` del vecchio server: account, saldi e storico; rieseguirlo non duplica nulla. |

API pubbliche dell'hub, compatibili con il vecchio coordinatore, sotto
`/api/sigma_network/ailo_hub`:

```
GET  /api/status   /api/network-stats   /api/nodes   /api/v1/token   /api/balance/{wallet}
POST /api/register  /api/login  /api/transfer  /api/ledger/transfer
POST /api/v1/rpc                 alc_getBalance, alc_getTransaction, alc_getTransactionsByAddress,
                                 alc_getBlockNumber, alc_getTotalSupply, alc_getNetworkStats, alc_getTokenInfo
POST /api/inference/gpu          smistata ai nodi collegati
POST /api/inference/fused        motore locale dell'hub
WS   /ws/gpu-inference           nodi di inferenza
```

Amministrazione (solo da questa macchina, loopback):

```
GET  /api/sigma_network/ailo/hub/status
POST /api/sigma_network/ailo/hub/enable     {enabled}
POST /api/sigma_network/ailo/hub/use_local  collega il bridge all'hub di questa istanza
POST /api/sigma_network/ailo/hub/import     {path}  migra un ailo.db
```

### Collegarsi a un hub (`ailo_bridge.py`)

| Funzione | Come funziona |
|---|---|
| Verifica hub | `alc_getTokenInfo` deve dichiarare il token `ALC` e `/api/status` lo stato del coordinatore; senza verifica non si inviano credenziali. |
| Wallet ALC | Login/registrazione, saldo, storico via JSON-RPC, trasferimenti con password (mai salvata né loggata). |
| Inferenza distribuita | `/api/inference/gpu` (nodi della rete) o `/api/inference/fused` (motore dell'hub). |
| Nodo di inferenza | Si collega a `/ws/gpu-inference` dell'hub col proprio wallet e risponde con il motore locale di Sigma. Solo generazione di testo, `max_tokens` limitato lato nodo, guard RAM/concorrenza del provider P2P. |

API locali del bridge (`/api/sigma_network/ailo/...`):

```
GET  /config  POST /config {server_url, node_max_tokens, node_model, gpu_label}
GET  /status  POST /login | /register {email, password}  GET /wallet
POST /transfer {to_wallet, amount, password}
POST /infer {prompt, max_tokens, temperature, backend: gpu|fused}
POST /node/start | /node/stop   GET /node/status
```

URL da indicare alle altre istanze: `http(s)://<host-hub>:<porta>/api/sigma_network/ailo_hub`.

Test: `tests/test_sigma_network_ailo.py` (bridge) e `tests/test_sigma_network_ailo_hub.py` (hub), senza rete.
