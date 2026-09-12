# Stato dell'Harness · 12 settembre 2026 (rev. 5)

Valutazione dell'harness dell'agente nel kernel: cosa regge, cosa no, e come si
guida un lavoro grande da dentro Sigma Studio.

| | |
|:---|:---|
| Test verdi | **1655** |
| Build frontend | verde (~0,9 s) |
| `npm run lint:undef` | 0 riferimenti non definiti |
| Punti dell'audit tecnico | 11 / 11 chiusi |
| Difetti trovati **dopo** la chiusura dell'audit | 29, tutti nell'integrazione |
| Ventaglio parallelo, prova dal vivo | da 0 voci su 6 a **2 su 2**, in 8 e 9 turni |
| Banco sul protocollo dei tool | Qwen 27B **100/100**; Ornith 35B e gemma 12B **70/100** |
| Voto del flusso di squadra | **8,5 / 10** (era 6) |

---

## 1. Cosa c'è, e regge

**Il ciclo.** Multi-turno con ledger di sessione persistente, cancello di
completamento che pretende prove ancorate a fatti, recupero dallo stallo in tre
stadi distinti, compattazione della cronologia con memoria decisionale.

**I ruoli come dato.** `config/roles.json` si sovrappone ai predefiniti campo per
campo. La policy dei tool è un'intersezione fra profilo operativo ed elenco del
ruolo, e il prompt documenta soltanto i tool che quel ruolo può davvero usare.

**Quattro reti di sicurezza.** Revisione del diff per singola scrittura;
revisione dell'intero lavoro di un run in una volta; isolamento in worktree git
con checkpoint di turno e rollback manuale; conservazione del lavoro su un branch
quando l'obiettivo non viene chiuso.

**Il lavoro grande.** Una coda persistente che sopravvive ai run, consumata da N
agenti in parallelo, ognuno nel proprio worktree. Il lavoro approvato non compare
nell'albero: finisce su `dev` e si accetta con una pull request.

**Il contorno.** Prefix cache multi-slot per ruolo, finestra di contesto reale,
tool-calling nativo dove il provider lo supporta, verifica strutturata dei test,
traduzione a lotti con i segnaposto protetti, pubblicazione dei moduli nel loro
repository.

---

## 2. Cosa ha continuato a rompersi, e perché conta

Le 11 lacune dell'audit erano chiuse, con i loro test verdi. Rileggendo **i punti
in cui i moduli nuovi incontrano il ciclo** — e poi provandoli su un repository
vero — ne sono usciti altri diciassette. Nessuno era visibile dai test dei singoli
moduli; sette si sono visti solo facendo girare il sistema davvero.

| Difetto | Effetto |
|:---|:---|
| `isolate_worktree` dichiarato e mai passato | L'intero isolamento non era accendibile da alcun percorso reale |
| Chiusura del run fuori da un `finally` | Ogni stop lasciava un worktree e un branch orfani |
| `git branch -D` a ogni obiettivo non raggiunto | Trenta turni di lavoro buono cancellati per l'ultimo passo mancante |
| `apply_to_main` con base sbagliata e senza l'ultimo turno | La modifica che *chiudeva* l'obiettivo non arrivava all'albero principale |
| `shutil.copy2` nella sincronizzazione moduli | Una volta su quattro il commit veniva saltato in silenzio |
| Prova a vuoto che rispecchiava davvero | Il pannello diceva «tutto allineato» su lavoro mai pubblicato |
| `manifest.backend.handlers_module` mai letto | Sbagliato in 7 moduli su 15, e nessuno se n'era accorto |
| `diff_from_main` con base sbagliata e senza i file nuovi | Chi rivede avrebbe approvato una cosa diversa da quella applicata |
| Revisione di fine run confusa con quella per scrittura | Le scritture si fermavano una per una, scadevano, e alla fine non restava niente da rivedere |
| `sigma_audio_studio` senza manifest | Un modulo che gira e non sta in nessun repository, saltato in silenzio |
| `rollback()` mai chiamata | Il modulo prometteva un ripristino che nessun codice manteneva |
| `mcp_hub` → `sigma_mcp_hub` in `registry.js` | Una mappa che promette un modulo inesistente: scheda vuota |
| Prova richiesta e non riconosciuta | Il sistema indicava il comando da eseguire e poi non lo contava |
| Guardia anti-ripetizione dopo un piano corretto | Chi faceva ciò che gli era stato chiesto non poteva riprovare |
| Chiave `modified_files` inventata | Il resoconto diceva «nessuna modifica» su run che avevano scritto il file giusto |
| `deliver` dichiarato e ignorato nel ventaglio | Chiedere «non consegnare» non aveva alcun effetto |
| Profilo operativo mai spedito dall'interfaccia | Il tetto ai tool esisteva e non lo si poteva alzare |

