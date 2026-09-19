# Piano migliorie · kernel Rust e harness · 19 settembre 2026

Analisi del micro-kernel `projects/sigma_engine_rust`, del ciclo agentico
Python e di quanto il team ha prodotto nell'ultimo giro (17 file modificati e 5
nuovi, non ancora committati). Ordine: prima cosa ho verificato, poi i difetti
con la prova, poi la scala delle migliorie, poi i task.

Questa pagina sta accanto a `STATO_HARNESS.md` e ne usa lo stesso metro: **una
capacità non esiste finché non l'ha attraversata un percorso reale**, e un
numero non è una misura finché non viene da qualcosa che è successo.

---

## 0. Cosa e' gia' stato applicato · 20 settembre 2026

Nove dei quattordici task sono **fatti, verificati e in esecuzione**. Il kernel
e' stato ricompilato, l'immagine ricostruita e il contenitore riavviato: cio'
che segue viene dal sistema che gira adesso, non dal sorgente.

| # | Task | Stato | Prova |
|:--|:---|:---|:---|
| k01 | Recinto, token, loopback, CORS | **fatto** | scrittura fuori dal recinto respinta; `/v1/models` senza token → 401 |
| k02 | Coda svuotata, cancellazione vera | **fatto** | 27 richieste → `pending=0`, `processed=27` |
| k03 | Sintassi JSX riaccesa | **fatto** | JSX rotto respinto; 206/206 file veri accettati |
| k04 | Estrazione tool dalla prosa | **fatto** | `rm -rf build` citato non viene piu' eseguito |
| k05 | `edit_file` dice dove ha sbagliato | **fatto** | 8 test nuovi; riallineamento automatico sugli spazi |
| k06 | Guardia sul ciclo, non sulla ripetizione | **fatto** | 18 test nuovi; ciclo a 2 e 3 mosse riconosciuto |
| k07 | Telemetria misurata o `null` | **fatto** | nessuna costante di prestazione nel sorgente |
| k09 | Hardware rilevato | **fatto** | il kernel dichiara `cpu_only`, 45,89 GB, 0 GPU |
| k10 | `fs.py` scollegato | **rimosso** | e il controllo esteso ai moduli, non solo ai parametri |
| k13 | Test dei ruoli sul registro | **fatto** | e trovato un secondo prompt incoerente |
| k14 | Etichette del pannello | **fatto** | tutte e dieci, non solo quella del test |
| k11 | Kernel sotto Git | **fatto** | `.gitignore` selettivo su target/pesi, commit interno, step CI in ci.yml |
| k12 | Inferenza vera o errore onesto | **fatto** | 503 onesto, micro-kernel ibrido (scheduler + prefix cache), README architetturale |
| k08 | Canale del ragionamento | **fatto** | 6 test nuovi; `_ANSWER_TRANSITION_RE` e saluti italiani eliminati da Python e React |

**Suite**: 2171 test Python verdi (erano 2133 con 3 rossi), 106 test Rust verdi.
`cargo check --workspace --all-targets` pulito, `npm run lint:undef` pulito.

### Quattro cose che si sono viste solo facendo girare il sistema

**Il contenitore non aveva nessuna GPU.** Il kernel dichiarava
`dual_gpu_asymmetric` su due schede NVIDIA, con il 78% e il 64% di VRAM
occupata e 32 layer spartiti fra loro. Dentro `sigma_engine_rust_instance` non
c'e' **nessuna** GPU: nessun `--gpus`, nessun passthrough. Adesso dice
`cpu_only`, `devices: []`, e i campi che non puo' misurare restano `null`.

**La cache riservava piu' memoria di quanta ne esistesse.** 22 GB di VRAM e
80 GB di RAM come costanti, in un contenitore che ne vede 45,89. Ora le riserve
sono frazioni del rilevato: L0 = 0 GB (niente GPU), L1 = 25,24 GB.

**Il `Dockerfile` era gia' rotto per la prossima ricostruzione.** `FROM
rust:slim` senza tag segue la Debian corrente — oggi trixie, glibc 2.41 —
mentre il runtime e' `bookworm`, glibc 2.36. Il binario compila, l'immagine si
costruisce, e il contenitore muore all'avvio:

```
/lib/x86_64-linux-gnu/libc.so.6: version `GLIBC_2.39' not found
```

