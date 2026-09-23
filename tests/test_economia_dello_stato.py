"""Lo stato si riscrive a ogni turno: ogni sua riga si paga trenta volte.

Misurato su un run vero del 23 settembre: lo stato del lavoro era 6075
caratteri, la mappa dei file 1808, il system prompt 12478 ? e con la cronologia
il prompt di un turno arrivava a circa 12700 token. Su un run da trenta turni
sono circa 380mila token di solo scheletro, riscritti identici.

Qui si verifica che lo stato abbia un tetto, che il tetto tagli la *storia* e
non la testa (obiettivo e criteri di accettazione sono le due cose senza cui il
turno non decide niente), e che le liste lunghe vengano accorciate prima di
arrivare al taglio.
"""

from core.harness.ledger import MAX_STATE_CHARS, DevSessionLedger

WS = "C:/progetto"


def _ledger_con_storia(numero=20, obiettivo="Implementa la funzione di importazione"):
    led = DevSessionLedger(goal=obiettivo, workspace_root=WS)
    for i in range(numero):
        # Un comando qualsiasi, non una verifica: `python -m pytest` senza un
        # "N passed" nell output e una verifica fallita, e il registro lo segna
        # come tale. Qui interessa la lunghezza della lista, non l esito.
        comando = 'python -c "print(%d)"' % i
        led.record_tool("terminal", {"command": comando},
                        {"success": True, "returncode": 0, "command": comando,
                         "stdout": "%d" % i})
    for i in range(numero):
        percorso = "%s/core/modulo_%02d.py" % (WS, i)
        led.record_tool("read_file", {"path": percorso},
                        {"success": True, "path": percorso, "offset": 1,
                         "last_line": 120, "total_lines": 120,
                         "content": "x" * 200})
    return led


class TestIlTetto:
    def test_lo_stato_non_supera_il_tetto(self):
        stato = _ledger_con_storia(obiettivo="I" * 12000).render_state_block(5, 30)
        assert len(stato) <= MAX_STATE_CHARS + 200, len(stato)

    def test_il_taglio_lo_dichiara(self):
        stato = _ledger_con_storia(obiettivo="I" * 12000).render_state_block(5, 30)
        assert "stato abbreviato" in stato

    def test_la_testa_resta_la_testa(self):
        """Obiettivo e turni stanno in cima, ed e cio che il turno usa per decidere."""
        stato = _ledger_con_storia(obiettivo="I" * 12000).render_state_block(5, 30)
        assert stato.startswith("## STATO DEL LAVORO")
        assert "**Obiettivo:**" in stato

    def test_uno_stato_normale_non_viene_toccato(self):
        stato = _ledger_con_storia(numero=3).render_state_block(5, 30)
        assert "stato abbreviato" not in stato


class TestLeListeSiAccorciano:
    def test_i_comandi_sono_gli_ultimi_quattro(self):
        stato = _ledger_con_storia().render_state_block(5, 30)
        assert stato.count("- [OK ] `python -c") == 4

    def test_i_file_letti_non_sono_piu_di_dodici(self):
        stato = _ledger_con_storia().render_state_block(5, 30)
        assert stato.count("letto integralmente") <= 12

    def test_un_run_corto_li_mostra_tutti(self):
        stato = _ledger_con_storia(numero=2).render_state_block(1, 30)
        assert stato.count("- [OK ] `python -c") == 2

