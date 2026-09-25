# ==============================================================================
# tests/test_kicad_agent.py — L'agente della scheda, e la sua verifica
# ==============================================================================
"""Il pannello agente del PCB Lab era una recita, e qui si prova che non lo e' piu'.

`HardwareTeamOrchestrator` faceva cinque personaggi e nessuno dei cinque
chiamava un modello: il workflow eseguiva passi meccanici e intorno scriveva la
cronaca di un lavoro che nessuno stava facendo. Un `emit("closed_loop_verification",
drc_errors=0)` scritto a mano e' la cosa piu' pericolosa che potesse contenere:
diceva «scheda verificata» senza aver aperto kicad-cli.

Questi test guardano le tre cose che rendono vera quella scena:

- il run passa al ciclo dell'harness il ruolo `kicad_engineer` con i suoi tool,
  il suo prompt e la cartella del progetto;
- gli eventi del modello e dei tool arrivano all'interfaccia tradotti;
- la verifica finale e' il numero che ha risposto il controllo, o -1 quando il
  controllo non ha risposto — mai zero per cortesia.
"""
import json

import pytest

from core.modules.sigma_kicad_lab import orchestrator as O
from core.modules.sigma_kicad_lab import tools

tools.registra()

RUOLO = None


def _ruolo():
    from core.harness.roles import DEV_ROLES
    return DEV_ROLES["kicad_engineer"]


PCB = """(kicad_pcb
  (version 20240108)
  (generator "pcbnew")
  (net 0 "")
  (net 1 "GND")
  (gr_line (start 0 0) (end 20 0) (layer "Edge.Cuts") (stroke (width 0.05) (type solid)))
  (gr_line (start 20 0) (end 20 20) (layer "Edge.Cuts") (stroke (width 0.05) (type solid)))
  (footprint "Resistor_SMD:R_0603_1608Metric"
    (at 10 10)
    (layer "F.Cu")
    (property "Reference" "R1")
    (property "Value" "10k")
    (pad "1" smd rect (at -0.825 0) (size 0.8 0.95) (layers "F.Cu") (net 1 "GND"))
    (pad "2" smd rect (at 0.825 0) (size 0.8 0.95) (layers "F.Cu")))
)
"""


def _eventi(generatore) -> list:
    """Gli eventi SSE di un run, gia' decodificati."""
    eventi = []
    for riga in generatore:
        testo = riga.strip()
        if not testo.startswith("data: "):
            continue
        eventi.append(json.loads(testo[6:]))
    return eventi


@pytest.fixture
def progetto(tmp_path):
    """Una cartella con dentro una scheda vera e il suo schematico."""
    pcb = tmp_path / "prova.kicad_pcb"
    pcb.write_text(PCB, encoding="utf-8")
    (tmp_path / "prova.kicad_sch").write_text("(kicad_sch (version 20231120))\n",
                                              encoding="utf-8")
    return tmp_path, pcb


@pytest.fixture
def cattura(monkeypatch):
    """Sostituisce il ciclo dell'harness e registra come e' stato chiamato."""
    chiamate = {}

    def finto(*args, **kwargs):
        chiamate.update(kwargs)
        chiamate["args"] = args
        for evento in chiamate.get("eventi", []):
            yield evento

    monkeypatch.setattr("core.harness.loop.stream_admin_agent_turn", finto)
    return chiamate


def _verifica_pulita(monkeypatch, drc=0, erc=0):
    monkeypatch.setattr(tools, "kicad_open",
                        lambda percorso: {"success": True, "pcb": percorso})
    monkeypatch.setattr(tools, "kicad_drc",
                        lambda: {"success": True, "total_errors": drc})
    monkeypatch.setattr(tools, "kicad_erc",
                        lambda: {"success": True, "total_errors": erc})


# --- 1. il run passa al ciclo il ruolo vero ---------------------------------

def test_il_run_usa_il_ruolo_kicad_con_i_suoi_tool(progetto, cattura, monkeypatch):
    cartella, pcb = progetto
    _verifica_pulita(monkeypatch)
    ruolo = _ruolo()

    orch = O.HardwareTeamOrchestrator(task="Metti una resistenza di pull-up",
                                      project_dir=str(cartella), pcb_path=str(pcb))
    _eventi(orch.run_stream())

    assert cattura.get("allowed_tools") == list(ruolo.tools), (
        "il run non e' ristretto ai tool del ruolo: l'agente proverebbe tool "
        "che il ruolo non concede")
    assert cattura.get("policy_label") == "kicad_engineer"
    assert cattura.get("system_prompt_override") == ruolo.system_prompt
    assert cattura.get("workspace_root") == str(cartella)
    assert cattura.get("max_turns") == ruolo.max_turns
    # La richiesta porta il percorso della scheda: senza, `kicad_open` non sa
    # cosa aprire e l'agente non puo' cominciare.
    messaggi = cattura.get("messages") or []
    assert str(pcb) in messaggi[0]["content"]
    assert "kicad_drc" in messaggi[0]["content"]


