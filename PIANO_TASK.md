# La sequenza dei task · 22 settembre 2026

Cosa resta da fare, in ordine, e perché quell'ordine.

Il presupposto che cambia le priorità: **chi scarica Sigma Studio usa
SigmaEngine**, il motore Python. Il kernel Rust è il motore nuovo, in
sviluppo, e non deve bloccare niente. Tutto ciò che segue è ordinato di
conseguenza.

---

## Perché quest'ordine

**Prima ciò che impedisce alla squadra di lavorare.** Oggi il ventaglio ha
fallito nove volte su nove: 225 turni, zero lavoro consegnato. Finché un
agente non riesce a chiudere un task, nessuna delle migliorie successive viene
fatta da loro — le devo fare io, una per una. Ogni correzione in questo blocco
moltiplica tutte le altre.

**Poi ciò che l'utente tocca ogni giorno.** La chat e il primo avvio.

**Poi il motore Rust**, che è ricerca: va avanti in parallelo e non entra nel
percorso di chi scarica finché non fa inferenza vera.

**Infine la fiducia**: una suite che non si blocca e una CI. È ciò che permette
di andare veloci senza accorgersi tardi di aver rotto qualcosa.

---

## Blocco 1 — Perché la squadra possa lavorare

Quattro difetti, tutti osservati oggi su run veri.

### 1.1 · Il task troppo grande non viene spezzato · **fatto**

Nove run su nove hanno consumato **tutti** i turni disponibili. Due esiti
ricorrenti: «nessuna modifica prodotta entro i turni disponibili» e «lavoro
prodotto ma non dimostrato».

`queue_add` con `replaces` esiste ed è documentato nel prompt del ventaglio —
e nessun agente lo ha usato. Il motivo probabile è che la via d’uscita è
descritta in fondo a un prompt lungo, dopo l’obiettivo e le avvertenze, e chiede
di comporre a mano un JSON con quattro campi annidati.

Fatto il 23 settembre: a metà dei turni senza una sola scrittura il ciclo propone
la forma pronta (`_proposta_di_spezzatura` in `core/harness/loop.py`), **una volta
sola per run**, con `queue_id` e `item_id` già compilati; senza coda propone di
aggiornare la pipeline. Perché la condizione «solo se c’è la coda» fosse
esprimibile, `queue_id` e `item_id` sono diventati **parametri della firma** del
ciclo, e `core/harness/fanout.py` li passa: prima viaggiavano solo dentro il testo
del prompt, e il ciclo non sapeva di essere in una coda. I turni consumati sono ora
scritti nello stato del lavoro, e una ricerca ripetuta non azzera più il contatore
dei turni improduttivi — era quella la ragione per cui il recupero non entrava mai
in scena.

> **La premessa era sbagliata, ed è la seconda volta.** La voce diceva «il ciclo
> sa già se la coda esiste». Vero per il *testo* del prompt, falso per il
> *codice*: `fanout.py` passava `queue_id` a `_prompt_voce`, non a
> `stream_admin_agent_turn`. Un agente che cerca la risposta nei file dichiarati
> non può trovarla, e non può nemmeno dire di non averla trovata: il perimetro
> assegnato non contiene la riga che gli serve. Vale la regola di fondo: prima di
> scrivere in un task «questo dato arriva sempre così», si cercano **tutti** i
> chiamanti — e se la correzione tocca un secondo file, quel file entra nel task.

### 1.2 · La sandbox si può finalmente accendere · **alto**

`STATO_HARNESS.md` §7 dice «docker non è installato, e WSL non c'è». **Non è
più vero**: `docker --version` risponde 29.7.2. Il demone al momento è spento,
ma l'installazione c'è.

Questo sblocca il punto §8.1 e chiude il §8.2 — il comando del terminale senza
recinto. Il lavoro è: le immagini per progetto, la cache dei volumi, e il
`verify` della coda che deve girare **dalla stessa parte** del lavoro.

### 1.3 · Il consuntivo non arriva al ventaglio · **medio**

`run_report` è per singolo run. Un lavoro da cinquanta voci produce cinquanta
resoconti e nessuna vista d'insieme. Chi guarda non ha modo di sapere cosa è
stato fatto nel complesso senza aprirli uno per uno.

### 1.4 · Le dipendenze della coda non attraversano i worktree · **medio**

Una voce che dipende da un'altra vede il lavoro della prima solo dopo la
consegna. Finché `deliver` è spento — che è il modo in cui si lavora quando si
vuole rivedere prima — le dipendenze non funzionano affatto.

---

## Blocco 1b — Perché la squadra cercava e non trovava · **fatto**

