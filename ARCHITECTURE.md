# Sigma Studio — Architecture Overview

**Version 8.1 — Kernel / Module separation**
**Verified on**: Windows 11 (x86_64, NVIDIA CUDA) and Raspberry Pi 5 (aarch64, CPU only)

> **`architettura.md` is the authoritative document.** It carries the full
> specification: diagrams, endpoint tables, measured figures and the refactoring
> backlog. This file is the English entry point and stays deliberately short —
> two full copies of the same specification in two languages is precisely the
> kind of duplication this architecture is being cleaned of, and the copy that
> nobody edits is the one that lies.

---

## The shape of the system

A React 19 SPA talks to a FastAPI application over REST and SSE on port 8000.
Behind it sit two layers with one rule between them.

```
                    React 19 SPA  (sigma_studio/)
                            │  REST / SSE :8000
                    ────────┴────────
                       Uvicorn ASGI
                            │
    ┌───────────────────────┴────────────────────────┐
    │  KERNEL — core/                                │
    │  paths · engine · chat · pipeline · mcp ·      │
    │  developer_studio · module_loader              │
    └───────────────────────┬────────────────────────┘
                            ▲   register_routes() / register_mcp()
    ┌───────────────────────┴────────────────────────┐
    │  MODULES — core/modules/  (optional)           │
    │  training_lab · model_hub · hardware_lab ·     │
    │  knowledge · audio_studio                      │
    └────────────────────────────────────────────────┘
```

**The rule**: dependencies point down, and sideways only along a link a module
declares for itself. The kernel never imports, lists or names a module. Where
that rule is still broken it is written down in `architettura.md` § 9 rather
than quietly tolerated.

The kernel offers *services* — where files live, what hardware is underneath,
how a stream is opened, how a model is loaded. Anything meaningful to a single
domain (training, evaluation, audio) is a module, even when its code still sits
inside `core/`.

---

## Four data roots

Everything used to live in `data/`: 122 GB of model weights beside the user's
notes, with the knowledge graph indexing the wrong two thirds of it. One
question separates them — *what happens if I delete this?*

| Root | Holds | If deleted | Back up |
|:---|:---|:---|:---:|
| `data/` | the user's own work: topics, notes, generated images | **data loss** | yes |
| `config/` | machine configuration — **holds credentials** | back to defaults | yes |
| `var/` | runtime state: tasks, indexes, caches | starts clean | no |
| `store/` | downloaded artefacts: models, shards, engine tools | re-downloads | no |

All four resolve through `core/paths.py`, anchored to the installation and never
to the working directory. `SIGMA_HOME` relocates the whole installation — useful
when code sits on an SD card and data on an external disk.

---

## Non-negotiables

**Never rebuild a path.** No `Path(__file__).parent.parent`, no `os.getcwd()`,
no path relative to the launch directory. Ask `core/paths.py`. A `__file__`
climb counts levels from wherever the file currently is: moving a package two
directories deeper without updating it raises no error, it silently creates a
second empty tree via `mkdir(parents=True)` and keeps working inside it. That is
how the Training Lab stopped seeing all 103 of its jobs for weeks.

**Never block the event loop.** Handlers are synchronous and must reach a worker
thread — `asyncio.to_thread`, or the dispatcher's own pools (32 API threads, 16
stream threads, sized for the workload rather than the core count). One
synchronous filesystem search run inline froze every endpoint in the
application.

**Every scan gets a budget.** Per-file cap, total cap, deadline, and partial
results instead of an unbounded wait. An unbounded workspace search took the
process to 75 GB resident before anyone noticed; the same code on a Pi 5 would
have died in thirty seconds, which is the better signal.

**Modules live in another repository.** `core/modules/` is an install target,
not source: the modules are kept in `SigmaStudio-Moduli`. A fix applied only to
the installed copy is erased by the next marketplace reinstall.

---

## Where things are

| Path | What |
|:---|:---|
| `sigma_server.py` | prepares the environment and starts uvicorn — nothing else |
| `core/fastapi_app.py` | the single request pipeline, adapter and thread pools |
| `core/paths.py` | every root and well-known file in the installation |
| `core/api_router.py` | route → handler tables |
| `core/engine/` | inference runtime, hardware probe, memory planner |
| `core/agents/catalog/` | the twenty stock agents, one Modelfile each |
| `core/modules/<id>/` | installed module backends |
| `sigma_studio/src/modules/<id>/` | installed module frontends |
| `training/`, `training_lab/` | training data, deliberately outside the module |

---

## Testing

```bash
python -m pytest tests/ -q
```

199 kernel tests. Module suites live with their modules in `SigmaStudio-Moduli`
and run against the installed copy; point `SIGMA_HOME` at this installation to
run them from elsewhere.
