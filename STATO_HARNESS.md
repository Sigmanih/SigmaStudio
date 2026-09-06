# Stato dell'Harness di Sigma Studio · Revisione 6 Settembre 2026

Rapporto tecnico completo sull'evoluzione dell'harness dell'agente nel kernel, l'analisi delle lacune chiuse, lo stato dei commit recenti e la roadmap dettagliata per l'autonomia dello sviluppo.

---

## 1. Quadro Generale dei Risultati

| Metrica | Audit Iniziale | Stato Attuale | Progresso |
|:---|:---:|:---:|:---:|
| **Test verdi nel kernel** | 895 | **1037 passed** | +142 test |
| **Punti Audit Chiusi** | 0 / 11 | **10 / 11 completati** | Punti 1, 2, 3, 4, 5, 6, 7, 8, 9, 10 chiusi |
| **Turni medi al completamento** | 30 (fallito/deadlock) | **12 / 30 turni** | Completamento effettivo con criteri dimostrati |
| **Frontend Vite Build** | N/D | **Verde (782ms)** | Nessuna regressione |
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

### Commit `036c013` & `b22bacb` — Isolamento Workspace e Tool Policy per Ruolo
* **Isolamento Git**: Introdotto `core/harness/workspace.py` per legare i tool git al progetto su cui l'agente lavora anziché al repository di Sigma Studio.
* **Tool Policy**: In `core/harness/policy.py`, il prompt del sistema filtra i tool in base a ciò che il ruolo può effettivamente usare, evitando tentativi di tool non permessi (`append_file`).
* Disattivato `auto_approve` su tool sensibili come `git_push`.

### Commit `f18627e` — Gate di Revisione del Diff e Igiene di Runtime (Punto 3 dell'Audit)
* **Kernel (`core/harness/review.py`)**: Pattern *apply-and-revert* con diff unificato, `FileSnapshot` e thread safety.
* **Ciclo agente (`core/harness/loop.py`)**: `review_writes` integrata, eventi SSE `write_proposed` / `write_reverted`.
* **Server e Sistema**: Pulizia processi orfani/zombie e monitoraggio RAM in `core/system_cleanup.py`.

### Commit `d46d601` — Controllo mirato `no-undef` (Punto 8 dell'Audit)
* Configurato `sigma_studio/eslint.config.undef.js` mirato a `no-undef`.
* Comando `npm run lint:undef` in `package.json` e aggiornato `AGENTS.md`.

### Commit `84ef969` — Verifica strutturata anziché solo exit code (Punto 6 dell'Audit)
* Implementato `core/harness/verification.py` con parser strutturati per pytest, unittest, vitest e linter.
* Rifiuto esplicito di suite con 0 test raccolti o 0 eseguiti.

### Commit `18d444e` — Git worktree isolato per run (Punto 4 dell'Audit)
* Creato `core/harness/worktree.py` con allocazione worktree git isolata in `.sigma_worktrees/<session_id>`.
* Checkpoint di turno e rollback automatico a inizio sessione o turno specifico.

### Commit `78420d0` — Ledger e cancello di mutazione nella Chat (Punto 5 dell'Audit)
* Creato `core/chat/ledger.py` con `is_mutation_permitted()` e `ChatLedger`.
* Integrato in `core/chat/file_extractor.py` per bloccare estrazioni file su query informative/conversazionali.

### Commit `b2078ac` — Errori di console nel controllo visivo (Punto 7 dell'Audit)
* `core/harness/visual.py`: Aggiunto `--enable-logging=stderr` a Chromium headless; implementato `extract_console_errors()` per catturare eccezioni `ReferenceError`, `TypeError`, `Uncaught ...`.
* Se si verificano crash JS, `capture()` ritorna `success: False` con dettaglio degli errori.
* `core/harness/ledger.py`: Le schermate con errori di console vengono rifiutate come prove visive e l'errore registrato in `_failures`.
* Test in `tests/test_visual_console_errors.py` (6 test verdi).

### Commit `d42ddde` — Editor dei ruoli nella tab Pipelines (Punto 9 dell'Audit)
* **Backend (`core/fastapi_app.py`, `core/api_router.py`)**: Esposti endpoint core per ruoli `/api/roles`, `/api/developer/roles` (GET, POST) e `/api/roles/reset`, `/api/developer/roles/reset` (POST) collegati al registro unificato `core/harness/role_registry.py`.
* **Frontend (`sigma_studio/src/modules/sigma_research_lab/RolesEditor.jsx`)**: Creata interfaccia visuale completa per modificare prompt di sistema, modello preferito, budget turni (`max_turns`), max tokens, parametri di sampling e abilitazione selettiva dei tool con anteprima e salvataggio su `config/roles.json`.
* **Integrazione tab Pipelines (`ResearchLabTab.jsx`)**: Aggiunta la terza modalità "👥 Ruoli AI" accanto a "🚀 Pipeline Predefinita" e "🧩 Pipeline Designer".
* **Test (`tests/test_roles_api.py`)**: 3 test completi passati.

