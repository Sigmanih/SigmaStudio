# 🧠 Analisi Completa: Miglioramento del Sistema Agenti in Sigma Studio

**Data:** 7/7/2026
**Versione:** 1.0
**Autore:** Sigma Code Architect

---

## Stato Attuale degli Agenti

| Aspetto | Stato | Valutazione |
|---------|-------|-------------|
| **Definizione** | 3 Modelfile in `manifesti/` (agente0, math1, code_architect) | ✅ Base solida |
| **Identità** | SYSTEM prompt nel Modelfile | ✅ Buono |
| **Parametri** | Temperature, top_p, num_ctx customizzati | ✅ Buono |
| **Chat** | 4 modalità (ask, plan, execute, complete) | ✅ Funzionale |
| **Routing** | Manifesto risolto per nome modello | ⚠️ Base |
| **Collaborazione** | Nessuna | ❌ Assente |
| **Memoria** | Solo cronologia sessione | ❌ Assente |
| **Orchestrazione** | Nessuna | ❌ Assente |
| **Performance** | Nessun tracking | ❌ Assente |

---

## 🟢 PRIORITÀ ALTA — Miglioramenti Immediati

### 1. Sistema di Agenti Collaborativi (Multi-Agent Orchestration)

**Problema:** Ogni agente lavora in isolamento. Non possono collaborare, delegare o passarsi il testimone.

**Soluzione:** Creare un **Agent Orchestrator** che gestisca la comunicazione tra agenti.

```
Utente → Orchestrator
           ├── Pianifica (agente0) → scompone il goal in sotto-task
           ├── Esegui Ricerca (math1) → produce teoremi/dimostrazioni
           ├── Scrivi Test (code_architect) → genera codice di verifica
           ├── Documenta (agente0) → produce whitepaper
           └── Verifica (math1) → convalida risultati
```

**Implementazione:**
- Nuovo endpoint `POST /api/chat/orchestrate` che accetta un goal e automaticamente:
  1. Analizza il goal e determina quali agenti servono
  2. Assegna sotto-task a ciascun agente in parallelo o sequenza
  3. Fa il merge dei risultati
  4. Gestisce conflitti tra output di agenti diversi

**File da creare/modificare:**
- `core/agent_orchestrator.py` — Nuovo modulo per orchestrazione
- `core/api_router.py` — Aggiungere endpoint `/api/chat/orchestrate`
- `sigma_server.py` — Importare e registrare handler

### 2. Registry degli Agenti (Agent Registry)

**Problema:** Non esiste un vero "catalogo" di agenti. Solo file `.md` in `manifesti/`.

**Soluzione:** Creare un sistema di registrazione strutturato con `agents_meta.json`.

```json
{
  "agents": {
    "agente0": {
      "name": "Sigma AI Architect",
      "version": "7.2",
      "manifesto": "manifesti/agente0.md",
      "specialization": "software_architecture",
      "capabilities": ["create_file", "edit_file", "run_test", "plan"],
      "models": ["agente0_gwen3_6_35b", "llama3.2"],
      "temperature": 0.55,
      "context_window": 16384,
      "status": "active",
      "usage_count": 0,
      "success_rate": 0.0,
      "allowed_topics": ["matematica", "informatica"],
      "parent_id": null
    },
    "math1": {
      "name": "Sigma Math Researcher",
      "version": "6.0",
      "manifesto": "manifesti/math1.md",
      "specialization": "mathematics",
      "capabilities": ["create_file", "run_test", "prove_theorem"],
      "models": ["math1", "deepseek-reasoner"],
      "temperature": 0.7,
      "context_window": 8192,
      "status": "active",
      "usage_count": 42,
      "success_rate": 0.85,
      "allowed_topics": ["matematica"],
      "parent_id": null
    }
  }
}
```

**Nuove API:**
- `GET /api/agents` — Lista agenti registrati con stato e statistiche
- `POST /api/agents/register` — Registra nuovo agente da Modelfile
- `POST /api/agents/assign` — Assegna agente a un topic specifico

**File da creare/modificare:**
- `agents_meta.json` — Nuovo file di registro
- `core/agent_registry.py` — Modulo di gestione
- `core/api_router.py` — Nuovi endpoint `/api/agents/*`
- `sigma_server.py` — Import handler

### 3. Memoria Persistente per Agenti (Agent Memory)

**Problema:** Ogni conversazione parte da zero. Gli agenti non ricordano scoperte, decisioni o pattern appresi in precedenza.

**Soluzione:** Implementare **memoria episodica e semantica** per ogni agente.

