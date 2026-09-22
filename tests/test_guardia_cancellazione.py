# ==============================================================================
# tests/test_guardia_cancellazione.py — La cancellazione non aggira il troncamento
# ==============================================================================
"""`write_file` rifiuta una riscrittura che accorcia troppo un file. `delete`
non controllava niente, e la protezione si aggirava in un passo solo.

E' successo davvero, in questo repository. Un run ha perso 428 righe cosi':

  1. `write_file` rifiutato — «la nuova versione e' molto piu' corta»
  2. `delete` accettato senza obiezioni
  3. `write_file` bloccato dalla guardia anti-ripetizione

File distrutto, niente con cui rifarlo, nessun backup. La guardia aveva fatto
il suo lavoro sul tool che sorvegliava, e il lavoro e' andato perso lo stesso.

Cancellare un file e' ridurlo a zero caratteri: passa dalla stessa funzione e
dalla stessa soglia di `write_file`. Una regola parallela avrebbe avuto una
soglia diversa, e prima o poi le due si sarebbero contraddette.
"""
import os

import pytest

from core.harness.loop import execute_admin_tool


@pytest.fixture
def spazio(tmp_path):
    """Un workspace con dentro un file che vale la pena non perdere."""
    corposo = tmp_path / "modulo.py"
    corposo.write_text("\n".join(f"riga_{i} = {i}" for i in range(200)),
                       encoding="utf-8")
    minuscolo = tmp_path / "appunto.txt"
    minuscolo.write_text("due righe\ne basta\n", encoding="utf-8")
    return tmp_path


def _cancella(spazio, nome, **extra):
    return execute_admin_tool("delete", {"path": nome, **extra},
                              workspace_root=str(spazio))


class TestCancellazioneProtetta:

    def test_un_file_corposo_non_si_cancella_di_slancio(self, spazio):
        esito = _cancella(spazio, "modulo.py")
        assert esito["success"] is False
        assert (spazio / "modulo.py").is_file(), "il file doveva restare"

    def test_l_errore_indica_la_via_d_uscita(self, spazio):
        """Un rifiuto che non dice come procedere costa un turno a tentativo."""
        esito = _cancella(spazio, "modulo.py")
        assert "edit_file" in esito["error"]
        assert "allow_truncate" in esito["error"]
        assert "200 righe" in esito["error"]

    def test_con_il_permesso_esplicito_si_cancella(self, spazio):
        """La guardia chiede un'intenzione dichiarata, non vieta."""
        esito = _cancella(spazio, "modulo.py", allow_truncate=True)
        assert esito["success"] is True
        assert not (spazio / "modulo.py").exists()

    def test_un_file_piccolo_passa(self, spazio):
        """Sotto la soglia la cancellazione e' a basso costo: rifarlo e' banale,
        e chiedere conferma per ogni file di appunti sarebbe solo attrito."""
        esito = _cancella(spazio, "appunto.txt")
        assert esito["success"] is True

    def test_un_file_inesistente_non_inciampa_nella_guardia(self, spazio):
        esito = _cancella(spazio, "mai_esistito.py")
        assert "error" in esito or esito.get("success") is False


class TestLaScappatoiaEChiusa:
    """La sequenza esatta che ha distrutto il lavoro."""

    def test_write_rifiutato_poi_delete_rifiutato(self, spazio):
        scrittura = execute_admin_tool(
            "write_file", {"path": "modulo.py", "content": "x = 1\n"},
            workspace_root=str(spazio))
        assert scrittura["success"] is False, "la guardia su write_file non ha reagito"

        cancellazione = _cancella(spazio, "modulo.py")
        assert cancellazione["success"] is False, "delete ha ancora la scappatoia"
        assert (spazio / "modulo.py").is_file()

    def test_la_soglia_e_la_stessa_dei_due_tool(self, spazio):
        """Se le due guardie usassero soglie diverse, esisterebbe una fascia di
        dimensioni in cui una rifiuta e l'altra lascia passare."""
        from core.harness.fs_tools import would_truncate
        testo = (spazio / "modulo.py").read_text(encoding="utf-8")
        assert would_truncate(testo, "") is True
        assert _cancella(spazio, "modulo.py")["success"] is False

        piccolo = (spazio / "appunto.txt").read_text(encoding="utf-8")
        assert would_truncate(piccolo, "") is False
        assert _cancella(spazio, "appunto.txt")["success"] is True
