# Stato dell'Harness · 8 settembre 2026 (rev. 2)

Valutazione dell'harness dell'agente nel kernel: cosa regge, cosa no, e cosa serve
prima del prossimo lavoro — rendere l'intero Sigma Studio, moduli e tab compresi,
impostabile in più lingue.

| | |
|:---|:---|
| Test verdi | **1183** |
| Build frontend | verde (~0,9 s) |
| `npm run lint:undef` | 0 riferimenti non definiti |
| Punti dell'audit tecnico | 11 / 11 chiusi |
| Difetti trovati **dopo** la chiusura dell'audit | 9, tutti nell'integrazione |

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
**ai punti in cui i moduli nuovi incontrano il ciclo** ne ha trovati altri nove.
Nessuno era visibile dai test dei singoli moduli, perché nessuno stava dentro un
modulo, e due sono usciti soltanto provando il percorso vero.

| Difetto | Effetto |
|:---|:---|
| `isolate_worktree` dichiarato e mai passato da nessuno | L'intero isolamento non era accendibile da alcun percorso reale |
| Chiusura del run fuori da un `finally` | Ogni stop lasciava un worktree e un branch orfani |
| `git branch -D` a ogni obiettivo non raggiunto | Trenta turni di lavoro buono cancellati per l'ultimo passo mancante |
| `apply_to_main` con base sbagliata e senza l'ultimo turno | La modifica che *chiudeva* l'obiettivo non arrivava all'albero principale |
| `shutil.copy2` nella sincronizzazione moduli | Una volta su quattro il commit veniva saltato in silenzio |
| Prova a vuoto che rispecchiava davvero | Il pannello diceva «tutto allineato» su lavoro mai pubblicato |
| `manifest.backend.handlers_module` mai letto | Sbagliato in 7 moduli su 15, e nessuno se n'era accorto |
| `diff_from_main` con base sbagliata e senza i file nuovi | Chi rivede avrebbe approvato una cosa diversa da quella applicata |
| Revisione di fine run confusa con quella per scrittura | Le scritture si fermavano una per una, scadevano, e alla fine non restava niente da rivedere |

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

Quattro dei nove **riportavano successo mentre perdevano lavoro**: il branch
cancellato, il commit saltato, la prova a vuoto che si autoconsumava, e la
revisione di fine run che annullava il lavoro che doveva far vedere. In un
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

## 4. Fatto in questo giro

**Revisione a livello di run.** `review_run` mostra una volta sola il diff di
tutto ciò che il run ha prodotto e chiede una decisione: approvato passa
all'albero principale, rifiutato resta sul branch della sessione. Richiede
l'isolamento in worktree, e se manca lo dice invece di fingere.

Due difetti trovati costruendolo, entrambi nel punto che conta. `diff_from_main`
aveva la stessa base sbagliata già corretta in `apply_to_main`, e guardava solo i
commit: ometteva l'ultimo turno e **tutti i file nuovi**, cioè la maggior parte di
un lavoro di internazionalizzazione — chi rivede avrebbe approvato una cosa e ne
sarebbe stata applicata un'altra. E la condizione del cancello per scrittura
guardava se il gate esistesse invece di quale revisione fosse stata chiesta:
provandolo dal vivo, le scritture si sono fermate una per una, sono scadute, e
alla fine non restava niente da rivedere. Verificato end to end su un repository
vero, in entrambi i versi.

**Un controllo di progetto vale come prova**, a una condizione: deve dire
**quanti elementi ha esaminato**.

```
SIGMA-CHECK {"check": "i18n", "checked": 214, "problems": 0}
```

`checked` è il punto. Un controllo che non ha guardato niente esce con codice zero
esattamente come uno che ha guardato tutto senza trovare nulla — è la differenza
fra una prova e un'illusione, ed è la stessa regola per cui qui una suite con zero
test raccolti non passa. Senza la riga, o con `checked` a zero, il cancello di
completamento resta chiuso. Contratto in `AGENTS.md`, dove l'harness lo mette
davanti all'agente. Resta da scrivere il controllo vero per la lingua: è lavoro
del prossimo compito, e ora ha un modo di essere creduto.

---

## 5. Cosa manca ancora, in ordine

Il compito — rendere impostabile la lingua in tutto Sigma Studio, moduli e tab —
è per forma un intervento meccanico su centinaia di file, con poche decisioni
difficili all'inizio e molte ripetizioni dopo.

### 1. Ventaglio di run paralleli su una coda condivisa
Oggi c'è un ciclo per volta e un orchestratore a cinque fasi **sequenziali**.
Duecento file in sequenza non finiscono. Serve una coda di lavoro persistente
(voce, stato, esito, riprendibile) e N run in parallelo che la consumano —
possibile in sicurezza solo adesso che ogni run può stare nel proprio worktree,
e leggibile solo adesso che il lavoro di ciascuno si rivede in una volta.
**È il pezzo che manca per primo.**

### 2. Disciplina del codemod
La via efficiente non è far riscrivere 200 file a un modello: è fargli scrivere
**uno script** che li riscrive, controllare un campione, e trattare a mano solo
le eccezioni. Il prompt oggi spinge verso `edit_file` file per file. Serve una
regola esplicita e un modo di applicare uno script a un insieme di file
riportando l'esito per ciascuno.

### 3. Traduzione a lotti con i segnaposto protetti
Un percorso separato dal ciclo dell'agente: catalogo → lingue, con protezione di
`{nome}`, `%s` e degli elementi interpolati in JSX, un glossario di termini che
non si traducono, e una validazione che i segnaposto sopravvivano. È codice nuovo,
non harness.

### 4. La lingua deve arrivare anche al backend
Messaggi d'errore, risposte delle rotte, prompt dei ruoli. Se l'intervento si
ferma al frontend, metà del prodotto resta in italiano.

### 5. Poi
Rollback manuale dal pannello (i checkpoint ci sono, il pulsante no);
unificazione fra `tabType`/`sidebar*` nei manifest e la mappa scritta a mano in
`registry.js`; P2P, che resta per ultimo.