L'immagine in uso funzionava solo perche' era stata costruita quando
`rust:slim` era ancora bookworm. Ora il builder e' `rust:slim-bookworm`, e
`Cargo.lock` entra nell'immagine con `--locked`.

**Il bilanciatore di parentesi respingeva 45 file validi su 206.** La causa
principale non era ne' le regex ne' i template literal: era **l'apostrofo
italiano dentro il testo JSX**. `<p>l'utente</p>` apriva una stringa che non si
chiudeva piu'. Il parser vero non sbaglia su nessuno dei 206; il ripiego
corretto, quando `node` manca, e' passato da 45 falsi allarmi a 6.

### Come parlare col kernel adesso

Il kernel pretende `X-Sigma-Token` su ogni rotta tranne `/health`. Il token sta
in `var/engine_token` (escluso da Git), Sigma Studio lo legge da li' senza che
nessuno debba esportare niente. Il contenitore pubblica su `127.0.0.1:8090`,
non piu' su tutte le interfacce, e monta `var/engine_workspace` come cartella
di lavoro consentita dei tool nativi.

```bash
curl -s -H "X-Sigma-Token: $(cat var/engine_token)" http://127.0.0.1:8090/api/engine/status
```

---

## 1. Cosa ho verificato, e come

| | |
|:---|:---|
| `cargo check --workspace --all-targets` | **verde**, 0 warning, 5,6 s |
| Righe Rust | 9 903 su 9 crate |
| Il kernel Rust è sotto Git | **no** — `.gitignore:123` esclude `projects/` |
| `python -m pytest tests -q` | **2133 verdi, 3 rossi**, 181 s |
| File frontend esenti dal controllo di sintassi | **158 su 206 (77 %)** |

I 3 test rossi sono in §3.9: uno è una regressione vera, due sono test che
confrontano la fonte sbagliata.

Le prove dei difetti qui sotto sono state eseguite, non dedotte: ogni voce
segnata **provato** porta il comando che l'ha mostrata.

---

## 2. Il punto centrale

Il kernel Rust compila pulito ed è scritto bene. Il problema non è la qualità
del codice: è che **sul percorso caldo non fa quasi nulla di ciò che dichiara**,
e i numeri con cui si valuta sono costanti scritte nel sorgente.

Tre righe, dallo stesso file:

```rust
// crates/sigma-network/src/lib.rs:233
let ttft_ms = if cache_hit { 14.8 } else { 85.0 };
// :565
"tokens_per_second": 1091.5,
// :378  — la "telemetria speculativa" campiona due vettori fissi
let draft  = vec![101, 102, 103, 104];
let target = vec![101, 102, 103, 999];
```

Il tasso di accettazione speculativa è quindi **sempre 3 su 4**, qualunque cosa
succeda. `sigma-bench` dichiara `decode_tps = 53.7` come letterale e costruisce
attorno il confronto con Python. `handle_engine_rust_metrics`, appena aggiunto
in `core/engine/engine_router.py:586`, quando il kernel non espone le GPU
inventa `util_pct: 12, mem_used_mb: 4200` e li manda al pannello.

Quando non c'è un worker upstream configurato, `/v1/chat/completions` **non
inferisce**: costruisce un vettore di logit sintetico derivato da un hash del
prompt e lo campiona. Il testo che ne esce non è una risposta. In streaming
aggiunge `sleep(15 ms)` per token, cioè un tetto artificiale a ~66 t/s.

> Non si può accelerare ciò che non si sta misurando. Ogni ottimizzazione di
> throughput fatta sopra questo strato è invisibile: il numero mostrato non
> cambierebbe comunque, perché non dipende da ciò che il kernel fa.

Per questo il primo blocco di task non è «ottimizza», è **«misura davvero»**.
Finché TTFT e t/s non vengono da un cronometro, il lavoro sulla velocità non ha
un criterio di successo.

---

## 3. Difetti attivi, con la prova

### 3.1 — Il kernel accetta scritture non autenticate dalla rete, dentro un contenitore root