### Primo schema: scritto, testato, scollegato

**Sette volte.** `is_tool_allowed`, i profili operativi, il binding del modello
per ruolo, l'isolamento in worktree, il campo `handlers_module`, `deliver` —
dentro codice scritto in questa stessa sessione — e la **scelta del profilo
operativo**, che il kernel accettava e nessuna interfaccia spediva. L'ultima è
uscita scrivendo questa stessa pagina: stavo per documentare come si usa una
cosa che non si poteva usare. Ogni volta i test erano verdi, perché chiamavano
la funzione direttamente.

> Un test che non parte da un percorso raggiungibile dall'utente non dimostra che
> la funzionalità esista.

`tests/test_no_dead_wiring.py` cammina i parametri del ciclo *e del ventaglio* e
pretende che ognuno sia passato da un chiamante di produzione. Va esteso a ogni
nuovo punto d'ingresso, non aggirato.

### Secondo schema: successo dichiarato, lavoro perduto

**Cinque volte** il sistema ha riportato successo mentre perdeva o negava
lavoro: il branch cancellato, il commit saltato, la prova a vuoto che si
autoconsumava, la revisione di fine run che annullava ciò che doveva mostrare, e
il resoconto che negava file scritti davvero. In un sistema che serve a non
perdere lavoro, il fallimento silenzioso è la modalità di guasto peggiore.

Dove due fonti si contraddicono — il mirror dice «cambiato», git dice «no» — il
sistema ora si ferma e lo dice.

### Terzo schema: il sistema che si contraddice

È il più insidioso, perché la colpa sembra del modello. Due casi, entrambi
trovati facendo girare il ventaglio su un repository vero:

- il cancello chiede una verifica, il prompt indica **quale**, l'agente la
  esegue con successo, e il cancello non la riconosce;
- il cancello dice «chiudi i task del piano», l'agente li chiude, e la guardia
  anti-ripetizione gli impedisce di riprovare.

In entrambi i casi l'agente aveva fatto esattamente ciò che gli era stato
chiesto. Prima delle correzioni: 6 voci fallite su 6. Dopo: 2 su 2, in 8 e 9
turni.

### La lezione sui test

Il difetto della chiave `modified_files` aveva un test che avrebbe dovuto
vederlo, e non lo vedeva: usava uno snapshot **inventato**, con una chiave che
nel ledger non esiste. Era il finto a nascondere il difetto.

> Quando un test costruisce a mano il dato che il codice riceverà, prova che il
> codice funziona su un dato immaginario.

I test di quel punto costruiscono ora uno snapshot vero, con un `DevSessionLedger`
vero.

---

## 3. Valutazione

**Regge**: un obiettivo circoscritto con verifica eseguibile, e — da questo giro
— un lavoro spezzato in voci indipendenti, eseguito in parallelo, rivisto una
volta sola e consegnato con una pull request.

**Non regge da solo**: la parte difficile resta **spezzare bene il lavoro**.
Il ventaglio consuma una coda; deciderne le voci richiede di aver guardato il
progetto, ed è il primo compito di chi pianifica — persona o agente.

**Il rischio che resta**: l'harness ha ormai molte parti che si incontrano, e
tutti i difetti recenti stanno negli incontri, non dentro i pezzi. Una nuova
capacità non è finita quando i suoi test passano: è finita quando l'ha
attraversata un run vero.

---

## 3bis. Quale modello, e come lo si e' deciso

I benchmark che avevamo misuravano domande e risposte. E' un'altra abilita': un
modello puo' prendere 80 su 100 e non saper chiudere un ciclo di venti turni.
`core/harness/protocol_bench.py` misura quella — dieci prove per scenario, tutte
su fatti osservabili nel transcript, con il risultato finale controllato sul
disco.

