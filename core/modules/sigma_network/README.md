# Sigma Network

Rete peer-to-peer di Sigma Studio per l'inferenza distribuita, con contabilità
AiloCoin. Specifica completa del lato P2P in [`SPEC.md`](SPEC.md) (nel kernel:
`core/modules/sigma_network/SPEC.md`).

## Rete AiLo (AiloCoin ALC + inferenza distribuita)

Il modulo parla nativamente il protocollo del coordinatore
[ailo-network](https://github.com/xxrickyxx/ailo-network): Sigma Studio entra
nella rete AiLo come un miner GPU ufficiale, senza il client CUDA separato.
Tab **Rete AiLo** nell'interfaccia di Sigma Network.

| Funzione | Come funziona |
|---|---|
| Verifica server | `alc_getTokenInfo` deve dichiarare il token `ALC` e `/api/status` lo stato del coordinatore; senza verifica non si inviano credenziali. |
| Wallet ALC | Login/registrazione (`/api/login`, `/api/register`), saldo confermato/pendente (`/api/balance/:wallet`), storico via JSON-RPC (`alc_getTransactionsByAddress`). |
| Trasferimenti | `/api/transfer`, autenticato da password. La password non viene mai salvata né loggata. |
| Inferenza distribuita (consumer) | `/api/inference/gpu` (nodi GPU della rete) o `/api/inference/fused` (modello AILO FedAvg). |
| Nodo di inferenza (provider) | WebSocket `/ws/gpu-inference`: `register_inference` con il wallet, risposta alle `inference_request` col motore locale di Sigma, heartbeat e riconnessione automatica. Solo generazione di testo; `max_tokens` limitato lato nodo e stessi guard RAM/concorrenza del provider P2P. |

### API locali (`/api/sigma_network/ailo/...`)

```
GET  /config            POST /config {server_url, node_max_tokens, node_model, gpu_label}
GET  /status            stato server, catena ALC, rete, nodo locale
POST /login | /register {email, password}
GET  /wallet            saldo + transazioni ALC
POST /transfer          {to_wallet, amount, password}
POST /infer             {prompt, max_tokens, temperature, backend: gpu|fused}
POST /node/start | /node/stop      GET /node/status
```

Il server AiLo va indicato esplicitamente (es. `http://localhost:3000` per un
coordinatore self-hosted): il dominio storico `ailo.site` oggi non ospita più
il coordinatore, e la verifica lo rileva.

Test: `tests/test_sigma_network_ailo.py` (senza rete).