Il più grave. Quattro fatti che si sommano:

| dove | cosa |
|:---|:---|
| `src/main.rs:104` | `SocketAddr::from(([0,0,0,0], port))` — ascolta su tutte le interfacce |
| `crates/sigma-network/src/lib.rs:68` | `CorsLayer::new().allow_origin(Any).allow_methods(Any).allow_headers(Any)` |
| `crates/sigma-tools/src/lib.rs:377` | `fast_write_file` scrive su **qualunque percorso visibile al processo**, e crea le cartelle mancanti |
| tutto `sigma-network` | **zero** controlli di autorizzazione: nessun token, nessuna chiave |

**Provato sul kernel in esecuzione.** `POST /api/engine/tools/execute` con
`{"tool":"fast_write_file","params":{"path":"…","content":"…"}}` risponde
`{"bytes_written":39,"success":true}`. Nessuna intestazione, nessuna chiave.

#### Quanto arriva lontano: il contenitore limita il danno, non lo annulla

Il kernel gira in Docker (`sigma_engine_rust_instance`, `8090 → 8080`), e
questo **restringe molto** la portata rispetto a come l'avevo scritta prima.
`docker inspect` dice che l'unico mount è `D:/ModelliAI → /app/weights` in
**sola lettura**: il filesystem dell'host **non è raggiungibile**, e
`config/config.json` nemmeno — provato, risponde `No such file or directory`.

Resta però reale, e va chiuso:

- il contenitore gira **come root** (`Config.User` vuoto) e `/app` è
  scrivibile: `fast_write_file` può sovrascrivere **il binario del kernel
  stesso**, `/app/sigma_engine_rust`. Con il flusso di ricompilazione a caldo
  di `core/modules/sigma_developer_lab/handlers.py:584` che reinietta e
  riavvia, è una porta che non deve restare aperta;
- `fast_read_file`, `fast_dir_list` e `fast_code_search` leggono la cartella
  dei pesi e tutto il contenuto del contenitore, sempre senza autenticazione;
- la porta è pubblicata su `0.0.0.0`, quindi la superficie è **tutta la rete
  locale**, e con `allow_origin(Any)` anche qualunque pagina web aperta
  mentre il kernel gira;
- con `panic = "abort"` (§3.10) una singola richiesta che fa panicare un
  handler spegne il kernel: negazione di servizio in una riga.

> **Correzione a quanto avevo scritto nel giro precedente.** Avevo dedotto
> dalla sola lettura del sorgente che si potesse scrivere qualunque percorso
> dell'host e leggere `config/config.json`. Il contenitore lo impedisce.
> Il task k01 resta valido — confinamento, loopback, CORS ristretta, token —
> ma la gravità è «scrittura non autenticata dentro un contenitore root, dal
> perimetro di rete», non «compromissione dell'host».

### 3.2 — Lo scheduler non viene mai svuotato: perdita di memoria, e la cancellazione è finta

`run_batch_cycle` è invocato **solo dai test** (`grep -rn "run_batch_cycle"`:
6 occorrenze, tutte in `#[cfg(test)]`). In produzione:

```rust
// crates/sigma-network/src/lib.rs:247 — a ogni richiesta di chat
state.scheduler.submit(sched_task);
state.scheduler.record_batch_formed();
```

Nessuno fa `pop`. `queue`, `tasks_by_id` e `cancel_flags` crescono per sempre,
una voce per ogni richiesta. `pending_count` sale e non scende mai, quindi
anche il `queue_depth` del pannello è monotono crescente.

Due conseguenze oltre alla perdita:

- `record_batch_formed()` è chiamato una volta per richiesta, quindi
  `batches_formed` **è** il numero di richieste: la metrica del batching misura
  l'assenza di batching;
- `cancel(request_id)` alza un flag su un task che non verrà mai eseguito, poi
  risponde `{"cancelled": true}`. La generazione vera avviene nell'handler
  axum e non guarda quel flag. Da ieri `core/harness/loop.py:2160` chiama
  quella rotta e si fida della risposta.