Scenario `file_nuovo`, 9 settembre 2026:

| modello | quiz | **protocollo** | turni | tempo |
|:---|---:|---:|:---|---:|
| **Qwen3.8-27B-Q4_K_S** | 78 | **100 / 100** | 11, chiude | **83 s** |
| Ornith-1.0-35B-Q4_K_M | 73 | 70 / 100 | 14, esauriti | 86 s |
| gemma-4-12B-Q4_K_M | 79 | 70 / 100 | non chiude | > 300 s |

I due che perdono **producono il file giusto** e poi non lo dimostrano: non
eseguono la verifica, non dichiarano le prove. Sul quiz gemma vinceva di un
punto ed era 2,4 volte piu' veloce in token al secondo.

> I token al secondo non sono la metrica. Quella che conta e' il tempo fino alla
> chiusura, e un modello che emette il triplo dei token a parita' di velocita' e'
> piu' lento end to end. Nessun quiz lo dice.

E una scoperta di configurazione: **`coder` era l'unico ruolo senza binding** e
ricadeva sul modello attivo. La chat libera del Developer Studio e ogni
lavoratore del ventaglio ereditano quel ruolo — tutto il lavoro reale girava su
un modello che non chiude il ciclo. Ora tutti e cinque i ruoli usano Qwen 27B, e
`config/roles.json` porta scritto perche'.

---

## 4. Come si segue un lavoro come questo da dentro Sigma Studio

Tutto quello che è stato fatto qui a mano si guida dal **Developer Studio**.
Il percorso, nell'ordine:

**1. Decidere come spezzare il lavoro.** Nella chat dell'agente, mettendo il
selettore su *Sola Lettura* — è un tetto sopra i tool del ruolo, quindi
l'agente esplora senza poter toccare niente: «elenca i file di ogni modulo che
contengono stringhe visibili all'utente, uno per riga». Ne esce l'elenco che
diventerà la coda. Questo passo non si delega al ventaglio: è la parte che
richiede di aver guardato.

**2. Riempire la coda.** Pannello **LAVORO IN PARALLELO** nella colonna sinistra:
obiettivo generale in alto, una voce per riga sotto, *Aggiungi alla coda*. Le
voci si accumulano su disco: si può chiudere tutto e riprendere domani.

**3. Dire come si dimostra il lavoro.** È il passo che vale tre run per voce.
Ogni voce può portare con sé il comando che la prova — `python tools/check_i18n.py
--file X` — e allora l'agente sa cosa eseguire e il cancello lo riconosce. Senza,
l'agente deve trovarsela da solo, e a volte non ci riesce.

**4. Avviare.** Si sceglie quanti agenti in parallelo (2 è il default: oltre, la
banda verso i pesi del modello diventa il collo di bottiglia) e si preme *Avvia*.
La barra avanza, le voci si chiudono una per una, ogni riga dice quale
lavoratore l'ha presa. *Ferma* interrompe: ciò che è stato fatto resta fatto.

**5. Rivedere.** Con **Revisione run** acceso, ogni agente si ferma a fine lavoro
e mostra il diff completo di ciò che ha prodotto: *Applica* o *Scarta*. Scartare
non perde niente — il lavoro resta sul branch della sessione, e il pannello lo
dice. Se qualcosa è andato storto a metà, il rollback riporta indietro di N turni
(`/api/developer/run/rollback`).

**6. Accettare.** Il lavoro approvato non compare nell'albero: va su `dev` e si
apre una richiesta verso `main`. Si guarda con calma, anche due giorni dopo,
anche insieme a qualcun altro.

**7. Pubblicare i moduli.** Ciò che l'agente ha toccato dentro un modulo
appartiene al repository di quel modulo: il pannello **PUBBLICA MODULI** elenca
cosa cambierebbe e lo manda. Il commit locale è automatico, la pubblicazione la
si preme.

**Cosa guardare mentre gira.** Il monitor del lavoro mostra il ledger dell'agente
— cosa ha letto, cosa ha scritto, quali verifiche ha superato — cioè esattamente
ciò che il cancello di completamento userà per decidere. Quando una voce non si
chiude, la risposta è quasi sempre lì.

---

## 5. Cosa manca ancora, in ordine