```
agent_memory/
├── agente0/
│   ├── long_term/          ← Conoscenza cumulativa
│   ├── episodic/           ← Cronologia sessioni
│   ├── decisions/          ← Decisioni passate con contesto
│   └── learned_patterns/   ← Pattern appresi dall'esperienza
├── math1/
│   └── ...
```

**Meccanismo:**
- Alla fine di ogni sessione, l'agente produce automaticamente un **memory snapshot** JSON
- Il snapshot include: cosa ha imparato, decisioni prese, pattern rilevanti
- All'inizio della sessione successiva, il sistema inietta la memoria rilevante nel prompt
- Limite: ultime N memory entries più recenti (per non saturare il contesto)

**File da creare/modificare:**
- `core/agent_memory.py` — Nuovo modulo
- `core/chat_handler.py` — Integrazione snapshot pre/post sessione
- `core/task_handler.py` — Aggiunta memoria alle notifiche

### 4. Sistema di Agenda e Prioritizzazione (Agent Task Queue)

**Problema:** I task in `tasks.json` non hanno assegnazione ad agenti specifici, deadline, dipendenze o priorità dinamica.

**Soluzione:** Estendere `tasks.json` con campi per orchestrazione agenti.

```json
{
  "titolo": "Dimostrare Lemma di Saturazione",
  "assigned_to": "math1",
  "depends_on": ["1779996110563"],
  "deadline": "2026-07-10",
  "priority_score": 0.85,
  "agent_mode": "execute",
  "max_iterations": 50,
  "context_files": ["data/matematica/01_congettura/teoria/lemma_base.md"]
}
```

**File da modificare:**
- `core/task_handler.py` — Nuovi campi task, routing per agente
- `sigma_studio/src/components/Dashboard.jsx` — UI per assegnazione agente

---

## 🟡 PRIORITÀ MEDIA — Miglioramenti Architetturali

### 5. Tool Calling / Function Calling Framework

**Problema:** Le azioni sono hardcoded in `execute_ai_actions()`. Ogni nuovo tipo di azione richiede modifiche al codice.

**Soluzione:** Creare un **plugin system** per le azioni degli agenti.

```python
class AgentTool:
    name: str
    description: str
    parameters: dict  # JSON Schema
    execute(params) -> dict

# Esempio: Registrazione di un tool
register_tool(AgentTool(
    name="web_search",
    description="Cerca informazioni sul web",
    parameters={"query": {"type": "string"}},
    execute=lambda params: search_web(params["query"])
))
```

**Vantaggi:**
- L'AI può scoprire dinamicamente quali tool sono disponibili (come ChatGPT plugins)
- Ogni manifest può dichiarare quali tool abilita
- I tool possono essere attivati/disattivati per agente

**File da creare/modificare:**
- `core/tool_registry.py` — Nuovo modulo
- `core/task_handler.py` — Refactoring `execute_ai_actions()` per usare tool registry
- `core/chat_handler.py` — Inject tool descriptions nel system prompt

### 6. Sistema di Validazione Output (Agent Output Validator)

**Problema:** L'output degli agenti non viene validato strutturalmente prima dell'esecuzione.

**Soluzione:** Validazione con **JSON Schema** e **contract testing**.

```python
AGENT_OUTPUT_SCHEMAS = {
    "code_architect": {
        "response": {"type": "string"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type", "path"],
                "properties": {
                    "type": {"enum": ["create_file", "edit_file", "delete_file"]},
                    "path": {"type": "string", "pattern": "^data/|^sigma_studio/"}
                }
            }
        }
    },
    "math1": {
        "response": {"type": "string"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"enum": ["create_file", "run_test", "edit_file"]}
                }
            }
        }
    }
}
```

**File da creare/modificare:**
- `core/output_validator.py` — Nuovo modulo
- `core/chat_handler.py` — Validazione prima di eseguire azioni

### 7. Profili di Esecuzione per Agente (Agent Execution Profiles)

**Problema:** Tutti gli agenti usano gli stessi parametri di default. Non c'è ottimizzazione per contesto.

**Soluzione:** Profili dinamici basati sul contesto operativo.

| Contesto | Temperature | max_tokens | num_ctx | Strategia |
|----------|-------------|------------|---------|-----------|
| **Codice** | 0.3 | 4096 | 8192 | Preciso, deterministico |
| **Matematica** | 0.4 | 8192 | 16384 | Ragionamento, dimostrazioni |
| **Ricreativo** | 0.9 | 2048 | 4096 | Creativo, divergente |
| **Analisi Dati** | 0.2 | 4096 | 32768 | Analitico, contesto ampio |
| **Ricerca Web** | 0.5 | 2048 | 4096 | Bilanciato, sintetico |