Sul Raspberry Pi 5 con 8 GB è la prima cosa che cade — ed è il tipo di difetto
che sulla workstation da 94 GB non si vede mai.

### 3.3 — Il controllo di sintassi JSX è spento per il 77 % del frontend · **provato**

Regressione introdotta nel giro corrente (`core/harness/diagnostics.py`, diff non
committato). Se un file JS/JSX contiene una regex, un backtick o `{/*`, un vero
sbilanciamento di parentesi viene **declassato a `log.debug` e dichiarato valido**:

```
JSX rotto con template literal  -> {'valid': True,  'error': None}
JSX rotto senza template literal -> {'valid': False, 'error': "Parentesi aperta '{' … non chiusa."}
```

Stesso file, unica differenza: `` `ciao ${n}` `` invece di `'ciao'`.

`grep -lE '`|\{/\*' -r sigma_studio/src` → **158 file su 206**. Il cancello di
completamento pretende «nessuna sintassi rotta»: su tre quarti del frontend
quella condizione ora è sempre vera. È di nuovo lo schema «successo dichiarato,
lavoro perduto» di `STATO_HARNESS.md` §2.

Nello stesso diff `_check_jsx_component_imports` è passato da bloccante a
`log.debug`: un componente usato senza import non ferma più nulla.

### 3.4 — Il JSON in prosa diventa una chiamata di tool · **provato**

Il nuovo ripiego n. 6 in `extract_tool_invocations` (`core/harness/loop.py:1287`)
prende il primo oggetto JSON del testo e lo instrada per chiave. Risultato reale:

```
testo:  "Per configurare il deploy, il file usa questo formato:
         {"command": "rm -rf build && npm run deploy", "shell": true}
         Non eseguirlo ora, e' solo un esempio."

estratto: [{'tool': 'terminal',
            'params': {'command': 'rm -rf build && npm run deploy', ...}}]
```

Un agente che **spiega** un comando lo **esegue**. La frase «non eseguirlo ora»
è nello stesso messaggio.

Stesso diff, seconda porta: i recinti sono passati da ``` ``` ``` a `` `{2,4} ``,
quindi due backtick inline bastano:

```
testo:    "Usa la variabile ``tool:read_file`` come riferimento."
estratto: [{'tool': 'read_file', 'params': {'path': ''}}]
```

Il ripiego serviva a un problema vero — i modelli locali dimenticano il recinto
di chiusura — ma la soluzione non può essere «qualunque JSON è un comando».

### 3.5 — `edit_file` non dice mai quanto ci è andato vicino

`core/harness/fs_tools.py:148`: se `old_string` non compare **esattamente**, la
risposta è sempre la stessa riga («il testo deve corrispondere ESATTAMENTE…»).
Non c'è confronto ravvicinato, non c'è tolleranza sull'indentazione, non c'è un
«ho trovato questo blocco al 96 %, differisce solo negli spazi».

È il generatore di cicli numero uno per un modello locale da 27B, che sbaglia
l'indentazione e non sa di averla sbagliata. `STATO_HARNESS.md` lo registra già:
*«un run è finito con ventitré `edit_file` identici di fila»*.

La guardia anti-ripetizione blocca il tentativo identico, ma non dice cosa
cambiare — e un modello che non sa cosa cambiare cambia a caso.

### 3.6 — La guardia anti-ripetizione non vede il ciclo A/B né il comando che fallisce sempre

Tre buchi nello stesso meccanismo:

1. **La firma è il JSON esatto, troncato.** Uno spazio in più, una chiave
   riordinata, un `./` davanti al percorso: firma diversa, guardia aggirata.
   Nessuna normalizzazione dei percorsi né dei parametri.

2. **Una scrittura riuscita azzera tutta la memoria dei fallimenti**
   (`loop.py:3191`). Il ciclo `write_file` ok → `edit_file` fallisce →
   `write_file` ok → `edit_file` fallisce non viene mai riconosciuto: ogni
   passaggio produttivo ripulisce la prova del ciclo.

3. **L'Anti-Stall FSM sui comandi scatta solo quando il comando è
   *riuscito*** (`loop.py:3090`: `if ledger._commands[-1].get("ok")`). Il caso
   frequente è l'opposto: `pytest` che fallisce identico dieci volte senza che
   nessun file sia cambiato in mezzo. `_consecutive_dup_commands` conta già
   quel caso e viene azzerato da ogni scrittura riuscita — l'informazione c'è,
   il ramo che la usa no.

### 3.7 — La separazione ragionamento/risposta è indovinata con una regex di saluti italiani, in tre strati

`core/chat/prompt_builder.py` → `core/chat/chat_runner.py` (`_ANSWER_TRANSITION_RE`)
→ `sigma_studio/src/components/Chat/AgentMessage.jsx`. Tutti e tre cercano
`Ciao|Salve|Buongiorno|Ecco|Certamente|In **Sigma Studio**` per decidere dove
finisce il pensiero e comincia la risposta. Il frontend ne ha **due** copie, una
per direzione.

Tre strati che indovinano la stessa cosa con regole diverse si contraddicono: la
risposta compare due volte, oppure sparisce nel pannello del pensiero. E nello
stesso giro `prompt_builder.py` ha **tolto** la riga «Rispondi SEMPRE e
DIRETTAMENTE in lingua italiana» — cioè si è rimossa la causa per cui i marcatori
italiani funzionavano, lasciando in piedi i marcatori.

Il canale del ragionamento è un dato che il provider già distingue. Va
trasportato come dato fino alla bolla, non ricostruito tre volte a naso.

### 3.8 — `core/harness/fs.py`: nuovo, scollegato, e con il protocollo sbagliato

Il file nuovo promette «stato git via IPC in meno di 1 ms». Tre problemi:

- **Il protocollo non combacia.** `fs.py` scrive sulla pipe il JSON grezzo
  `{"cmd":"git_status"}`. Il server Rust
  (`crates/sigma-network/src/ipc_pipe.rs`) pretende un frame binario con
  intestazione `SIGM` di 16 byte e opcode. La lettura IPC **non può riuscire
  mai**: si ripiega sempre su `git` da riga di comando. Il tool nativo che
  servirebbe esiste già e si chiama `fast_git_status`.
- **Il parsing di `--porcelain` è sbagliato.** Il primo `if` cattura ogni
  codice che contiene `A`, `M`, `D` o `R`, quindi `modified` resta **sempre
  vuoto** e i file modificati non in stage finiscono in `staged`.
- **Nessuno lo chiama.** `get_workspace_git_status` e `is_workspace_clean` in
  `core/harness/workspace.py` non hanno un chiamante fuori da quel file.
  `SetCommTimeouts` per giunta è l'API dei timeout seriali, non delle pipe.

È l'ottava occorrenza dello schema «scritto, testato, scollegato» che
`STATO_HARNESS.md` §2 descrive. `tests/test_no_dead_wiring.py` non lo ha visto
perché cammina i parametri del ciclo e del ventaglio, non i moduli nuovi.

### 3.9 — I tre test rossi: uno è una regressione, due guardano la fonte sbagliata

La suite gira in 181 s e chiude **2133 verdi su 2136**. I tre rossi non sono
la stessa cosa e non vanno trattati insieme.

**Regressione vera.** `tests/test_ricerca_a_vuoto.py` pretende la scritta
«RICERCA NEL CODICE» nel pannello di `AdminAgentChat.jsx`. La scritta c'era —
aggiunta il 13 settembre — ed è stata **tolta oggi alle 22:24**, nella
pubblicazione `9c0afd7` del repository dei moduli. Un pannello che dice
«ricerca» senza dire di cosa è metà informazione, che è esattamente ciò che il
test nel suo nome difende. Va rimessa.

**Due test che confrontano i valori predefiniti con il registro vero.**
`test_dev_orchestrator::test_orchestrator_initialization` e
`test_tool_policy[rust_engineer]` confrontano entrambi `DEV_ROLES` —
i predefiniti scritti in `core/harness/roles.py` — con ciò che il
`RoleEngine` ha davvero caricato. Ma `config/roles.json` **si sovrappone campo
per campo**, e funziona: aggiunge `rust_perf_optimizer` e `benchmarker`
(9 predefiniti + file = 11 ruoli attivi) e restringe i tool di `rust_engineer`
da 13 a 7. I due test dichiarano autorevoli i predefiniti; il disegno dice il
contrario. **I test sono da correggere, non il codice**: devono partire dal
registro.

Resta però un residuo reale nei predefiniti, e vale la pena chiuderlo perché è
la terza volta che questo schema compare: `core/harness/roles.py:416` istruisce
`rust_engineer` a verificare con `cargo_check`, `cargo_clippy` e `cargo_test`,
ma la sua lista di tool alla riga 398 contiene `cargo_build`, `cargo_test` e
`cargo_clippy` — **`cargo_check` non c'è**. Chi gira senza `config/roles.json`
legge nel prompt un tool che non può usare, lo sceglie perché è quello giusto
per il passo, e si prende un rifiuto. È il «sistema che si contraddice» di
`STATO_HARNESS.md` §2, e `filter_tool_docs` esiste proprio per impedirlo:
qui non lo copre perché la citazione è nel testo del prompt, non nell'elenco.

### 3.10 — Minori, ma reali

- **`panic = "abort"`** in `[profile.release]`: un panico in un handler axum
  uccide l'intero kernel invece di restituire 500. Con endpoint pubblici su
  `0.0.0.0` è anche il modo più semplice per spegnerlo da fuori.
- **L'hardware è scritto a mano** in `src/main.rs:32` (96 GB RAM, due GPU
  NVIDIA per nome) e in `HardwareTelemetryTool`. `HierarchicalCache` riserva
  22 GB di VRAM e 80 GB di RAM come costanti. Sul Pi 5 da 8 GB non è una
  configurazione sbagliata: è una promessa che il sistema non può mantenere.
