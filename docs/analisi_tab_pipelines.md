# Analisi completa della tabella `pipelines`

## 1. Dove vive la definizione

La tabella **non** è definita da uno schema SQL classico, ma dal modello Python
`Pipeline` in `core/pipeline/models.py`, che gestisce il persistimento su
JSON (`data/pipelines.json`).

## 2. Campi della "tabella"

| Campo | Tipo | Vincolo / Note |
|---|---|---|
| `pipeline_id` | str | PK, generato come `uuid.uuid4()` |
| `name` | str | nome della pipeline, univoco nel progetto |
| `status` | str | stato corrente: `running`, `stopped`, `completed`, `failed` |
| `created_at` | datetime | istante di creazione |
| `updated_at` | datetime | ultimo aggiornamento |
| `tasks` | list[dict] | elenco dei task della pipeline, ciascuno con `task_id`, `name`, `status`, `result` |
| `config` | dict | configurazione della pipeline (parametri, risorse) |
| `metadata` | dict | metadati aggiuntivi (autore, versione, note) |
| `description` | str | descrizione opzionale |
| `created_at` | datetime | timestamp di creazione |
| `updated_at` | datetime | ultimo aggiornamento |
| `status` | str | stato (es. `running`, `stopped`) |
| `steps` | list[dict] | lista di step, ognuno con `step_id`, `type`, `config` |
| `report` | dict | report generato dal runner |

## 3. Query / operazioni su dati

- **Crea**: `Pipeline.create(...)` → scrive su JSON.
- **Lettura**: `Pipeline.from_json(...)`, `Pipeline.list_all()`.
- **Aggiornamento**: `pipeline.save()` → serializza su JSON.
- **Eliminazione**: `Pipeline.delete(pipeline_id)`.

## 4. API REST (endpoint)

In `core/pipeline/runner.py`:

| Metodo | Endpoint | Descrizione |
|---|---|---|
| POST | `/api/chat/pipeline/start` | Avvia un pipeline con SSE streaming |
| GET | `/api/chat/pipeline/status` | Stato corrente (in memoria o da checkpoint) |
| POST | `/api/chat/pipeline/stop` | Fermata |

## 5. Frontend React

- Componente `PipelinePanel` in `sigma_studio/src/modules/sigma_research_lab/`.
- Fetch su `/api/chat/pipeline/*` con `fetch` e gestione SSE per live update.

## 6. Integrazione con altri moduli

- **Harness**: `run_node()` (in `core/harness/node_runner.py`) esegue ogni nodo con lo stesso harness dell'agente sviluppatore: tool, ledger, cancello di completamento.
- **Chat**: il report finale viene restituito come messaggio nella sessione chat.
- **Moduli**: `sigma_research_lab` (Pipelines Lab & Dynamic Swarm) espone la UI e le route.
