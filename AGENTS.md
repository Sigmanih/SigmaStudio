# Sigma Studio Agent Conventions

This file is read by Developer Studio and any compatible agent harness
before each run. Its rules take precedence over general agent habits.
Keep it concise: it is a list of constraints, not documentation.
The full specification lives in `ARCHITECTURE.md`.

## Structure

| Path | Contents |
|:---|:---|
| `core/` | Python kernel: paths, engine, chat, pipeline, mcp, module_loader |
| `core/modules/` | optional installable modules; never imported by the kernel |
| `core/harness/` | agent runtime: tool loop, roles, ledger, permissions |
| `core/modules/sigma_developer_lab/` | Developer Studio: routes, phases, dev MCP servers |
| `sigma_studio/src/` | React 19 SPA served by Vite |
| `tests/` | kernel pytest test suite |
| `data/` | user workspace — **never delete anything here** |
| `config/` | machine configuration, **contains credentials** |
| `var/` | runtime state: sessions, indices, cache (recreatable) |
| `store/` | model weights and heavy artifacts |

**The architectural rule:** dependencies point downward. The kernel never
imports, lists, or names any module. A module registers itself via
`register_routes()` / `register_mcp()`.

## Python Backend

- Python 3.10+. No `pass` stubs, no placeholder code.
- Always handle exceptions, timeouts, and return codes cleanly.
- Logging via `from core.logger import get_logger`, never `print`.
- Paths with `pathlib.Path`, never string concatenations.
- Must run on Windows 11 **and** Raspberry Pi 5 (aarch64, CPU-only, 8 GB RAM).
  No raw CUDA assumptions, no absolute Windows paths.

## React Frontend

- Standard React only: `useState`, `useEffect`, `useCallback`.
  **Component libraries strictly forbidden** (`@mui`, `antd`, `bootstrap`, `tailwind`).
- Icons exclusively from `lucide-react`.
- Styles in `sigma_studio/src/styles/` (`01-base`, `02-layout`, `03-modules`). No CSS-in-JS.
- Allowed dependencies: `d3`, `three`, `mermaid`, `prismjs`, `katex`, `react-simple-code-editor`.

## Harness in Kernel, IDE in Module

The agent runtime lives in `core/harness/`: tool loop, roles, ledger, permissions,
filesystem/terminal primitives, provider routing. It belongs in the kernel because
it serves any module executing tasks via models.

Developer Studio is the installable module `core/modules/sigma_developer_lab/`:
it holds `/api/developer/*` routes, the 5-phase workflow, git/lint/test MCP servers,
and UI in `sigma_studio/src/modules/sigma_developer_lab/`.

**Dependency direction:** modules import `core.harness`, never vice versa.

## Verification

Work is not complete until verified by an executable check:

```bash
python -m pytest -m harness -q                # agent loop: turns, ledger, evidence, queue
python -m pytest -m mcp -q                    # MCP hub, approvals, axes, dev server
python -m pytest -m chat -q                   # chat: prompts, history, responses
python -m pytest -m motore -q                 # inference and models: engine, GGUF, hardware
python -m pytest -m moduli -q                 # modules: EDA, KiCad, pipeline, i18n
python -m pytest -m base -q                   # rest of kernel: paths, boot, system
python -m pytest tests/test_<file>.py -q      # single test file
npm --prefix sigma_studio run lint:undef      # frontend: undefined references (no-undef)
npm --prefix sigma_studio run build           # frontend production build
python -c "import core.<module>"              # minimal import check
```

**Never run tests while the dev server is active on port 8000.**

### Custom Checks Output Format
For checks that are not standard pytest tests, output this as the final line:
```
SIGMA-CHECK {"check": "i18n", "checked": 214, "problems": 0}
```

## Language and Style

- Respond to the user in Italian. Code comments: new ones in Italian; keep existing English comments if editing English files.
- Comments explain **why**, not what.
- Git commit messages in Italian, imperative mood.

## Strictly Prohibited

- Do not touch `data/`, `config/`, `store/` unless explicitly requested.
- Do not rewrite whole files with `write_file` when `edit_file` / `replace_file_content` suffices.
- Do not add dependencies to `requirements.txt` or `package.json` unprompted.
- Do not create status/summary/scratch files on disk at completion; summarize in chat.