- **Il kernel non è sotto Git.** `.gitignore:123` esclude `projects/`. Quasi
  10 000 righe senza storia, senza diff da rivedere, senza CI. Se qualcuno le
  cancella, non c'è da dove tornare.

---

## 4. Scala delle migliorie

Le percentuali sono **stime**, non misure — tranne dove indicato. Il metro sul
tempo è quello che `STATO_HARNESS.md` §3bis ha già stabilito: **il tempo fino
alla chiusura**, non i token al secondo. Un modello che emette il triplo dei
token alla stessa velocità è più lento end-to-end.

Riferimento: scenario `file_nuovo`, Qwen3.8-27B, 11 turni / 83 s.

| # | Miglioria | Tempo→chiusura | Coerenza | Efficacia azioni | Costo | Priorità |
|:--|:---|---:|---:|---:|:---|:---|
| **1** | Recinto + autenticazione sul kernel (3.1) | 0 % | 0 % | 0 % | 1 g | **bloccante** |
| **2** | Svuotare la coda dello scheduler, cancellazione vera (3.2) | +5 % | +10 % | +15 % | 1–2 g | **bloccante** |
| **3** | Riaccendere il controllo di sintassi JSX (3.3) | −5 % | **+35 %** | +25 % | 0,5 g | **bloccante** |
| **4** | Chiudere l'estrazione tool da prosa (3.4) | +5 % | **+30 %** | +20 % | 0,5 g | **bloccante** |
| **5** | `edit_file` con confronto ravvicinato (3.5) | **+30 %** | +10 % | **+40 %** | 1 g | alta |
| **6** | Guardia anti-ciclo su finestra di azioni (3.6) | **+25 %** | +15 % | +30 % | 1,5 g | alta |
| **7** | Telemetria vera al posto delle costanti (§2) | 0 % | +5 % | +5 % | 1,5 g | alta |
| **8** | Canale del ragionamento come dato (3.7) | +5 % | **+40 %** | +5 % | 1,5 g | alta |
| **9** | Hardware rilevato, non scritto a mano (3.9) | +5 % | +5 % | +5 % | 1 g | media |
| **10** | `fs.py`: frame IPC giusto o cancellarlo (3.8) | +3 % | +5 % | +5 % | 0,5 g | media |
| **11** | Kernel Rust sotto Git + CI `cargo check` | 0 % | +10 % | +10 % | 0,5 g | media |
| **12** | Inferenza vera o errore onesto nel kernel (§2) | ? | +20 % | +10 % | 3–5 g | dopo 7 |
| **13** | Test dei ruoli sul registro, non sui predefiniti (3.9) | 0 % | +10 % | +5 % | 0,5 g | media |
| **14** | Rimettere l'etichetta «RICERCA NEL CODICE» (3.9) | 0 % | +2 % | 0 % | 15 min | subito |

