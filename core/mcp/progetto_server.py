# ==============================================================================
# core/mcp/progetto_server.py — Consultare la documentazione di Sigma Studio
# Sigma Studio v8 — MCP
# ==============================================================================
"""Uno strumento per leggere i documenti del progetto, a richiesta.

La scheda nel prompt dice **cosa esiste**: i ruoli veri, i tool veri, i moduli
veri. Costa cinquecento token e vale per tutta la conversazione. Non dice
perche' una cosa e' fatta cosi', ne' cosa e' andato storto la volta scorsa, ne'
come si usa — e quelle risposte stanno in seicento righe di documenti che
sarebbe assurdo tenere sempre in finestra.

Questo strumento e' l'altra meta': si chiede quando serve, torna **le sezioni
che parlano di quell'argomento**, e costa zero finche' nessuno lo chiama.

E' la stessa divisione che l'harness fa con il ledger: nel contesto sta il
sommario, e il dettaglio si va a prendere. Tenere tutto in finestra sembra piu'
sicuro e in pratica e' il modo piu' rapido di non avere spazio per il lavoro.
"""

from __future__ import annotations

from typing import Any, Dict

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE

log = get_logger("progetto_mcp")


class ProgettoMCPServer(BaseMCPServer):
    """Espone la documentazione di Sigma Studio come strumento interrogabile."""

    def __init__(self) -> None:
        super().__init__(
            name="Progetto MCP",
            version="1.0.0",
            description="Consulta la documentazione interna di Sigma Studio: "
                        "com'e' fatto, perche', e cosa e' gia' stato provato.",
        )

        self.register_tool(
            name="consulta_progetto",
            description=(
                "Cerca nella documentazione di Sigma Studio e restituisce le "
                "sezioni pertinenti. USALO ogni volta che ti viene chiesto "
                "com'e' fatto questo programma, come funziona l'harness, "
                "perche' una scelta e' stata presa cosi', o cosa e' gia' stato "
                "provato: rispondere a memoria su questo progetto produce nomi "
                "e componenti che non esistono. Senza argomento restituisce "
                "l'indice dei documenti disponibili."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "argomento": {
                        "type": "string",
                        "description": "Cosa cercare, in parole: «sandbox "
                                       "docker», «come si spezza il lavoro», "
                                       "«cancello di completamento».",
                    },
                    "documento": {
                        "type": "string",
                        "description": "Limita la ricerca a un documento "
                                       "(STATO_HARNESS.md, AGENTS.md, README.md).",
                    },
                },
                "required": [],
            },
            handler=self._consulta,
            # Legge file del progetto e non tocca niente: e' il caso piu'
            # innocuo che esista, e chiedere conferma per leggere insegnerebbe
            # a chiedere conferma per tutto.
            safety=SAFE,
            category="progetto",
        )

    def _consulta(self, argomento: str = "", documento: str = "") -> Dict[str, Any]:
        try:
            from core.scheda_progetto import consulta
            return consulta(argomento=argomento, documento=documento)
        except Exception as exc:
            log.warning("[Progetto] consultazione fallita: %s", exc)
            return {"ok": False, "error": str(exc)}
