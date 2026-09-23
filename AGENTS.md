# Convenzioni di Sigma Studio per gli agenti

Questo file e' letto dal Developer Studio e da qualsiasi harness compatibile
prima di ogni run, e le sue regole prevalgono sulle abitudini generali
dell'agente. Tienilo corto: e' un elenco di vincoli, non documentazione.
La specifica completa sta in `architettura.md`, che si legge con `read_file`
quando serve davvero.

## Struttura

| Percorso | Cosa contiene |
|:---|:---|
| `core/` | il kernel Python: paths, engine, chat, pipeline, mcp, module_loader |
| `core/modules/` | moduli opzionali installabili; il kernel non li importa mai |
| `core/harness/` | il runtime dell'agente: ciclo tool, ruoli, ledger, permessi |
| `core/modules/sigma_developer_lab/` | il Developer Studio: rotte, fasi, MCP di sviluppo |
| `sigma_studio/src/` | la SPA React 19 servita da Vite |
| `tests/` | la suite pytest del kernel |
| `data/` | lavoro dell'utente — **non cancellare mai nulla qui** |
| `config/` | configurazione di macchina, **contiene credenziali** |
| `var/` | stato di runtime: sessioni, indici, cache. Ricreabile |
| `store/` | pesi dei modelli e artefatti pesanti |

**La regola dell'architettura:** le dipendenze puntano verso il basso. Il kernel
non importa, non elenca e non nomina alcun modulo. Un modulo si aggancia da
solo con `register_routes()` / `register_mcp()`.

## Backend Python

- Python 3.10+. Niente stub `pass`, niente segnaposto lasciati da riempire.
- Gestisci sempre eccezioni, timeout e codici di ritorno: questo codice gira
  senza nessuno che guardi.
- Logging via `from core.logger import get_logger`, mai `print`.
- Percorsi con `pathlib.Path`, mai concatenazioni di stringhe.
- Il codice deve girare su Windows 11 **e** su Raspberry Pi 5 (aarch64, solo
  CPU, 8 GB di RAM). Niente assunzioni su CUDA, niente path assoluti Windows.

## Frontend React

- Solo React standard: `useState`, `useEffect`, `useCallback`. Niente librerie
  di componenti — **vietati** `@mui`, `antd`, `bootstrap`, `tailwind`.
- Icone esclusivamente da `lucide-react`.
- Gli stili stanno in `sigma_studio/src/styles/`, organizzati per livello
  (`01-base`, `02-layout`, `03-modules`). Niente CSS-in-JS.
- Le dipendenze gia' presenti e utilizzabili: `d3`, `three`, `mermaid`,
  `marked`, `prismjs`, `katex`, `react-simple-code-editor`. Non aggiungerne
  altre senza che sia stato chiesto.

## Harness nel kernel, IDE nel modulo

Il runtime dell'agente vive in `core/harness/`: ciclo tool, ruoli, ledger,
permessi, primitive di filesystem e terminale, instradamento fra provider.
E' kernel perche' serve a ogni modulo che debba far eseguire un compito a un
modello, non solo all'IDE.

Il Developer Studio e' il modulo installabile `core/modules/sigma_developer_lab/`
(ignorato da git, pubblicato sul repository dei moduli): tiene le rotte
`/api/developer/*`, il flusso a cinque fasi, i server MCP di git/lint/test e la
UI in `sigma_studio/src/modules/sigma_developer_lab/`.

**La direzione delle dipendenze:** il modulo importa `core.harness`, mai il
contrario. Se stai per scrivere `from core.modules...` dentro `core/`, ti sei
perso.

## Verifica

Un lavoro non e' finito finche' un comando non lo dimostra. Usa quello che
corrisponde a cio' che hai toccato:

```
python -m pytest -m harness -q                # il ciclo dell'agente: turni, ledger, prove, coda
python -m pytest -m mcp -q                    # hub MCP, assenso, assi, server di sviluppo
python -m pytest -m chat -q                   # conversazione: prompt, storia, risposte
python -m pytest -m motore -q                 # inferenza e modelli: engine, GGUF, hardware
python -m pytest -m moduli -q                 # moduli: EDA, KiCad, pipeline, i18n
python -m pytest -m base -q                   # il resto del kernel: percorsi, avvio, sistema
python -m pytest tests/test_<file>.py -q      # un solo file, quando basta
npm --prefix sigma_studio run lint:undef      # frontend: riferimenti non definiti (no-undef)
npm --prefix sigma_studio run build           # frontend, prova piu forte
python -c "import core.<modulo>"              # verifica minima di import
```

I lotti sono sette e stanno in `tests/lotti.py`: ogni file di prova appartiene a
esattamente uno, e `tests/test_lotti_della_suite.py` diventa rosso se qualcuno
ne aggiunge uno senza lotto. **Non serve la suite intera a ogni modifica**: si
esegue il lotto che si e' toccato, e i lotti vicini se la modifica li attraversa.
La corsa completa (`python -m pytest -q`, 2633 prove) si fa alla fine di un
gruppo di lavoro o quando la modifica e' critica. Le prove che caricano un
modello vero sono marcate `lento` e restano fuori dalla corsa predefinita: si
chiedono con `python -m pytest -m lento -q`, o tutte insieme con
`python -m pytest -m "lento or not lento" -q` (attento: `-m ""` NON annulla
`addopts`, seleziona zero prove).

**Non eseguire la suite con il server acceso.** L'app gira sulla porta 8000 e
parecchie prove la aprono o la interrogano (`test_eda_lab`, `test_sigma_network`,
`test_visual_console_errors`, `test_inference_wave2`): la prima che passa non
trova la porta libera, e a meta' lavoro la sessione muore — con l'hub MCP che va
con lei. Il server si spegne prima, o si verifica con un import.

Il server di sviluppo si avvia con `python sigma_server.py` sulla porta 8000.
Non avviarlo per verificare una modifica al backend: un import basta ed e'
istantaneo.

### Quando la prova non e' una suite di test

Certi lavori non si dimostrano con pytest. Che ogni chiave di traduzione esista
in ogni lingua, che nessun modulo dichiari una rotta inesistente, che nessun
file superi un limite: sono controlli scritti apposta, e per contare come prova
devono dire **quanti elementi hanno esaminato**. Un controllo che non ha
guardato niente esce con codice zero esattamente come uno che ha guardato tutto
senza trovare nulla.

Fai emettere al tuo controllo una riga come questa, l'ultima dell'output:

```
SIGMA-CHECK {"check": "i18n", "checked": 214, "problems": 0}
```

`checked` e' il numero di elementi esaminati, `problems` quelli con un problema.
L'harness la legge: con `checked` a zero, o senza la riga, il controllo **non**
vale come verifica e il cancello di completamento resta chiuso. Esci con codice
diverso da zero quando `problems` non e' zero.

## Lingua e stile

- Rispondi in italiano. I commenti nel codice: in italiano quelli nuovi,
  lascia in inglese quelli esistenti se stai modificando un file inglese.
- I commenti spiegano **perche'**, non cosa: il cosa e' gia' scritto nel codice
  sotto. Un commento che ripete la riga successiva va tolto, non aggiornato.
- I messaggi di commit sono in italiano, all'imperativo.

## Cose da non fare

- Non toccare `data/`, `config/`, `store/` senza che sia stato chiesto
  esplicitamente.
- Non riscrivere un file intero con `write_file` quando basta `edit_file`:
  la riscrittura perde tutto cio' che non hai riletto.
- Non aggiungere dipendenze a `requirements.txt` o a `package.json` di tua
  iniziativa.
- Non creare file di riepilogo, di stato o di appunti a fine lavoro: il
  riepilogo va scritto nella risposta all'utente, non su disco.