Tre difetti, misurati sul run del 23 settembre che ha consumato 30 turni su 30
senza scrivere una riga: modello Qwen3.8-27B, pipeline a tre voci, voce 2 mai
cominciata, **zero scritture, zero errori dei tool**. L’agente non sbagliava: non
trovava. Le tre cause erano tutte fuori di lui.

### 1b.1 · La ricerca trovava sé stessa

`def stream_admin_agent_turn` dava **8 corrispondenze, 7 dentro `var/`**, di cui
tre erano il log di quella stessa ricerca scritto un turno prima: il contatore
cresceva di uno a ogni tentativo (6 → 7 → 8) perché la ricerca trovava sempre un
po’ di sé. `def _esegui_voce` dava 5 risultati, 4 in copie morte nei worktree di
run finiti. E `queue_id` esauriva il tetto dei 50 risultati sui file di coda
scritti a mano nella radice, senza arrivare mai a `core/harness/workqueue.py`.

Fatto: `SEARCH_IGNORE_RUNTIME_DIRS` in `core/harness/fs_manager.py` — `var`,
`store`, `logs` non entrano nell’albero cercato, mentre un percorso chiesto
esplicitamente resta visitabile — più `SEARCH_FIRST_DIRS` e
`_voci_da_esaminare()`, che visitano prima `core/`, `tests/`, `tools/`, `sigma_studio/`,
`projects/` e i file della radice per ultimi: il tetto non lo decide più l’ordine
del filesystem. Il controllo che lo misura è `tools/controlla_ricerca_stato.py`,
che dichiara quanti elementi ha esaminato.

### 1b.2 · Un file letto a pezzi non è un file letto

L’agente ha letto `core/harness/loop.py` (4212 righe) nelle finestre 1-1200 e
2400-2899 e ha cercato per dieci turni una firma che stava alla **riga 2132**:
dentro il buco. Il ledger sapeva dire «lo letto righe 1-1200, 2400-2899 di 4212»,
ma nessuno nominava ciò che mancava, e il rifiuto della rilettura diceva «chiedila
con un offset esplicito» lasciando il conto a chi non aveva in testa nemmeno la
lunghezza del file. La stessa frase, ripetuta, ha bruciato cinque turni su
`gguf_converter.py` e quattro su `pcb-lab.css`.

Fatto: `FileRecord.missing_ranges()` e `coverage_note()` che dice **anche il buco**
(`manca 1201-2399`), `DevSessionLedger.gap_windows()` che restituisce la finestra
pronta, e in `core/harness/loop.py` il rifiuto che porta la chiamata da emettere
("offset": 1201) o dichiara che il file è stato visto tutto. Durante il turno di
recupero una finestra mai vista non viene più rifiutata come una rilettura, e lo
stadio `gap` del recupero impedisce al ciclo di ripetere «scrivi ORA» a chi deve
soltanto leggere il pezzo mancante. Il messaggio `has_more` dice quante righe
restano.

### 1b.3 · La mappa dei simboli non arrivava a chi lavora

Il motore esisteva (`core/harness/symbol_index.py`, tool `find_symbol`) ma non era
fra i tool del ruolo Coder e non entrava nello stato per i file citati
nell’obiettivo: per un file di 4212 righe la prima finestra era una scelta cieca.

Fatto: `outline_of_file()`, `find_symbol` fra i tool del Coder e nel prompt, e
`_mappa_dei_file_citati()` che mette l’indice (nome + riga, con memo su mtime e
taglia) nello stato finché quel file non è stato letto per intero.

---

## Blocco 2 — Ciò che l'utente tocca

### 2.1 · Il ragionamento mangia il budget della risposta · **alto**

Osservato: `finish_reason: "length"` con la risposta tagliata a metà frase.

`max_tokens` è il tetto dell'**output**, e per un modello che ragiona quel
tetto copre ragionamento **più** risposta. Con 4096 token e un ragionamento da
3500, alla risposta ne restano 596. La riserva che esiste — `reserve_for_answer`
— protegge il **contesto in ingresso**, che è un'altra cosa.

Rimedio: quando il profilo chiede il ragionamento, il tetto va alzato di
conseguenza; e se lo stream finisce mentre si è ancora dentro il blocco di
pensiero, va chiesta una continuazione invece di mostrare una risposta vuota.
L'avviso di troncamento esiste già e arriva all'interfaccia: quello resta.

### 2.2 · La seconda pipeline della chat · **fatto**

Lo stadio 1 di `_clean_all_tags` è stato tolto, ma solo dopo aver chiuso la
**quarta** implementazione della stessa separazione — vedi la lezione in
fondo. I casi negativi li ha scritti l'agente.

### 2.3 · La lingua: una decisione, non un task · **da decidere**

