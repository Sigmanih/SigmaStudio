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

from core.harness.ledger import MAX_STATE_CHARS, DevSessionLedger, Requirement

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
    """Il tetto adesso sta sulla parte VOLATILE, che e' l'unica che cresce.

    La parte stabile (obiettivo, percorsi, cartelle vere) e' andata in testa al
    prompt e ha una proprieta' migliore del tetto: non cresce affatto con il
    lavoro fatto, quindi la cache del prefisso la copre.
    """

    def test_la_parte_volatile_non_supera_il_tetto(self):
        # Con una storia lunga e duecento criteri la parte volatile resta
        # piccola: i tetti per sezione bastano, ed e' il risultato voluto.
        led = _ledger_con_storia()
        led.set_spec("capito", ["C" * 200 for _ in range(200)])
        assert len(led.render_volatile_block(5, 30)) <= MAX_STATE_CHARS

    def test_il_taglio_lo_dichiara(self):
        """Il taglio resta dichiarato, perche' il tetto resta.

        Oggi sfondarlo e' difficile — i tetti per sezione lo impediscono quasi
        sempre — ma il meccanismo deve dire cosa ha tolto invece di tagliare in
        silenzio: e' il caso che un test deve poter costruire.
        """
        led = _ledger_con_storia(numero=3)
        led.set_spec("capito", ["un criterio"])
        led._requirements = {
            str(i): Requirement(id=str(i), text="C" * 400, met=False, evidence="")
            for i in range(40)}
        stato = led.render_volatile_block(5, 30)
        assert len(stato) <= MAX_STATE_CHARS + 200
        assert "stato abbreviato" in stato

    def test_il_taglio_taglia_la_coda_non_la_testa(self):
        """Criteri e turni restano in cima: sono cio' con cui il turno decide."""
        led = _ledger_con_storia(numero=3)
        led.set_spec("capito", ["un criterio"])
        led._requirements = {
            str(i): Requirement(id=str(i), text="C" * 400, met=False, evidence="")
            for i in range(40)}
        stato = led.render_volatile_block(5, 30)
        assert stato.startswith("## STATO DEL LAVORO")
        assert "**Turni:** 5 di 30" in stato
        assert "**Criteri di accettazione" in stato

    def test_lo_stabile_non_cresce_con_la_storia(self):
        """La proprieta' che si paga: in testa non entra il lavoro gia' fatto."""
        corto = _ledger_con_storia(numero=2, obiettivo="Obiettivo fisso")
        lungo = _ledger_con_storia(numero=20, obiettivo="Obiettivo fisso")
        assert corto.render_stable_block() == lungo.render_stable_block()

    def test_uno_stato_normale_non_viene_toccato(self):
        stato = _ledger_con_storia(numero=3).render_volatile_block(5, 30)
        assert "stato abbreviato" not in stato


class TestLeListeSiAccorciano:
    def test_i_comandi_sono_gli_ultimi_due(self):
        # Due, non quattro: lo stato si riscrive a ogni turno, e un comando di
        # dieci turni fa non dice piu' niente su cosa fare adesso.
        stato = _ledger_con_storia().render_volatile_block(5, 30)
        assert stato.count("- [OK ] `python -c") == 2

    def test_i_file_letti_non_sono_piu_di_sei(self):
        stato = _ledger_con_storia().render_volatile_block(5, 30)
        assert stato.count("letto integralmente") <= 6

    def test_un_run_corto_li_mostra_tutti(self):
        stato = _ledger_con_storia(numero=2).render_state_block(1, 30)
        assert stato.count("- [OK ] `python -c") == 2