def test_il_ruolo_concede_le_operazioni_di_correzione():
    """Il ruolo e' quello del modulo: i tool nuovi devono esserci."""
    ruolo = _ruolo()
    for nome in ("kicad_move_footprint", "kicad_rename_footprint",
                 "kicad_delete_track", "kicad_delete_via",
                 "kicad_set_board_outline", "kicad_set_pad_net"):
        assert nome in ruolo.tools, f"{nome} non concesso all'agente"


def test_senza_scheda_non_si_inventa_un_progetto(tmp_path, cattura):
    """Prima si creava una scheda vuota e si proseguiva: una bugia comoda."""
    orch = O.HardwareTeamOrchestrator(task="Fai qualcosa",
                                      project_dir=str(tmp_path))
    eventi = _eventi(orch.run_stream())
    assert eventi and eventi[-1]["type"] == "error"
    assert "kicad_pcb" in eventi[-1]["message"]
    assert not cattura, "il modello e' stato chiamato senza una scheda da aprire"


# --- 2. gli eventi arrivano tradotti ----------------------------------------

def test_gli_eventi_dell_agente_arrivano_alla_scheda(progetto, cattura, monkeypatch):
    cartella, pcb = progetto
    _verifica_pulita(monkeypatch)
    cattura["eventi"] = [
        {"type": "token", "token": "Ho aperto il progetto."},
        {"type": "tool_start", "tool": "kicad_open", "params": {}},
        {"type": "tool_result", "tool": "kicad_open", "result": {"success": True}},
        {"type": "thought", "token": "forse conviene...", "nascosto": True},
        {"type": "tool_result", "tool": "kicad_add_track",
         "result": {"success": False, "error": "nessun progetto aperto"}},
        {"type": "goal_complete", "summary": "Fatto."},
        {"type": "done", "full_text": ""},
    ]

    orch = O.HardwareTeamOrchestrator(task="Traccia una pista",
                                      project_dir=str(cartella), pcb_path=str(pcb))
    eventi = _eventi(orch.run_stream())
    tipi = [e["type"] for e in eventi]

    assert tipi[0] == "role_changed"
    assert eventi[0]["role"]["id"] == "kicad_engineer"
    assert "token" in tipi
    assert "tool" in tipi
    assert "tool_result" in tipi
    # Il ragionamento non esce dal server: e' il canale in cui il modello si
    # parla addosso.
    assert "thought" not in tipi
    assert "closed_loop_verification" in tipi
    assert tipi[-1] == "completed"

    fallito = [e for e in eventi
               if e["type"] == "tool_result" and e["success"] is False]
    assert fallito and "nessun progetto aperto" in fallito[0]["error"]


# --- 3. la verifica e' un esito, non una didascalia -------------------------

def test_la_verifica_riporta_gli_errori_veri(progetto, cattura, monkeypatch):
    cartella, pcb = progetto
    _verifica_pulita(monkeypatch, drc=3, erc=1)

    orch = O.HardwareTeamOrchestrator(task="Sistema il layout",
                                      project_dir=str(cartella), pcb_path=str(pcb))
    eventi = _eventi(orch.run_stream())
    verifica = [e for e in eventi if e["type"] == "closed_loop_verification"][0]

    assert verifica["drc_errors"] == 3
    assert verifica["erc_errors"] == 1
    finale = [e for e in eventi if e["type"] == "completed"][0]
    assert finale["score_percent"] < 100, (
        "una scheda con violazioni non e' un lavoro completo")


def test_senza_schematico_l_erc_non_si_inventa(progetto, cattura, monkeypatch):
    """Senza schematico l'ERC non c'e': il suo esito e' -1, non zero.

    Zero vorrebbe dire «controllato e pulito», che e' la cosa piu' lontana dal
    vero: non e' stato controllato niente.
    """
    cartella, pcb = progetto
    (cartella / "prova.kicad_sch").unlink()
    _verifica_pulita(monkeypatch, drc=0, erc=0)

    def erc_mai_chiamato():
        raise AssertionError("l'ERC e' stato eseguito senza uno schematico")

    monkeypatch.setattr(tools, "kicad_erc", erc_mai_chiamato)

    orch = O.HardwareTeamOrchestrator(task="Prova",
                                      project_dir=str(cartella), pcb_path=str(pcb))
    eventi = _eventi(orch.run_stream())
    verifica = [e for e in eventi if e["type"] == "closed_loop_verification"][0]
    assert verifica["drc_errors"] == 0
    assert verifica["erc_errors"] == -1


def test_una_verifica_non_eseguita_non_diventa_zero_errori(progetto, cattura,
                                                           monkeypatch):
    cartella, pcb = progetto
    monkeypatch.setattr(tools, "kicad_open",
                        lambda percorso: {"success": True, "pcb": percorso})
    monkeypatch.setattr(tools, "kicad_drc",
                        lambda: {"success": False, "error": "kicad-cli assente"})
    monkeypatch.setattr(tools, "kicad_erc",
                        lambda: {"success": False, "error": "kicad-cli assente"})

    orch = O.HardwareTeamOrchestrator(task="Prova",
                                      project_dir=str(cartella), pcb_path=str(pcb))
    eventi = _eventi(orch.run_stream())
    tipi = [e["type"] for e in eventi]

    assert "closed_loop_verification" not in tipi, (
        "una verifica che non ha risposto non e' una verifica riuscita")
    assert "status" in tipi
    assert tipi[-1] == "completed"
