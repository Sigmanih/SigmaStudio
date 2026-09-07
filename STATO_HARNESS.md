# Stato dell'Harness · 8 settembre 2026

Valutazione dell'harness dell'agente nel kernel: cosa regge, cosa no, e cosa serve
prima del prossimo lavoro — rendere l'intero Sigma Studio, moduli e tab compresi,
impostabile in più lingue.

| | |
|:---|:---|
| Test verdi | **1148** |
| Build frontend | verde (~0,9 s) |
| `npm run lint:undef` | 0 riferimenti non definiti |
| Punti dell'audit tecnico | 11 / 11 chiusi |
| Difetti trovati **dopo** la chiusura dell'audit | 7, tutti nell'integrazione |

---

## 1. Cosa c'è, e regge

**Il ciclo.** Multi-turno con ledger di sessione persistente, cancello di
completamento che pretende prove ancorate a fatti (non la parola del modello),
recupero dallo stallo in tre stadi distinti (chi non ha visto nulla esplora, chi
ha elencato senza leggere legge, chi ha letto agisce), compattazione della
cronologia con memoria decisionale per i run lunghi.

**I ruoli come dato.** `config/roles.json` si sovrappone ai predefiniti campo per
campo: prompt, modello, budget di turni, tool permessi. La policy dei tool è
un'intersezione fra profilo operativo (tetto scelto dall'utente) ed elenco del
ruolo, e il prompt documenta soltanto i tool che quel ruolo può davvero usare.

**Le tre reti di sicurezza.** Revisione del diff prima che una scrittura resti;
isolamento del run in un worktree git con checkpoint di turno; conservazione del
lavoro su un branch quando l'obiettivo non viene chiuso.

**Il motore.** Prefix cache multi-slot per ruolo, finestra di contesto reale
(divisa per gli slot del backend), tool-calling nativo dove il provider lo
supporta e grammatica GBNF dove no, verifica strutturata dei test che rifiuta le
suite a zero test anche con exit code 0.

**La pubblicazione dei moduli.** Si sviluppa dentro Sigma Studio, si pubblica nel
repository dei moduli: `core/module_sync.py` è l'inverso del loader.

---

## 2. Cosa ha continuato a rompersi, e perché conta

Le 11 lacune dell'audit erano chiuse, con i loro test verdi. Una rilettura mirata
**ai punti in cui i moduli nuovi incontrano il ciclo** ne ha trovati altri sette.
Nessuno era visibile dai test dei singoli moduli, perché nessuno stava dentro un
modulo.

| Difetto | Effetto |
|:---|:---|
| `isolate_worktree` dichiarato e mai passato da nessuno | L'intero isolamento non era accendibile da alcun percorso reale |
| Chiusura del run fuori da un `finally` | Ogni stop lasciava un worktree e un branch orfani |
| `git branch -D` a ogni obiettivo non raggiunto | Trenta turni di lavoro buono cancellati per l'ultimo passo mancante |
| `apply_to_main` con base sbagliata e senza l'ultimo turno | La modifica che *chiudeva* l'obiettivo non arrivava all'albero principale |
| `shutil.copy2` nella sincronizzazione moduli | Una volta su quattro il commit veniva saltato in silenzio |
| Prova a vuoto che rispecchiava davvero | Il pannello diceva «tutto allineato» su lavoro mai pubblicato |
| `manifest.backend.handlers_module` mai letto | Sbagliato in 7 moduli su 15, e nessuno se n'era accorto |

### Il pattern

Cinque volte una funzionalità è stata **scritta, testata e lasciata scollegata**:
`is_tool_allowed`, i profili operativi, il binding del modello per ruolo,
l'isolamento in worktree, il campo `handlers_module`. Ogni volta i test erano
verdi, perché chiamavano la funzione direttamente.

> Un test che non parte da un percorso raggiungibile dall'utente non dimostra che
> la funzionalità esista.

