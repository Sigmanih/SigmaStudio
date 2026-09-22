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

### 1.1 · Il task troppo grande non viene spezzato · **alto**

Nove run su nove hanno consumato **tutti** i turni disponibili. Due esiti
ricorrenti: «nessuna modifica prodotta entro i turni disponibili» e «lavoro
prodotto ma non dimostrato».

`queue_add` con `replaces` esiste ed è documentato nel prompt del ventaglio —
e nessun agente lo ha usato. Il motivo probabile è che la via d'uscita è
descritta in fondo a un prompt lungo, dopo l'obiettivo e le avvertenze, e
chiede di comporre a mano un JSON con quattro campi annidati.

Va reso imboccabile: quando un agente ha speso metà dei turni senza scrivere
niente, il ciclo deve **dirglielo e proporgli la forma già pronta** da
riempire, come fa il turno di recupero con la scrittura forzata.

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