### 1. L'estrattore delle stringhe e `check_i18n`
Il pezzo che trasforma «rendere impostabile la lingua» in una coda di voci
dimostrabili. La traduzione a lotti c'è, il cancello sa credere a un controllo di
progetto, ma il controllo che scandaglia i file e produce il catalogo va scritto.
È lavoro del compito, non dell'harness, e ora l'agente ha tutto per farlo.

### 2. La lingua deve arrivare anche al backend
Messaggi d'errore, risposte delle rotte, prompt dei ruoli. Fermarsi al frontend
lascia metà prodotto in italiano.

### 3. I campi `sidebar*` nei manifest sono metadata morta
La sidebar è scritta a mano in `Sidebar.jsx`. A differenza di `tabType` non c'è
nemmeno una mappa con cui confrontarli: o li consuma qualcuno, o vanno tolti.

### 4. `gh` o un `GITHUB_TOKEN`
Senza, il branch viene spinto e la richiesta si apre a mano con un click. Con,
sparisce anche quel passaggio.

### 5. P2P
Resta per ultimo, come deciso.

---

## 6. Revisione del 12 settembre: dal piano alla sandbox

La domanda di partenza era diversa dalle precedenti: non «cosa si rompe», ma
**come si scrive un task, chi lo scrive, e come lo si segue**. Guardando quel
percorso da capo sono usciti altri sette punti. Tre erano difetti attivi, e il
primo è il più grosso trovato finora.

### Il piano dell'architetto perdeva tre campi su cinque

Il ruolo `architect` chiede — e il prompt lo dice esplicitamente — un piano con
*file coinvolti, dipendenze da altri task, ruolo consigliato*. Il
normalizzatore del tool `pipeline` teneva `id`, `title`, `status` e scartava
tutto il resto:

```
in:  {"id": "t2", "title": "Estrai le stringhe", "role": "coder",
      "description": "Usa tools/estrai_stringhe.py", "depends_on": ["t1"]}
out: {"id": "t2", "title": "Estrai le stringhe", "status": "pending"}
```

Tre conseguenze che si sommavano: **ogni task finiva al Coder** (il ripiego di
`_build_pipeline_from_architect`), **il grafo non aveva archi** — tutto sempre
pronto — e **l'istruzione del task era il suo titolo**, una riga.

Sotto c'è `next_role_batch()`, che esiste per raggruppare i task per ruolo
senza violare le dipendenze, e che ha centoventi righe di test. Girava su un
grafo che nella realtà era sempre senza archi e sempre di un ruolo solo.

> È la quarta volta che uno stesso test costruisce a mano il dato che il codice
> riceverà. `tests/test_role_scheduling.py` fabbricava i `TaskNode` con `role`
> e `depends_on`: provava che lo scheduler funziona su un dato che non
> riceveva mai.

`tests/test_plan.py` parte ora **dalla chiamata del tool** e arriva al grafo
eseguito, senza costruire niente in mezzo.

### La cartella di lavoro non era un confine

`resolve_workspace_path` prometteva nel nome di risolvere i percorsi *dentro*
la radice. Con il workspace su un progetto esterno, due vie su tre uscivano:

| percorso chiesto | prima |
|:---|:---|
| `C:/…/Sigma_Studio/config/config.json` | passava — assoluto, restituito tale e quale |
| `x/../../Sigma_Studio/config/config.json` | passava — `normpath` non ricontrollava |
| `../Sigma_Studio/config/config.json` | bloccato |

Da lì si leggeva `config/config.json`, dove stanno le credenziali. I tool di
file avevano una staccionata bucata; **il terminale non ne aveva nessuna**, e
non può averne una scritta in Python: `cd ..` è una riga.

### Nessuno poteva depositare il lavoro, e il lavoro non sapeva aspettare

La `WorkQueue` — quella che sopravvive ai run e regge il ventaglio — si
riempiva solo da `POST /api/harness/queue`. Un agente che aveva appena
guardato il progetto e capito come spezzare il lavoro non aveva dove
scriverlo. E le voci non sapevano esprimere un ordine: sulla Biblioteca le
voci 06 e 07 dipendevano dalla 05, e l'unica alternativa era la fila indiana
con un lavoratore solo.

### Cosa è stato fatto