`tests/test_no_dead_wiring.py` cammina ora i parametri del ciclo e pretende che
ognuno sia passato da almeno un chiamante di produzione, leggendolo dal sorgente.
Va esteso, non aggirato: se un parametro nuovo lo fa fallire, la risposta è
collegarlo o non dichiararlo.

### Il secondo pattern, più insidioso

Tre dei sette difetti **riportavano successo mentre perdevano lavoro**: il branch
cancellato, il commit saltato, la prova a vuoto che si autoconsumava. In un
sistema che serve a non perdere lavoro, il fallimento silenzioso è la modalità di
guasto peggiore. Dove c'è una contraddizione fra due fonti — il mirror dice
«cambiato», git dice «no» — adesso il sistema si ferma e lo dice.

---

## 3. Valutazione

**Regge**: un obiettivo circoscritto su pochi file, con verifica eseguibile. È il
caso su cui l'harness è stato costruito e misurato (12 turni su 30 per un
endpoint funzionante con criteri dimostrati).

**Non regge ancora**: un lavoro che tocca *centinaia* di file. Non per un difetto,
ma per assenza di tre cose — esecuzione parallela, una coda di lavoro che
sopravvive ai run, e una revisione all'altezza della scala. È esattamente la
forma del prossimo compito.

---

## 4. Cosa manca, in ordine di valore per il prossimo lavoro

Il compito — rendere impostabile la lingua in tutto Sigma Studio, moduli e tab —
è per forma un intervento meccanico su centinaia di file, con poche decisioni
difficili all'inizio e molte ripetizioni dopo. Quello che manca è tutto lì.

### 1. Revisione a livello di run, non di file
`WorktreeSession.diff_from_main()` esiste e non la chiama nessuno. Con il gate
attuale un lavoro da 200 file chiederebbe 200 approvazioni: nessuno le dà, e il
gate verrebbe spento — cioè la rete di sicurezza sparisce proprio quando serve di
più. Serve il diff dell'intero run, rivisto una volta.

### 2. Ventaglio di run paralleli su una coda condivisa
Oggi c'è un ciclo per volta e un orchestratore a cinque fasi **sequenziali**.
Duecento file in sequenza non finiscono. Serve una coda di lavoro persistente
(voce, stato, esito, riprendibile) e N run in parallelo che la consumano —
possibile in sicurezza solo adesso che ogni run può stare nel proprio worktree.

### 3. Disciplina del codemod
La via efficiente non è far riscrivere 200 file a un modello: è fargli scrivere
**uno script** che li riscrive, controllare un campione, e trattare a mano solo
le eccezioni. Il prompt oggi spinge verso `edit_file` file per file. Serve una
regola esplicita e un modo di applicare uno script a un insieme di file
riportando l'esito per ciascuno.

### 4. Un controllo di completezza che faccia da prova
Il cancello di completamento vuole prove ancorate. Per questo lavoro la prova è:
ogni chiave usata esiste in ogni lingua, nessun letterale non tradotto resta nei
file elencati, la build passa. Serve quel controllo come comando eseguibile, e un
parser in `verification.py` che ne legga il risultato — altrimenti l'agente
dichiara finito un lavoro che nessuno ha misurato.

### 5. Traduzione a lotti con i segnaposto protetti
Un percorso separato dal ciclo dell'agente: catalogo → lingue, con protezione di
`{nome}`, `%s` e degli elementi interpolati in JSX, un glossario di termini che
non si traducono, e una validazione che i segnaposto sopravvivano. È codice nuovo,
non harness.

### 6. La lingua deve arrivare anche al backend
Messaggi d'errore, risposte delle rotte, prompt dei ruoli. Se l'intervento si
ferma al frontend, metà del prodotto resta in italiano.

### 7. Poi
Rollback manuale dal pannello (i checkpoint ci sono, il pulsante no);
unificazione fra `tabType`/`sidebar*` nei manifest e la mappa scritta a mano in
`registry.js`; P2P, che resta per ultimo.
