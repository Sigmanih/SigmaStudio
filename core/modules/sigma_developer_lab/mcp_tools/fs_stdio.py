# ==============================================================================
# core/modules/sigma_developer_lab/mcp_tools/fs_stdio.py - La porta minima
# Sigma Studio v8 - Modulo installabile
# ==============================================================================
"""I tool dei file su stdin e stdout, passando dal cancello dell hub.

**Cosa e questo comando.** La porta minima per un client esterno che vuole solo i
file: i cinque tool del server dei file, con la policy dell applicazione e
l assenso sui tool sensibili. E `hub_stdio` con il filtro fissato su
`Developer Files`, non un implementazione parallela: una regola sola, un posto
solo.

**Perche non e piu un server a se.** Fino al 23 settembre 2026 questo file
chiamava `DeveloperFsMCPServer` direttamente e **non passava dal cancello**:
nessuna policy, nessun assenso. I tre tool di scrittura sono SENSITIVE - la
docstring lo prometteva - ma da qui nessuno chiedeva niente, quindi un client
esterno poteva scrivere nel workspace senza che un umano vedesse mai la
richiesta. Restava la traccia nel diario, che dice chi ha scritto; non restava il
permesso, che e un altra cosa. E una promessa scritta nella documentazione che il
codice non mantiene e peggio di una capacita che manca: ci si fida.

**Cosa costa.** Il filtro limita l elenco dei tool, non l avvio: l hub costruisce
i suoi server comunque, indice semantico compreso, e si paga una volta per
sessione. Rendere l avvio pigro e un lavoro suo (vedi la voce s7 della coda).

**Uso.** Come prima, e `SIGMA_WORKSPACE_ROOT` continua a decidere la radice:

    SIGMA_WORKSPACE_ROOT=/percorso/del/progetto SIGMA_MCP_CLIENT="Cline" python -m \\
        core.modules.sigma_developer_lab.mcp_tools.fs_stdio

**L ordine degli import conta.** Il canale del protocollo - `sys.stdout` - lo
prepara `hub_stdio`, e questo file lo importa dentro `main`, prima di qualunque
altra cosa. Due moduli che si scambiano `sys.stdout` a vicenda si rubano il
canale: il secondo a partire scambierebbe l ingresso e scriverebbe i messaggi su
stderr, dove il client non li legge.
"""

from typing import Optional

#: Il filtro di questa porta: i file, e nient altro.
FILTRO = ["Developer Files"]


def main(argv: Optional[list] = None) -> int:
    """Serve i tool dei file passando dall hub, filtro compreso."""
    from core.modules.sigma_developer_lab.mcp_tools.hub_stdio import (
        HubMCPServer,
        main as hub_main,
    )

    return hub_main(argv, server=HubMCPServer(ammessi=FILTRO))


if __name__ == "__main__":
    raise SystemExit(main())