| | |
|:---|:---|
| `core/harness/plan.py` | Il piano arriva intero. Dipendenze impossibili — id inesistenti, cicli — tolte **dicendo cosa si è tolto**: un piano corretto di nascosto insegna al modello che andava bene |
| `FuoriDalWorkspace` | Un percorso che esce viene rifiutato, con il confronto sui percorsi reali (un collegamento non è una scorciatoia). Il rifiuto torna all'agente come risultato leggibile, non come eccezione che uccide il turno |
| `core/harness/resoconto.py` | Cosa è stato fatto, come funziona, come lo sappiamo — **dai fatti del ledger**. Due forme: il consuntivo di fine run (e corpo della pull request) e il diario, un pezzo per volta mentre succede |
| `queue_add` | L'Architect riempie la coda. Nello schema, nella policy, nel prompt e fra i suoi tool |
| `depends_on` nella coda | Chi dipende da una voce fallita diventa `blocked` e dice da cosa; il lavoratore che non trova niente non se ne va se un altro sta lavorando a ciò che lo sbloccherà |
| `core/progetti.py` | `data/progetti/` come indirizzo di sviluppo, spostabile. E `radice_pericolosa()`: dischi, cartella utente e cartelle di sistema non si danno a un agente |
| `core/harness/esecutori.py` | La cucitura per la sandbox: host oggi, contenitore quando Docker c'è |

### Sul resoconto: perché dai fatti e non dal modello

Un modello sa scrivere «ho verificato tutto» senza aver eseguito niente, e su
questo progetto lo ha già fatto. Ogni riga del resoconto viene da qualcosa che
è successo e che qualcuno ha registrato mentre succedeva. Un comando che il
ledger non ha riconosciuto come verifica non compare fra le prove; un run che
ha scritto senza verificare si legge **«il lavoro non è dimostrato»**.

È anche ciò che finisce nel corpo della pull request. Prima elencava obiettivo
e nomi di file: chi doveva accettare non trovava scritto da nessuna parte quali
criteri fossero stati accettati né quale comando li avesse dimostrati — le due
cose che si vogliono sapere prima di premere merge.

---

## 7. Docker: il disegno, e cosa costa davvero

**Il contenitore non è una comodità: è la metà mancante del confinamento.** Un
recinto sui percorsi scritto in Python è aggirabile da qualunque comando di
shell. E l'obiettivo dichiarato — che i modelli possano installare, compilare,
rompere e ricominciare senza che nessuno debba fidarsi — è lo stesso problema
visto dall'altro lato.

**Stato della macchina**, verificato: `docker` non è installato, **e WSL non
c'è**. Docker Desktop su Windows 11 richiede WSL2 o Hyper-V: è un'installazione
vera, con riavvio. Non è `pip install`.

**La cucitura è `core/harness/esecutori.py`**, dietro al tool `terminal` — che
è l'unico punto da cui passano i comandi dell'agente. I tool di file
continuano a scrivere sul disco dell'host, e il contenitore monta la stessa
cartella: stessi byte, due viste. Così il diff, i backup, il cancello di
revisione e `apply_to_main` continuano a funzionare senza sapere che esiste un
contenitore.

Quattro scelte che non sono dettagli, tutte già verificate nei test **senza
Docker installato** — perché ciò che si può controllare a freddo è come viene
costruita la riga di comando, ed è proprio quella a distinguere una sandbox da
un modo complicato di eseguire un comando:

- **si monta il worktree, non il repository** — altrimenti i lavoratori
  paralleli tornano in comunicazione proprio dove l'isolamento li separa;
- **`config/` non entra mai** — è il punto dell'operazione;
- **l'ambiente è una lista bianca**, non `dict(os.environ)`;
- **la rete è spenta**, con deroga esplicita: senza, `npm install` fallisce e
  l'idea sembra sbagliata quando invece è solo stretta.

E la regola che conta più di tutte: **se il contenitore non c'è, si dice**. Mai
ripiegare in silenzio sull'host — chi ha acceso la sandbox crederebbe di essere
protetto senza esserlo, ed è peggio che non averla. Per lo stesso motivo
`stato_sandbox()` riporta `active` vero solo se la sandbox è chiesta **e**
possibile.

**Cosa resta da fare**, quando WSL2 sarà installato: le immagini per progetto
(un `node:22` per il frontend, un `python:3.12` per il backend, dichiarate
accanto al progetto), la cache dei volumi — altrimenti ogni voce della coda
reinstalla tutto — e il `verify` della coda, che deve girare dalla stessa parte
del lavoro.

