# ==============================================================================
# core/harness/__init__.py — Runtime dell'agente, lato kernel
# Sigma Studio v8 — Agent Harness
# ==============================================================================
"""Il motore che fa lavorare un agente su un workspace, riusabile da ogni modulo.

Questo pacchetto era `core/developer_studio/`, e quel nome diceva una cosa
falsa: non c'e' niente qui che riguardi solo l'IDE. Il ciclo tool, lo stato di
lavoro, i permessi, le primitive di filesystem e terminale servono a chiunque
debba far eseguire un compito a un modello — la Pipelines Lab, la Training Lab,
la chat con gli strumenti. Tenerli dentro il Developer Studio significava che
per riusarli bisognava installare un IDE.

**Il confine.** Qui sta la *capacita'*: come si esegue un tool, come si tiene
memoria di cio' che e' stato fatto, come si decide che il lavoro e' finito, su
quale modello o provider gira il turno. Nel modulo installabile
`sigma_developer_lab` sta l'*esperienza*: le rotte HTTP, il flusso di lavoro a
cinque fasi, i ruoli dello sviluppo, i server MCP di git/lint/test e la UI.
Chi vuole modificare Sigma Studio installa il modulo; chi vuole solo far
lavorare un agente usa questo pacchetto e basta.

**Le parti.**

===================  =========================================================
`loop`               il ciclo multi-turno: prompt, tool, osservazioni, stallo
`roles`              il meccanismo dei ruoli: prompt, sampling, tool ammessi
`ledger`             lo stato di lavoro durevole e il cancello di completamento
`store`              la persistenza delle sessioni su `var/dev_sessions/`
`policy`             quali tool puo' usare chi, e i profili operativi
`rules`              le convenzioni dichiarate dal workspace (AGENTS.md)
`providers`          l'instradamento fra SigmaEngine e i provider esterni
`context`            il contesto condiviso fra ruoli di uno stesso obiettivo
`pipeline`           il DAG dei task, con dipendenze e riprese
`fs_manager`         albero, ricerca, backup e ripristino del workspace
`fs_tools`           lettura paginata, modifica chirurgica, glob
`terminal`           esecuzione di comandi, sincrona e in streaming
`symbol_index`       dove e' definito un simbolo, senza grep
`diagnostics`        validazione sintattica senza dipendenze esterne
`visual`             cattura di una pagina, per verificare cio' che si vede
`hooks`              ganci pre e post tool, per adattare senza modificare
`cli`                esecuzione headless, per la CI e per altri agenti
===================  =========================================================

Gli import restano espliciti (`from core.harness.ledger import ...`): un
`__init__` che importa tutto renderebbe il costo di usarne un pezzo pari al
costo di caricarli tutti, motore di inferenza compreso.
"""

__all__ = [
    "loop", "roles", "ledger", "store", "policy", "rules", "providers",
    "context", "pipeline", "fs_manager", "fs_tools", "terminal",
    "symbol_index", "diagnostics", "visual", "hooks", "cli",
]
