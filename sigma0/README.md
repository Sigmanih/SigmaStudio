# 🏗️ Sigma AI Architect (sigma_architect)

**Agente amministratore e coordinatore principale di Sigma Studio.**

## Ruolo

sigma_architect è l'agente principale della piattaforma. Ha un duplice ruolo:

1. **Ricercatore Singolo**: Lavora autonomamente su obiettivi di ricerca
2. **Coordinatore**: Orchestrazione di pipeline multi-agente

## Come usarlo

```bash
# Crea il modello Ollama da questo manifesto
curl -X POST http://localhost:8000/api/create_model \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"sigma0\", \"modelfile\": \"$(cat sigma0/sigma_architect.md)\"}"
```

Oppure usa l'interfaccia grafica → Tab **Manifesti** → AI Model Lab.

## Struttura che sigma_architect conosce

```
data/<topic>/
├── <NN>_nome_modulo/
│   ├── teoria/         → Documenti teorici (.md)
│   ├── test/           → Test Python (.py)
│   ├── viz/            → Visualizzazioni HTML/D3.js
│   ├── docs/           → Report e documentazione
│   └── whitepapers/    → Whitepaper formali
└── <NN>_altro_modulo/
    └── ...
```

## Parametri

| Parametro | Valore |
|-----------|--------|
| Modello base | `llama3.2` |
| Temperature | 0.55 |
| Context window | 32768 |
| Ruolo | admin / orchestrator |