**Il prezzo onesto**: un errore in più da diagnosticare. «Passa sull'host e
fallisce nel contenitore» è la frase che si dirà spesso, ed è per questo che il
risultato del tool `terminal` porta ora il campo `dove`.

---

## 8. Cosa manca, dopo questo giro

1. **Docker installato** (WSL2 o Hyper-V), e le immagini per progetto.
2. **Il comando del terminale resta senza recinto** finché la sandbox non è
   accesa: il confine sui percorsi copre i tool di file e la `cwd`, non ciò che
   un comando fa dopo essere partito.
3. **Il consuntivo non arriva al ventaglio**: `run_report` è per singolo run.
   Un lavoro da cinquanta voci merita un resoconto complessivo.
4. **Le dipendenze della coda non attraversano i worktree**: una voce che
   dipende da un'altra vede il lavoro della prima solo dopo la consegna.
5. I punti 1-4 della sezione precedente restano: `check_i18n`, la lingua nel
   backend, i campi `sidebar*`, `gh`.
6. **P2P**, per ultimo.

---

## 9. Il flusso di squadra, esaminato riga per riga · 12 settembre 2026

Non «cosa si rompe» ma: **il percorso dei cinque ruoli è coerente,
ispezionabile, testato, completo e spiegato?** Sei criteri, un voto per
ciascuno, e i difetti trovati sono nove — tutti nei punti in cui le parti si
incontrano, nessuno dentro un pezzo.

### Il difetto più grosso: la squadra lavorava senza rete

`generate_with_role` dichiarava `isolate_worktree`, `review_run`,
`review_writes` e `verify_command`. Li passava la chat a un agente solo.
**L'orchestratore non ne passava nessuno** — cioè l'unico posto dove cinque
ruoli lavorano di fila senza che nessuno guardi era anche l'unico senza
isolamento, senza revisione del diff e senza la prova che il task stesso
dichiarava.

È la quinta volta con la stessa firma: *scritto, testato, scollegato*. La
guardia `tests/test_no_dead_wiring.py` copriva il ciclo e il ventaglio, non
questo ingresso. Estesa a `generate_with_role` e a `execute_goal`, ha trovato
il difetto al primo giro.

> Una guardia che non copre tutte le porte non è una guardia incompleta: è una
> guardia che dà l'impressione di esserci.

E ha trovato anche che **due di quei quattro parametri erano sul livello
sbagliato**. L'unità dell'isolamento non è il ruolo: è l'obiettivo. Un worktree
per ruolo darebbe cinque alberi che non si vedono fra loro, e il Tester non
troverebbe i file che il Coder ha appena scritto — la squadra smetterebbe di
essere una squadra. Ora `execute_goal` apre **un albero solo** e lo fa ereditare
a tutti e cinque; `review_writes` e `verify_command` restano per ruolo, perché
lì l'unità giusta è la scrittura e il task.

### Gli altri otto

| # | Difetto | Perché conta |
|:--|:---|:---|
| 2 | Due sistemi di correzione che non si conoscono | `_feedback_loop` contava le proprie mosse in modo separato dal `Bilancio`: insieme potevano spendere il doppio del tetto che il primo credeva di far rispettare |
| 3 | Al Coder si passava **la prosa del Tester** | Gli stessi fatti erano nel ledger, misurati invece che raccontati |
| 4 | Ogni ruolo vedeva solo l'Architetto | `upstream_outputs` esisteva in cinque punti e in cinque portava la stessa cosa: cinque ruoli in parallelo che fingevano una fila |
| 5 | La ripianificazione non si faceva approvare | L'utente approva ogni fase, poi il piano gli viene sostituito dentro una fase già approvata |
| 6 | `verify` del task dichiarato e mai passato | Il piano diceva come si dimostra quel task, e chi lo eseguiva doveva inventarselo |
| 7 | Il bilancio non si azzerava fra un obiettivo e l'altro | L'orchestratore vive per sessione: il secondo obiettivo partiva con le correzioni già spese |
| 8 | La consegna era un prompt con dentro quattro comandi git | Mentre il resto del sistema va branch → `dev` → pull request, come da regola |
| 9 | Il resoconto finale erano tre frasi scritte a mano | Identiche a ogni run, accanto a un elenco di file: non dicevano quali criteri fossero stati accettati né quale comando li avesse dimostrati |