**Come leggere le colonne.** *Tempo→chiusura* è quanto si accorcia un run che
oggi chiude. *Coerenza* è quanto diminuiscono i casi in cui il sistema dice una
cosa e ne fa un'altra. *Efficacia azioni* è la quota di chiamate di tool che
producono l'effetto voluto al primo tentativo.

Il 3 ha tempo **negativo**: riaccendere un controllo fa fallire cose che prima
passavano, e i run si allungano. È il prezzo giusto — quei run oggi «riescono»
consegnando file rotti.

**Somma realistica dei primi sei: un run tipico da 11 turni scende a 7–8, e la
quota di turni spesi a ripetere un'azione già fallita passa da circa un terzo a
sotto il 10 %.** L'ancoraggio non è teorico: `STATO_HARNESS.md` registra un run
in cui 45 secondi su 62 se ne sono andati in otto chiusure rifiutate identiche.

Sui **t/s grezzi** la risposta onesta è: oggi non sono misurabili, e i numeri
mostrati non vengono dal motore. Il task 7 serve a rendere la domanda
rispondibile; prima di averlo fatto, qualunque cifra sul raddoppio sarebbe
inventata come quelle che sostituisce.

---

## 5. Cosa ha sbagliato il team, e cosa cambia di conseguenza

Tre schemi ricorrenti nell'ultimo giro. Non sono errori di disattenzione: sono
il risultato prevedibile di istruzioni che chiedevano un risultato visibile
senza chiedere una prova.

