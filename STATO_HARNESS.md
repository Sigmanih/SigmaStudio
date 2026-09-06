# Stato dell'Harness di Sigma Studio · Revisione 6 Settembre 2026

Rapporto tecnico completo sull'evoluzione dell'harness dell'agente nel kernel, l'analisi delle lacune chiuse, lo stato dei commit recenti e la roadmap dettagliata per l'autonomia dello sviluppo.

---

## 1. Quadro Generale dei Risultati

| Metrica | Audit Iniziale | Stato Attuale | Progresso |
|:---|:---:|:---:|:---:|
| **Test verdi nel kernel** | 895 | **1000 passed** | +105 test |
| **Punti Audit Chiusi** | 0 / 11 | **3 / 11 completati** | Punti 1, 3, 8 chiusi; Punto 2 provato dal vivo |
| **Turni medi al completamento** | 30 (fallito/deadlock) | **12 / 30 turni** | Completamento effettivo con criteri dimostrati |
| **Frontend Vite Build** | N/D | **Verde (822ms)** | Nessuna regressione |
| **Controllo Riferimenti non definiti** | Fallito (invisibile tra 815 errori) | **0 no-undef (isolato)** | Comando dedicato `npm run lint:undef` |

---

## 2. Le Diciotto Lacune Chiuse Storiche

1. **Harness nel kernel**: Unificazione del runtime in `core/harness/`, mentre il Developer Studio resta modulo installabile in `core/modules/sigma_developer_lab/`.
2. **Completamento vincolato ai criteri**: Primo turno obbligato a produrre una specifica; `complete_goal` esige prova esplicita per ciascun criterio.
3. **Prefix cache riparata e multi-slot**: Stato rimosso dalla testa del prompt; prefisso dedicato per ruolo per evitare sfratti di cache.
4. **Finestra di contesto reale**: Correzione del calcolo della finestra con `-np N` (che divideva il contesto disponibile).
5. **Tre stalli distinti**: Gestione differenziata tra chi non ha visto nulla (esplora), chi ha elencato senza leggere (legge), chi ha letto (agisce).
6. **Ruoli come dato**: Configurazione `config/roles.json` sovrapposta ai predefiniti campo per campo.
7. **Scelta del modello da configurazione**: Rimossa l'euristica automatica che forzava modelli lenti scavalcando la scelta utente.
8. **Blocco scritture dal terminale**: Intercettati i comandi di scrittura inline che aggiravano backup, ledger e sintassi.
9. **Profili operativi effettivi**: Applicazione rigorosa dei vincoli di sola lettura e sola pianificazione.
10. **Approvazione interattiva non scavalcabile**: Il timeout non è più interpretato come consenso implicito.
11. **Task raggruppati per ruolo**: Riduzione dei cambi di modello da cinque a due nel percorso standard.
12. **Tool-calling nativo**: Fence + GBNF per motori locali, chiamate strutturate per provider esterni.
13. **Sessioni persistenti**: Sopravvivenza del ledger a refresh e riavvio.
14. **Regole dal workspace**: `AGENTS.md` letto dinamicamente dalla radice.
15. **Multi-provider, terminale background e rollback**: Instradamento SigmaEngine/esterni, processi persistenti e ripristino sessione.
16. **Indice dei simboli e diagnostica frontend**: Ricerca definizioni simboli e validazione sintattica multi-linguaggio.
17. **Hook e CLI headless**: Ganci pre/post tool ed esecuzione batch.
18. **Metriche di run**: Tracciamento turni, token, latenza ed esiti tool nel `run_metrics`.

---

## 3. Commit Recenti e Lavori Svolti