Tutti e nove corretti, con i loro test.

### Due cose che sembravano difetti e non lo erano

Le scrivo perché **misurare prima di intervenire** è metà del mestiere, e
tutte e due le avrei «aggiustate» a occhio.

**Il blocco di stato condiviso non esplode.** Sessanta file toccati e quaranta
comandi eseguiti producono 2 794 caratteri — circa 700 token. Il ledger tronca
già la propria resa: il problema che stavo per risolvere non esiste.

**`next_role_batch` non ottimizza un costo nullo.** Avevo pensato: i cinque
ruoli usano lo stesso modello, quindi non c'è nessun cambio di pesi da
ammortizzare. Sbagliato — il guadagno non è il modello, è **la cache di
prefisso KV**, che è chiavata sul ruolo (`cache_slot = f"role:{...}"`) perché
il system prompt è costante dentro un ruolo e diverso fra ruoli. Con
`-np 1` c'è un solo slot, quindi cambiare ruolo sfratta il prefisso
precedente: raggruppare i task per ruolo è **esattamente** la mossa giusta, per
una ragione diversa da quella scritta nel commento. Circa 2 500 token di
prompt per task che non vengono rielaborati.

### Il voto

| criterio | prima | dopo | perché |
|:---|:---:|:---:|:---|
| **Coerente** | 4 | 9 | Era il lato debole: la squadra e il singolo agente facevano cose diverse in cinque punti. Ora condividono revisione, consegna, diagnosi e bilancio — le stesse funzioni, non due copie |
| **Ispezionabile** | 6 | 9 | Ogni mossa dell'autocorrezione è un evento con dentro **le prove su cui si è deciso**; il piano nuovo si fa approvare; il consuntivo viene dai fatti. Manca il resoconto d'insieme del ventaglio |
| **Testato** | 7 | 9 | 1 655 verdi, e soprattutto: i test partono dalla chiamata vera. Due che leggevano il **sorgente** invece dell'effetto sono stati riscritti — fallivano per uno spostamento che non cambiava niente |
| **Completo** | 5 | 7 | Docker non è installato: la sandbox è verificata a freddo, mai dal vivo. Il ventaglio non diagnostica i propri fallimenti. `get_parallel_groups` non lo chiama nessuno |
| **Commentato** | 9 | 9 | È la cosa migliore di questo progetto. Ogni decisione non ovvia porta il suo perché, e spesso il numero che l'ha decisa |
| **Perfetto** | — | no | Tre cose aperte, elencate sotto |

**Voto complessivo: 8,5 / 10.** Era 6 all'inizio di questa revisione.

Il punto e mezzo che manca non è un dettaglio: è **la prova dal vivo**. Il
flusso di squadra con isolamento e revisione non ha ancora attraversato un
obiettivo vero dall'inizio alla fine. Vale qui quello che vale sempre:

> Una capacità non è finita quando i suoi test passano. È finita quando l'ha
> attraversata un run vero.

### Le tre cose aperte, in ordine

**1. Il ventaglio non si corregge.** L'orchestratore diagnostica un fallimento
e sceglie fra riprovare, correggere, ripianificare e rinunciare. Il ventaglio —
che è il percorso per il lavoro **grande**, quello dove i fallimenti costano di
più — si limita a rimettere la voce in coda per tre volte identiche. La
diagnosi è già scritta e non dipende dalla pipeline: le serve solo uno snapshot
del ledger. Andrebbe chiamata anche lì, e il suo esito scritto nel `payload`
della voce, così il tentativo successivo parte sapendo cosa è andato storto.

**2. `get_parallel_groups()` non lo chiama nessuno.** Esiste, è testata, e
promette un parallelismo che dentro un obiettivo non è ottenibile: il motore è
uno solo e `generate_stream` prende un lucchetto di processo. O la si collega a
`parallel_slots > 1`, o va tolta — una funzione che promette una capacità
inesistente è peggio di una che manca.

**3. Docker.** WSL2 con Ubuntu adesso c'è; Docker Desktop no. Finché non c'è,
`stato_sandbox()` dice `active: false` con il motivo, ed è l'unica cosa onesta
da dire.