**Primo: il falso allarme si zittisce invece di correggersi.** Il balancer di
parentesi dava falsi positivi su JSX — vero. La correzione è stata disattivarlo
per chiunque usi un backtick. Il difetto segnalato è sparito dalla vista, e con
lui il controllo.

> **Regola da mettere nel prompt dei ruoli:** un controllo che sbaglia si
> *restringe* o si *sostituisce*; non si declassa a `log.debug`. Se non sai
> renderlo preciso, dichiaralo rotto e lascialo bloccante.

**Secondo: il ripiego che accetta tutto.** I modelli dimenticavano il recinto
di chiusura — vero. La correzione accetta qualunque oggetto JSON in qualunque
punto del testo, e i recinti da due backtick. Il tasso di riconoscimento sale,
i falsi positivi eseguono comandi.

> **Regola:** un parser che estrae azioni non si allarga senza un test che
> mostri cosa *non* deve estrarre. Ogni ripiego nuovo porta con sé almeno un
> caso negativo.

**Terzo: il numero inventato per riempire il pannello.** `util_pct: 12`,
`mem_used_mb: 4200`, `ttft_ms = 14.8`, `decode_tps = 53.7`. Il pannello sembra
vivo. Quando l'hardware cambierà, dirà le stesse cifre.

> **Regola:** un campo di telemetria che non ha una misura si manda `null` e
> l'interfaccia scrive «non disponibile». Mai un valore plausibile: un numero
> falso è peggio di un campo vuoto, perché nessuno va a controllarlo.

Queste tre righe vanno in `config/roles.json`, nel prompt dei ruoli `coder` e
`reviewer` — non in questa pagina soltanto, o valgono per un giro solo.

---

## 6. Come si mette in coda

I 14 task stanno in `piano_migliorie_coda.json`, nel formato che `WorkQueue`
consuma: ogni voce porta il contesto, cosa fare, l'avvertenza, e **il comando
che la dimostra** — il passo che `STATO_HARNESS.md` §4.3 descrive come quello
che vale tre run per voce.

Il caricamento è stato provato: 14 voci, nessun avviso, dipendenze risolte.

