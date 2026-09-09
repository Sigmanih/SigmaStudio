# Stato dell'Harness · 9 settembre 2026 (rev. 3)

Valutazione dell'harness dell'agente nel kernel: cosa regge, cosa no, e come si
guida un lavoro grande da dentro Sigma Studio.

| | |
|:---|:---|
| Test verdi | **1369** |
| Build frontend | verde (~0,9 s) |
| `npm run lint:undef` | 0 riferimenti non definiti |
| Punti dell'audit tecnico | 11 / 11 chiusi |
| Difetti trovati **dopo** la chiusura dell'audit | 17, tutti nell'integrazione |
| Ventaglio parallelo, prova dal vivo | da 0 voci su 6 a **2 su 2**, in 8 e 9 turni |

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
