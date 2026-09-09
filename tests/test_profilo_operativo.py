"""Il profilo operativo dev'essere scegliibile, non solo accettato.

`ToolPolicy.for_profile` esiste, il gestore della chat legge `profile` dal corpo
della richiesta, il ciclo lo applica come tetto sopra i tool del ruolo — e
nessuno lo mandava. Settima volta in questo progetto che una capacita' viene
scritta, testata e lasciata scollegata, e stavolta stavo per documentarla
nell'audit come se si potesse usare.

Il profilo e' un **tetto**, non un'alternativa al ruolo: in sola lettura nessun
ruolo puo' scrivere, per quanti tool dichiari. E' la proprieta' che rende
sensato accenderlo quando si fa esplorare l'agente su un progetto che non si
vuole far toccare.
"""

import inspect
from pathlib import Path

import pytest

from core.harness.policy import ToolPolicy

CHAT = Path(__file__).resolve().parents[1] / (
    "sigma_studio/src/modules/sigma_developer_lab/AdminAgentChat.jsx")


class TestIlTettoResta:
    def test_in_sola_lettura_nessun_ruolo_puo_scrivere(self):
        """Il ruolo vero, non uno inventato: il Coder dichiara sia letture sia
        scritture, ed e' su di lui che il tetto deve mordere."""
        from core.harness.role_registry import get_role

        coder = get_role("coder")
        ruolo = ToolPolicy.of(list(coder.tools), label=coder.name)
        assert ruolo.permits("write_file") is True, "il ruolo di partenza deve poter scrivere"

        effettiva = ToolPolicy.for_profile("read_only").intersect(ruolo)

        assert effettiva.permits("write_file") is False
        assert effettiva.permits("terminal") is False
        # Cio' che il ruolo aveva e il tetto consente resta.
        assert effettiva.permits("read_file") is True

    def test_in_sola_pianificazione_non_si_esegue_niente(self):
        effettiva = ToolPolicy.for_profile("plan_only").intersect(
            ToolPolicy.of(["terminal", "write_file"]))
        assert effettiva.permits("terminal") is False
        assert effettiva.permits("spec") is True

    def test_senza_profilo_vale_solo_il_ruolo(self):
        ruolo = ToolPolicy.of(["read_file", "write_file"])
        assert ToolPolicy.for_profile("").intersect(ruolo).permits("write_file") is True


@pytest.mark.skipif(not CHAT.is_file(), reason="modulo Developer Studio non installato")
class TestSiPuoScegliere:
    """Il pezzo che mancava: il tetto c'era e non lo si poteva alzare."""

    def test_la_chat_manda_il_profilo_al_server(self):
        sorgente = CHAT.read_text(encoding="utf-8")
        assert "profile" in sorgente
        # Non solo nominato: spedito nel corpo della richiesta.
        assert "review_run: reviewRun,\n          profile" in sorgente

    def test_la_chat_offre_i_profili_che_il_kernel_conosce(self):
        sorgente = CHAT.read_text(encoding="utf-8")
        for valore in ('value=""', 'value="read_only"', 'value="plan_only"'):
            assert valore in sorgente, f"manca l'opzione {valore}"

    def test_il_gestore_lo_passa_al_ciclo(self):
        from core.modules.sigma_developer_lab import handlers

        sorgente = inspect.getsource(handlers.handle_agent_chat)
        assert 'body.get("profile")' in sorgente
        assert "profile=profile" in sorgente

    def test_i_nomi_offerti_sono_quelli_che_il_kernel_riconosce(self):
        """Un'opzione con un valore che il kernel non conosce ricadrebbe in
        silenzio su «nessun limite»: l'utente crederebbe di aver messo un tetto
        che non c'e'."""
        assert ToolPolicy.for_profile("read_only").restricted is True
        assert ToolPolicy.for_profile("plan_only").restricted is True
        assert ToolPolicy.for_profile("").restricted is False
