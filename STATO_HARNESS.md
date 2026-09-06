# Stato dell'Harness di Sigma Studio · Revisione 6 Settembre 2026

Rapporto tecnico completo sull'evoluzione dell'harness dell'agente nel kernel, l'analisi delle lacune chiuse, lo stato dei commit recenti e la roadmap dettagliata per l'autonomia dello sviluppo.

---

## 1. Quadro Generale dei Risultati

| Metrica | Audit Iniziale | Stato Attuale | Progresso |
|:---|:---:|:---:|:---:|
| **Test verdi nel kernel** | 895 | **1025 passed** | +130 test |
| **Punti Audit Chiusi** | 0 / 11 | **7 / 11 completati** | Punti 1, 3, 4, 5, 6, 7, 8 chiusi; Punto 2 provato dal vivo |
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

### Prossimo Commit — Errori di console nel controllo visivo (Punto 7 dell'Audit)
* `core/harness/visual.py`: Aggiunto `--enable-logging=stderr` a Chromium headless; implementato `extract_console_errors()` per catturare eccezioni `ReferenceError`, `TypeError`, `Uncaught ...`.
* Se si verificano crash JS, `capture()` ritorna `success: False` con dettaglio degli errori.
* `core/harness/ledger.py`: Le schermate con errori di console vengono rifiutate come prove visive e l'errore registrato in `_failures`.
* Test in `tests/test_visual_console_errors.py` (6 test verdi).

---

## 4. Stato delle 11 Lacune dell'Audit e Roadmap Rimanente

| # | Task | Stato Attuale | Prossima Azione |
|:---:|:---|:---:|:---|
| **1** | **Pipeline visuali via harness** | **CHIUSO** | Già integrato in `core/harness/node_runner.py` (commit `85a380a`). |
| **2** | **Orchestratore 5 fasi dal vivo** | **IN CORSO** | Primi run eseguiti; corretti isolamento workspace e policy tool. Necessita ulteriori test end-to-end con Architect/Reviewer. |
| **3** | **Gate di revisione del diff** | **CHIUSO (Kernel)** | Backend e test pronti (commit `f18627e`). Resta la UI nel Developer Studio per mostrare il diff. |
| **4** | **Worktree git per run** | **CHIUSO** | Implementato `core/harness/worktree.py` con allocazione worktree isolata, checkpoint di turno e rollback automatico. |
| **5** | **Ledger e cancello nella Chat** | **CHIUSO** | Implementato `core/chat/ledger.py` con cancello di mutazione `is_mutation_permitted` in `file_extractor.py`, bloccando scritture involontarie da query informative. |
| **6** | **Verifica strutturata anziché solo exit code** | **CHIUSO** | Implementato `core/harness/verification.py` e integrato nel ledger (commit `84ef969`). Rifiuta test a vuoto e documenta i test superati. |
| **7** | **Errori di console nel controllo visivo** | **CHIUSO** | Implementato parsing console stderr di Chromium headless e blocco nel ledger in caso di crash JS (commit in arrivo). |
| **8** | **Controllo mirato sui riferimenti non definiti** | **CHIUSO** | Implementato `npm run lint:undef` e registrato in `AGENTS.md` (commit `d46d601`). |
| **9** | **Editor dei ruoli nella tab Pipelines** | **IN CORSO** | UI ed endpoint per la modifica interattiva di prompt, tool, modelli e budget di `config/roles.json`. |
| **10** | **Compattazione con sintesi accanto al ledger** | **APERTO** | Riassunto progressivo delle motivazioni storiche nei run oltre 15-20 turni. |
| **11** | **Tool-calling nativo contro provider cloud** | **APERTO** | Test reale con API key OpenAI / DeepSeek. |

---

## 5. Piano Operativo Immediato

1. **Commit Punto 7 (Errori di console visivi)**.
2. **Realizzazione Punto 9 (Editor dei Ruoli nella tab Pipelines)**:
   * Backend: verificare le rotte per leggere e salvare `config/roles.json` tramite `core/harness/roles.py`.
   * Frontend: inserire l'editor di configurazione ruoli (prompt, tool abilitati, modello selezionato, budget turni) all'interno del modulo Pipelines / Developer Studio.
   * Verifica con test del backend e build frontend.