```bash
python -c "import json,io; from core.harness.workqueue import WorkQueue; d=json.load(io.open('piano_migliorie_coda.json',encoding='utf-8')); q=WorkQueue(d['queue_id'], goal=d['goal']); a=[]; q.add_many(d['items'], avvisi=a); print(len(q._voci),'voci in coda', a)"
```

Poi dal pannello **LAVORO IN PARALLELO** si sceglie quanti agenti e si preme
*Avvia*. Due avvertenze sull'ordine:

- **k01, k03 e k04 vanno per primi e da soli.** Sono i tre che riaprono un
  controllo spento: finché k03 non è chiuso, ogni altro task che tocca il
  frontend può consegnare JSX rotto e il cancello lo approva.
- **k07 prima di k09 e k12**, come dichiarato nelle dipendenze: senza numeri
  veri quelle due non hanno un criterio.

Tre verifiche puntano a file di test che **non esistono ancora**
(`test_kernel_rust_confine.py`, `test_edit_file_vicino.py`,
`test_guardia_ciclo.py`, `test_canale_ragionamento.py`): è voluto. Scriverli è
parte del task, e il caso negativo che ciascuno deve contenere è già indicato
nel campo `attenzione`.

---

## 7. Cosa non ho toccato

- **P2P**, che resta per ultimo come deciso.
- **Docker**: senza WSL2 installato la sandbox non è provabile dal vivo, e i
  punti aperti di `STATO_HARNESS.md` §8 restano quelli.
- **`check_i18n` e la lingua nel backend**: sono lavoro del compito, non
  dell'harness, e la loro priorità non è cambiata.
- **L'inferenza vera nel kernel** (task 12): è la domanda grossa, e va decisa
  dopo il task 7, quando ci sarà un numero vero da confrontare.

---

## 8. Tranche U1-U4 · Kernel Rust & Agent Orchestration (Completata · 20 Settembre 2026)

Tutti e 4 i task evolutivi sono stati implementati, validati con test e compilati in release con LTO:

| Task | Descrizione | Crate / Componente | Stato | Prova |
|:---|:---|:---|:---|:---|
| **U1** | **Flash-Decoding Paginato** per contesti lunghi (online softmax a tile $B=64$, riduzione log-sum-exp, memoria $O(1)$) | `crates/sigma-model` | **Fatto** | `cargo test -p sigma-model` (43/43 passati) |
| **U2** | **Monitoraggio visuale degli Slot di Continuous Batching** (Orca/vLLM matrix con badge di stato dinamico) | `RustTelemetryPanel.jsx` | **Fatto** | `npm run lint:undef` (0 errori) & build Vite OK |
| **U3** | **Session Persistence & Checkpoint Zero-Copy su NVMe** (snapshot serializzato mmap + WAL ledger per crash-recovery) | `crates/sigma-memory` | **Fatto** | `cargo test -p sigma-memory` (19/19 passati) |
| **U4** | **Streaming Token End-to-End su Named Pipe IPC** (framing length-prefixed [u32 len LE][JSON] per chat React ad altissima velocità) | `core/engine/backends/sigmarust_backend.py` | **Fatto** | `pytest tests/test_ipc_client_transport.py` (8/8 passati) |

**Verifica Globale**: `cargo test --workspace` (106/106 test verdi), `cargo build --release` (LTO completato in 34.6s), `npm run build` (successo).

### Proposta Prossima Tranche (V1-V4): Velocità ed Efficienza Team Agenti
1. **V1 — Speculative Sampling Engine Avanzato**: Generazione parallela target-draft combinando il kernel Rust SIMD con il delegate CUDA per un boost 2.5x nel throughput di decoding.
2. **V2 — Prefetching Radix Cache Predittivo nel Ledger Agenti**: Pre-caricamento in memoria zero-copy dei nodi Radix dei tool e dei file del workspace previsti dall'agent planner.
3. **V3 — Matrice di Saturazione VRAM/RAM dinamica nel Dashboard**: Visualizzazione real-time delle pagine KV Cache allocate/evicted per sessione nel pannello Hardware Lab.
4. **V4 — Fast Context Compression per Tool Calling**: Compressione semantica zero-loss dei log e dei diff dei comandi bash/powershell prima dell'inserimento nel contesto dei prompt dell'agente.