Il `README` è in inglese, l'interfaccia è in italiano, e l'identità dell'agente
impone l'italiano nel prompt di sistema. Il frontend **non ha nessuno strato di
traduzione**: nessun `i18n`, nessun `useTranslation`, le stringhe sono scritte
nei componenti. `tools/estrai_stringhe.py` esiste e produce il catalogo, quindi
il primo passo è fatto.

Tre strade, e la scelta è tua:

- **italiano e basta**, e il README lo dice in chiaro;
- **inglese come lingua del prodotto**, italiano come traduzione;
- **multilingua vero**, con lo strato di traduzione nel frontend e i messaggi
  del backend passati dal catalogo.

Solo la terza è un lavoro grande. Non metto task in coda finché non scegli.

---

## Blocco 3 — Il motore Rust

Ricerca, in parallelo. Non entra nel percorso di chi scarica.

### 3.1 · Il puntatore al kernel non porta da nessuna parte · **decisione tua**

Tre fatti verificati:

- il kernel **ha** un repository suo: 21 commit dal 19 settembre;
- il repo padre lo traccia come gitlink (`160000 f19a84c`);
- **non esiste `.gitmodules`** e **il kernel non ha alcun remote**.

Chi clona Sigma Studio ottiene `projects/sigma_engine_rust/` **vuoto**, e
`git submodule update` non sa da dove prenderlo. L'unica copia di quelle
diecimila righe è su questo disco.

Dimmi dove deve vivere — un repository suo, dentro il principale, o un remote
locale su un altro disco — e lo cablo in un passo.

### 3.2 · Proxy o inferenza propria · **dopo i numeri**

La domanda aperta dal piano precedente. Il percorso proxy ora misura TTFT e
token al secondo davvero. Serve un confronto con il percorso diretto
llama.cpp che Sigma Studio già usa, e poi una decisione scritta nel README del
kernel.

### 3.3 · Le ottimizzazioni del kernel restano ferme · **volutamente**

`ac3_priority_preemption` è ancora `todo` e `ac1` era fallito tre volte. Sono
ottimizzazioni di throughput su un motore che non ha un modello attaccato:
accelerare ciò che non si misura non ha un criterio di successo. Riprendono
dopo il 3.2.

---

## Blocco 4 — La fiducia

### 4.1 · La suite si bloccava, e non era un test · **fatto oggi**

`server_health` faceva `os.walk` dalla radice quattro volte senza potare
niente. Dopo le build release di Rust, `projects/sigma_engine_rust/target/` ha
33 876 file. Da minuti a **0,58 s**.

Resta un secondo rallentamento: almeno un test **carica un GGUF vero**. Va
marcato, così la corsa veloce resta veloce e quella lenta si chiede quando
serve.

### 4.2 · Nessuna CI · **medio**

Nessun controllo automatico su `main`. Con la suite che torna veloce, un
workflow che esegue pytest e `cargo check` costa poco e vale molto.

---

### 4.3 · Tre moduli di test non si raccolgono · **basso, ma blocca la CI**

`tests/test_local_ca.py` e `tests/test_sigma_network.py` chiedono `cryptography`,
`tests/test_pdf_support.py` chiede `fitz`. In questo ambiente **tre moduli non si
raccolgono affatto** e `pytest tests/` si ferma in collection: i «1784 test
verdi» di `STATO_HARNESS.md` non sono riproducibili qui, e senza un numero che si
può confrontare la CI del 4.2 non serve a niente. Due strade, entrambe brevi:
installare le due dipendenze, oppure marcare i tre moduli con
`pytest.importorskip` così la suite esce con un totale dichiarato invece di
fermarsi.

**Risolto il 23 settembre**: i tre moduli ora dichiarano la dipendenza con
`pytest.importorskip` **prima** degli import (e dopo `from __future__`, che deve
restare la prima istruzione: scavalcarlo rende il file non parsabile), quindi la
suite parte e l esito si legge. Misurato: **2574 test raccolti, zero errori di
collection**, corsa completa **2568 passed / 4 failed / 1 skipped in 273 s**.

E una misura che corregge un ipotesi della voce `s2`: **non ci sono test
patologicamente lenti**. I piu pesanti sono `test_inference_wave1` (13,5 s),
`test_inference_wave2` (8,9 s), `test_model_hub_scores` (5,2 s),
`test_protocol_bench` (4,1 s), `test_llama_runtime` (3,2 s) e `test_gguf_compatibility`
(2,0 s): in tutto ~40 s su 273, il 15%. La suite e lunga perche e **larga**
(2574 test, ~106 ms l uno) e perche ogni file importa uno stack pesante; marcare
i lenti guadagnerebbe un decimo del tempo, mentre il sottoinsieme per area ne
guadagna il 90% - ed e gia la regola di `AGENTS.md`.

