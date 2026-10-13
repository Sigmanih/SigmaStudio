# 🧬 Sigma Studio — AI Agent Manifests

Tutti i manifesti sono creati da **Ing. Diego Saitta** — Sigma Studio.

This directory contains the official Modelfile manifests for Sigma Studio's AI agents.

## Available Agents

| File | Temp | num_ctx | Role |
|------|------|---------|------|
| `sigma_admin.md` | 0.2 | 65536 | System orchestrator, admin, full architecture knowledge |
| `sigma_assistant.md` | 0.3 | 16384 | Front-desk, routing, chat |
| `sigma_architect.md` | 0.55 | 32768 | Research admin, coordinator |
| `code_architect.md` | 0.3 | 16384 | Full-stack developer |
| `math_researcher.md` | 0.5 | 32768 | Math theory & proofs |
| `test_engineer.md` | 0.25 | 16384 | Python test engineering |
| `viz_designer.md` | 0.5 | 16384 | D3.js visualizations |
| `proof_reviewer.md` | 0.3 | 32768 | Critical review |
| `regista_cinematografico.md` | 0.35 | 32768 | Film director, shot list, visual grammar & scene blocking |
| `sceneggiatore.md` | 0.4 | 32768 | Screenplay, character arcs, cinematic dialogues & 3-act structure |
| `direttore_fotografia.md` | 0.3 | 32768 | DoP, lighting design, lenses, color grading & cinematic prompts |
| `montatore_video.md` | 0.25 | 32768 | Film editor, scene cuts (J/L-cuts), pacing & video timeline |
| `sound_designer.md` | 0.3 | 32768 | Sound design, Foley, audio scoring, soundscape & track mixing |

## Private Manifests

Place personal/custom manifests in `Private/` — they will be ignored by git and not published.

## Architecture

```
User → Sigma Assistant (router)
          ├── Direct chat response
          ├── switch_agent → sigma_admin (orchestration, architecture)
          ├── switch_agent → sigma_architect (research, coordination)
          ├── switch_agent → code_architect (code changes)
          ├── switch_agent → math_researcher (math theory)
          ├── switch_agent → test_engineer (tests)
          ├── switch_agent → viz_designer (visualizations)
          └── switch_agent → proof_reviewer (validation)
```

## Usage

```bash
# Load an agent into Ollama
curl -X POST http://localhost:8000/api/create_model \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"sigma_assistant\", \"modelfile\": \"$(cat manifesti/sigma_assistant.md)\"}"
```
</write_to_file>