### Commit `85a380a` — Far eseguire le pipeline visuali dall'harness (Punto 1 dell'Audit)
* **Problema**: I nodi del designer visuale generavano risposte finte segnaposto («Esecuzione nodo X per l'obiettivo Y»), bypassando l'harness.
* **Soluzione**: Creato `core/harness/node_runner.py` e modificato `core/pipeline/runner.py`. I nodi con un ruolo dichiarato (`architect`, `coder`, ecc.) istanziano un agente autonomo con tool, ledger e completion gate condiviso. I nodi generici eseguono prompt puri senza tool.
* **Risultato**: 940 test verdi, la tab Pipelines è ora ancorata all'harness reale.

### Commit `e6a8852` — Correzione difetti emersi dalla prima pipeline reale
* Risolto `NameError` in `generate_with_role` che leggeva il modello effettivo prima di calcolarlo.
* Risolto loop di ripetizione su `complete_goal` respinto che non memorizzava le firme fallite.

### Commit `036c013` & `b22bacb` — Isolamento Workspace e Tool Policy per Ruolo (Punto 2 dell'Audit)
* **Isolamento Git**: Introdotto `core/harness/workspace.py` per legare i tool git al progetto su cui l'agente lavora anziché al repository di Sigma Studio.
* **Tool Policy**: In `core/harness/policy.py`, il prompt del sistema filtra i tool in base a ciò che il ruolo può effettivamente usare, evitando tentativi di tool non permessi (`append_file`).
* Disattivato `auto_approve` su tool sensibili come `git_push`.

### Commit `f18627e` — Gate di Revisione del Diff e Igiene di Runtime (Punto 3 dell'Audit)
* **Kernel (`core/harness/review.py`)**:
  * Pattern *apply-and-revert*: applica la modifica sul disco reale, calcola il diff unificato e ripristina byte per byte se rifiutata o in caso di timeout (300s).
  * `FileSnapshot` con gestione dei file cancellati, file nuovi e preservazione dei fine riga CRLF/LF.
  * Thread-safe tramite `RLock` e registro per sessione `gate_for(session_id)`.
* **Ciclo agente (`core/harness/loop.py`)**:
  * Flag `review_writes` integrata. Emissione eventi SSE `write_proposed` e `write_reverted`.
  * La registrazione nel ledger avviene solo dopo approvazione umana; il rifiuto viene restituito all'agente come tool fallito per evitare che finisca come prova di lavoro.
* **Test (`tests/test_review_gate.py`)**: 29 test completi passati.
* **Server e Sistema**:
  * In `core/system_cleanup.py`: rilevamento e kill sicuro di processi orfani/zombie (pytest rimasti appesi, server orfani, vecchi llama-server), monitoraggio RAM reale di sistema e `EmptyWorkingSet`.
  * In `sigma_server.py`: porta dinamica `_resolve_available_port` con abbattimento processi orfani su porta 8000 e timeout aumentati.
  * In `sigma_studio`: polling del frontend sospeso quando il tab è nascosto (`document.visibilityState !== 'hidden'`).

### Commit `d46d601` — Controllo mirato `no-undef` (Punto 8 dell'Audit)
* Configurato `sigma_studio/eslint.config.undef.js` mirato unicamente all'errore `no-undef`.
* Aggiunto comando `npm run lint:undef` in `package.json`.
* Aggiunto il comando alla sezione Verifica di `AGENTS.md`.

---

## 4. Stato delle 11 Lacune dell'Audit e Roadmap Rimanente

| # | Task | Stato Attuale | Prossima Azione |
|:---:|:---|:---:|:---|
| **1** | **Pipeline visuali via harness** | **CHIUSO** | Già integrato in `core/harness/node_runner.py` (commit `85a380a`). |
| **2** | **Orchestratore 5 fasi dal vivo** | **IN CORSO** | Primi run eseguiti; corretti isolamento workspace e policy tool. Necessita ulteriori test end-to-end con Architect/Reviewer. |
| **3** | **Gate di revisione del diff** | **CHIUSO (Kernel)** | Backend e test pronti (commit `f18627e`). Resta la UI nel Developer Studio per mostrare il diff. |
| **4** | **Worktree git per run** | **APERTO** | Isolamento fisico in worktree separato con rollback multi-turno istantaneo (`git reset/restore`). |
| **5** | **Ledger e cancello nella Chat** | **APERTO** | Portare ledger e vincoli di verifica in `core/chat/` per eliminare file spazzatura e allucinazioni. |
| **6** | **Verifica strutturata anziché solo exit code** | **IN SVILUPPO** | Parsing dell'output dei test (`pytest`, `vitest`, `npm test`) per verificare test effettivamente raccolti e passati (`collected > 0`, `passed > 0`). |
| **7** | **Errori di console nel controllo visivo** | **APERTO** | Intercettare log di console e ReferenceError nel subagent browser headless post-modifica UI. |
| **8** | **Controllo mirato sui riferimenti non definiti** | **CHIUSO** | Implementato `npm run lint:undef` e registrato in `AGENTS.md` (commit `d46d601`). |
| **9** | **Editor dei ruoli nella tab Pipelines** | **APERTO** | UI per la modifica interattiva di prompt, tool, modelli e budget di `config/roles.json`. |
| **10** | **Compattazione con sintesi accanto al ledger** | **APERTO** | Riassunto progressivo delle motivazioni storiche nei run oltre 15-20 turni. |
| **11** | **Tool-calling nativo contro provider cloud** | **APERTO** | Test reale con API key OpenAI / DeepSeek. |

---

## 5. Piano Operativo Immediato

1. **Implementare il Punto 6 (Verifica Strutturata)**:
   * Creare `core/harness/verification.py` per fare il parsing rigoroso degli output dei comandi (`pytest`, `unittest`, `npm run lint:undef`, `npm run build`, ecc.).
   * Nel cancello `check_completion_allowed()` e nel ledger, rifiutare comandi di test con 0 test raccolti o 0 passati.
   * Scrivere la suite di test in `tests/test_structured_verification.py`.
2. **Implementare il Punto 4 (Git Worktree per Run)**:
   * Creazione automatica di un worktree git per la sessione dell'agente.
   * Checkpoint di turno per rollback istantaneo su più turni.
3. **Completare il Punto 9 (Editor Ruoli UI)**:
   * Frontend nella tab Pipelines per gestire ruoli, prompt e modelli.