(Prima di questa correzione, il conteggio era: **2511 test raccolti**
(«2511 tests collected in 1.89s»), contro i 1784 dichiarati da `STATO_HARNESS.md`.

Baseline di questa macchina, misurata il 23 settembre sulla suite completa:
**2506 passed, 4 failed, 1 skipped, 140 subtests in 179 s**. I quattro fallimenti noti non
toccano il lavoro di oggi, e per la CI vanno o corretti o dichiarati: `test_network_ssl_config`
(manca `cryptography`), `test_provider_tools::test_la_grammatica_e_compilabile`
(`compile_for_llama_cpp` in `core/engine/grammars.py` non compila in questo ambiente),
`test_risposta_bilingue` (un `<think>` esplicito non viene tolto da `_clean_all_tags` in
`core/ai_providers.py`), `test_scheda_progetto` (un ruolo di `Ruoli/` che la scheda non
dovrebbe nominare). Un numero di partenza conosciuto e’ cio’ che rende utile un cancello.


---

## La regola per scrivere i task, imparata sbagliando

Il ventaglio di oggi ha chiuso **una voce su due**. Quella riuscita —
l'errore del tool nascosto — l'agente l'ha fatta al terzo tentativo, in venti
turni, esattamente come chiesto: la riga 208 di `ChatToolActionItem.jsx` ora
mostra l'errore sul ramo fallito.

Quella fallita non è colpa dell'agente. **Il suo lavoro era giusto** — ho
riletto il diff: toglieva lo stadio 1 di `_clean_all_tags` e aggiungeva due
casi negativi. Due cose sono andate storte, e **tutte e due erano mie**:

1. **Stavo modificando lo stesso file mentre lui ci lavorava.** Il suo branch
   non si è più potuto applicare. Chi lancia un ventaglio non deve toccare i
   file che ha appena assegnato.

2. **Il mio task partiva da una premessa non verificata.** Avevo scritto che
   «il testo che arriva a `_clean_all_tags` contiene SOLO il canale della
   risposta». È vero per la chat in streaming; **non** per
   `assistant_orchestrator` e `execute_loop`, che chiamano `call_ai_model` e
   vedono i tag grezzi. Togliere lo stadio 1 come lo avevo chiesto avrebbe
   lasciato il ragionamento nella risposta su quei due percorsi.

> **Regola:** prima di scrivere in un task «questo dato arriva sempre così»,
> si cercano **tutti** i chiamanti e si guarda cosa passano davvero. Una
> premessa sbagliata nel task diventa un difetto nel codice, e l'agente non
> ha modo di accorgersene: gli abbiamo detto noi che era vero.

La chiusura corretta era un passo più in là, e l'ho fatta: c'era una **quarta**
implementazione della stessa separazione, `parse_thinking_and_content` in
`core/ai_providers.py`, con lo stesso difetto delle altre tre. Ora delega al
router condiviso, e solo allora lo stadio 1 è diventato davvero ridondante.

---

## Cosa ho già fatto, per non rimetterlo in coda

| | |
|:---|:---|
| Il canale ragionamento/risposta | tre cause, una implementazione sola per chat e dev mode |
| `thinking` dalla configurazione al template | era dichiarato fino in fondo e non lo passava nessuno |
| La chat può mostrare HTML e JSX | il catch-all cancellava i tag da tutta la risposta |
| La diagnosi di autocorrezione | «non compila» non vuol più dire «qualcosa è andato storto» |
| `server_health` | non cammina più le cartelle di build |
| `edit_file` | dice dove ha sbagliato, e riallinea quando è solo indentazione |
| La guardia sui cicli | riconosce il ciclo a due e tre mosse |
| Il controllo di sintassi JSX | parser vero, zero falsi allarmi su 206 file |
| La quarta implementazione della separazione | `parse_thinking_and_content` delega al router |
| Lo stadio 1 di `_clean_all_tags` | tolto, ora che ogni chiamante passa dal router |
| L'errore del tool nel pannello | fatto dal ventaglio, voce chiusa al terzo tentativo |
| La via d’uscita per spezzare un task | proposta pronta a metà turni, `queue_id` come parametro del ciclo |
| La ricerca che trovava sé stessa | `var/`, `store`, `logs` fuori dall’albero cercato, ordine di visita scelto |
| Le finestre di lettura | lo stato nomina il buco, il rifiuto porta la chiamata pronta |
| La mappa dei simboli | `find_symbol` nel ruolo Coder, indice dei file citati nello stato |
| I turni nello stato | «19 di 30, nessuna scrittura, la metà era il turno 15» |
| La ripetizione non è progresso | una ricerca identica non azzera più i turni improduttivi |
| L’auto-loop dell’interfaccia | manda la differenza, non la stessa stringa identica |
| `max_turns` | esposto dalla richiesta, non più 30 fisso lato server |
