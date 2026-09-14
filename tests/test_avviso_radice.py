"""Un agente deve sapere se sta scrivendo dentro casa propria.

Un compito che diceva «crea un programma **staccato da sigma** in react e
nodejs» e' stato eseguito con la radice su Sigma Studio. L'agente ha scritto
`backend/`, `frontend/` e `landing/` dentro il sorgente del programma che lo
stava eseguendo, e un commit se li e' portati dentro: 3.795 righe di
un'applicazione estranea nel repository del kernel.

Non aveva sbagliato a ragionare. Nessuno gli aveva detto dove si trovava, e una
cartella vale l'altra finche' non si sa che quella e' casa propria.

Non e' un divieto: sviluppare Sigma Studio con il suo stesso harness e' il modo
in cui questo programma e' cresciuto. E' un avviso, e si paga solo nel caso in
cui serve.
"""

import pytest

from core import paths
from core.harness.ledger import DevSessionLedger


class TestQuandoLAvvisoCompare:
    def test_sulla_radice_di_sigma_studio(self):
        ledger = DevSessionLedger(goal="crea un programma", workspace_root=paths.project_root())
        assert "**Dove sei:**" in ledger.render_state_block()

    def test_non_su_un_altro_progetto(self, tmp_path):
        """Il caso normale non deve pagare niente."""
        ledger = DevSessionLedger(goal="x", workspace_root=str(tmp_path))
        assert "**Dove sei:**" not in ledger.render_state_block()

    def test_ne_senza_radice(self):
        ledger = DevSessionLedger(goal="x")
        assert "**Dove sei:**" not in ledger.render_state_block()

    def test_un_percorso_scritto_in_un_altro_modo_e_sempre_lo_stesso_posto(self):
        """Barre rovesciate, barre normali, un `..` di troppo: e' la stessa
        cartella, e l'avviso non puo' dipendere da come la si e' scritta."""
        storto = str(paths.project_root()).replace(chr(92), "/") + "/core/.."
        ledger = DevSessionLedger(goal="x", workspace_root=storto)
        assert "**Dove sei:**" in ledger.render_state_block()

    def test_un_percorso_impossibile_non_solleva(self):
        ledger = DevSessionLedger(goal="x", workspace_root=chr(0) + "non/valido")
        assert isinstance(ledger.render_state_block(), str)


class TestCosaDiceLAvviso:
    def _testo(self):
        return DevSessionLedger(goal="x", workspace_root=paths.project_root()).render_state_block()

    def test_dice_dove_va_invece_un_applicativo_nuovo(self):
        """Segnalare senza indicare l'alternativa lascia il problema intero."""
        assert "data/progetti/" in self._testo()

    def test_non_vieta_di_lavorare_qui(self):
        testo = self._testo()
        assert "legittimo" in testo

    def test_dice_cosa_fare_invece_di_scrivere(self):
        assert "fermati" in self._testo()

    def test_sta_in_cima_dove_si_legge(self):
        """In fondo a un blocco di stato lungo non lo legge nessuno."""
        testo = self._testo()
        assert testo.index("**Dove sei:**") < testo.index("**Obiettivo:**")
