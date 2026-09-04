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
| `core/developer_studio/` | l'harness dell'agente sviluppatore |
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

## Il Developer Studio esiste in due copie

`core/developer_studio/` e' il sorgente tracciato: si modifica quello, e i test
girano su quello. `core/modules/sigma_developer_lab/` e' la copia installata
(ignorata da git) che il module loader importa **davvero** a runtime.

Dopo ogni modifica al sorgente:

```
python scripts/sync_developer_lab.py
```

Saltarlo significa passare tutti i test su un file che il server non esegue.
Il test `tests/test_developer_lab_sync.py` fallisce se le due copie divergono.
Lo stesso vale per il frontend del modulo, che vive solo in
`sigma_studio/src/modules/sigma_developer_lab/`.

## Verifica

Un lavoro non e' finito finche' un comando non lo dimostra. Usa quello che
corrisponde a cio' che hai toccato:

```
python -m pytest tests/ -q                    # kernel Python
python -m pytest tests/test_<modulo>.py -q    # una sola area
npm --prefix sigma_studio run lint            # frontend
npm --prefix sigma_studio run build           # frontend, prova piu forte
python -c "import core.<modulo>"              # verifica minima di import
```

Il server di sviluppo si avvia con `python sigma_server.py` sulla porta 8000.
Non avviarlo per verificare una modifica al backend: un import basta ed e'
istantaneo.

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