### Commit `ae60e00` — Orchestratore 5 fasi dal vivo e test end-to-end (Punto 2 dell'Audit)
* **Tracciamento modifiche esteso (`core/modules/sigma_developer_lab/orchestrator.py`)**: Rilevamento delle scritture sia su `write_file` che su `edit_file` e `append_file`, con fallback sul ledger condiviso per garantire che la fase `deliver` produca sempre il riepilogo corretto dei file modificati.
* **Verifica strutturata integrata (`core/harness/verification.py` & `orchestrator.py`)**: Introdotto `looks_like_test_run()` per applicare `parse_verification` sia durante `_execute_task`, sia durante la fase `verify`, sia nel `_feedback_loop` per rilevare test falliti o test suite vuote anche in presenza di exit code 0.
* **Test End-to-End (`tests/test_orchestrator_live_5phases.py`)**: 3 test completi per la sequenza autonoma delle 5 fasi (`analyze` -> `setup` -> `implement` -> `verify` -> `deliver`), il rispetto del rifiuto in modalità interattiva e l'attivazione automatica del feedback loop verso il Coder quando la verifica fallisce.

### Prossimo Commit — Compattazione con sintesi accanto al ledger (Punto 10 dell'Audit)
* **Memoria di Sessione Duratura (`core/harness/ledger.py`)**: Aggiunto blocco `session_memory` a `DevSessionLedger` con supporto per serializzazione, ripristino e rendering automatico nello state block del prompt.
* **Modulo di Compattazione Progressiva (`core/harness/compaction.py`)**: Analisi ed estrazione automatica delle motivazioni, decisioni e intoppi prima dello sfratto dei turni con fallback deterministico euristico e supporto LLM.
* **Integrazione nel Ciclo Agente (`core/harness/loop.py`)**: La compattazione dei turni vecchi alimenta permanentemente la memoria di sessione senza amnesia per run prolungati (30+ turni).
* **Test Suite Dedicata (`tests/test_history_compaction.py`)**: 6 test completi passati.

---

## 4. Stato delle 11 Lacune dell'Audit e Roadmap Rimanente

| # | Task | Stato Attuale | Prossima Azione |
|:---:|:---|:---:|:---|
| **1** | **Pipeline visuali via harness** | **CHIUSO** | Già integrato in `core/harness/node_runner.py` (commit `85a380a`). |
| **2** | **Orchestratore 5 fasi dal vivo** | **CHIUSO** | Flusso convalidato end-to-end (commit `ae60e00`). |
| **3** | **Gate di revisione del diff** | **CHIUSO (Kernel)** | Backend e test pronti (commit `f18627e`). Resta la UI nel Developer Studio per mostrare il diff. |
| **4** | **Worktree git per run** | **CHIUSO** | Implementato `core/harness/worktree.py` con allocazione worktree isolata, checkpoint di turno e rollback automatico. |
| **5** | **Ledger e cancello nella Chat** | **CHIUSO** | Implementato `core/chat/ledger.py` con cancello di mutazione `is_mutation_permitted` in `file_extractor.py`, bloccando scritture involontarie da query informative. |
| **6** | **Verifica strutturata anziché solo exit code** | **CHIUSO** | Implementato `core/harness/verification.py` e integrato nel ledger (commit `84ef969`). Rifiuta test a vuoto e documenta i test superati. |
| **7** | **Errori di console nel controllo visivo** | **CHIUSO** | Implementato parsing console stderr di Chromium headless e blocco nel ledger in caso di crash JS (commit `b2078ac`). |
| **8** | **Controllo mirato sui riferimenti non definiti** | **CHIUSO** | Implementato `npm run lint:undef` e registrato in `AGENTS.md` (commit `d46d601`). |
| **9** | **Editor dei ruoli nella tab Pipelines** | **CHIUSO** | UI `RolesEditor.jsx` integrata nella tab Pipelines ed endpoint `/api/roles` nel kernel (commit `d42ddde`). |
| **10** | **Compattazione con sintesi accanto al ledger** | **CHIUSO** | Memoria decisionale permanente nel ledger e compattazione progressiva con estrazione motivazioni. |
| **11** | **Tool-calling nativo contro provider cloud** | **APERTO** | Test reale con API key OpenAI / DeepSeek. |

---

## 5. Piano Operativo Immediato

1. **Commit Punto 10 (Compattazione con sintesi accanto al ledger)**.
2. **Implementare il Punto 11 (Tool-calling nativo contro provider cloud)**:
   * Connessione e verifica reale del tool-calling strutturato per provider cloud (OpenAI / DeepSeek).