**File da modificare:**
- `core/ai_providers.py` — Aggiungere profili al resolver
- `core/chat_handler.py` — Applicare profilo prima della chiamata AI

### 8. Agent Templates / Scaffolding

**Problema:** Creare un nuovo agente richiede conoscenza della sintassi Modelfile.

**Soluzione:** Comando `POST /api/agents/create` con wizard.

```
Input: Nome, Specializzazione, Modello base, Temperature
Output: Modelfile generato + registrazione in agents_meta.json
```

**File da creare/modificare:**
- `core/agent_templates.py` — Template generator
- `core/api_router.py` — Nuovo endpoint

---

## 🔵 PRIORITÀ BASSA — Miglioramenti a Lungo Termine

### 9. Versionamento degli Agenti

- `manifesti/agente0_v7.2.md`, `manifesti/agente0_v8.0.md`
- Possibilità di confrontare performance tra versioni
- Rollback automatico su regressione

### 10. Agent Sandbox — Isolamento Esecuzione

- Ogni agente esegue in una sandbox Docker separata
- Limiti di risorse (RAM, CPU, disk) per agente
- Timeout per azione, non per intera sessione

### 11. Agent Audit Trail

- Log completo di ogni azione per agente (chi ha fatto cosa, quando, perché)
- Dashboard di audit per revisione umana
- Alert per pattern sospetti

### 12. Self-Improvement Loop

- L'agente analizza i propri errori passati e aggiorna il suo Modelfile
- Sistema di reward: azioni riuscite → rinforzo positivo
- Feedback loop: l'utente valuta l'output → l'agente si adatta

### 13. Agent Marketplace

- Catalogo condiviso di agenti predefiniti
- Template per dominio: matematico, linguista, biologo, legale, etc.
- Rating e recensioni

### 14. RAG (Retrieval-Augmented Generation) Integrato

- Ogni agente può indicizzare la knowledge base del topic assegnato
- Embedding + vettorializzazione dei file in `data/`
- Recupero automatico del contesto più rilevante prima di rispondere

---

## 📊 Piano di Implementazione Suggerito

| Fase | Cosa | Sforzo | Impatto | Priorità |
|------|------|--------|---------|----------|
| **1** | Agent Registry (`agents_meta.json`) | 1 giorno | Alto | 🔴 Alta |
| **2** | Memoria Persistente (memory snapshots) | 2 giorni | Alto | 🔴 Alta |
| **3** | Agent Task Queue (orchestrazione base) | 2 giorni | Alto | 🔴 Alta |
| **4** | Multi-Agent Orchestration | 5 giorni | Molto Alto | 🔴 Alta |
| **5** | Tool Calling Framework | 3 giorni | Medio | 🟡 Media |
| **6** | Output Validation (JSON Schema) | 1 giorno | Medio | 🟡 Media |
| **7** | Execution Profiles dinamici | 1 giorno | Medio | 🟡 Media |
| **8** | Agent Templates | 1 giorno | Basso | 🟡 Media |
| **9** | RAG Integration | 3 giorni | Alto | 🔵 Bassa |
| **10** | Audit Trail + Dashboard | 3 giorni | Medio | 🔵 Bassa |

**Totale stimato:** ~22 giorni lavorativi per implementazione completa

---

## 📋 Riepilogo File da Creare

| Nuovo File | Descrizione | Priorità |
|-----------|-------------|----------|
| `agents_meta.json` | Registry strutturato degli agenti | Alta |
| `core/agent_registry.py` | Gestione registro agenti | Alta |
| `core/agent_memory.py` | Memoria persistente per agenti | Alta |
| `core/agent_orchestrator.py` | Orchestrazione multi-agente | Alta |
| `core/tool_registry.py` | Plugin system per tool | Media |
| `core/output_validator.py` | Validazione output agenti | Media |
| `core/agent_templates.py` | Template generator agenti | Media |

## 📋 Riepilogo File da Modificare

| File Modificato | Cosa Cambia | Priorità |
|----------------|-------------|----------|
| `core/api_router.py` | Nuovi endpoint `/api/agents/*`, `/api/chat/orchestrate` | Alta |
| `sigma_server.py` | Nuovi handler import | Alta |
| `core/chat_handler.py` | Memoria pre/post sessione, tool injection | Alta |
| `core/task_handler.py` | Routing agenti, task queue estesa | Alta |
| `core/ai_providers.py` | Execution profiles | Media |

---

> *"Un sistema di agenti è potente quanto la sua capacità di orchestrare, ricordare e migliorare."*
> *"Un agente senza memoria è uno schiavo efficiente ma stupido."*
> *"La collaborazione tra agenti moltiplica le capacità individuali."*
> — Principi Sigma