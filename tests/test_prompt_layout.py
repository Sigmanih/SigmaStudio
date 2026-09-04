"""Dove sta il blocco di stato decide quanto prompt viene riprefillato.

La prefix cache del runtime riusa il prefisso di token che il prompt di questo
turno condivide con quello del turno scorso. Il blocco di stato del ledger
cambia a ogni turno: concatenato al system prompt stava in posizione 0, e il
prefisso condiviso finiva li' — ogni turno riprefillava l'intera conversazione,
cioe' proprio cio' che la cache esiste per evitare.

Spostandolo in coda, tutto quello che lo precede resta identico al turno
precedente. Questi test fissano quella proprieta', che e' invisibile a occhio
e si perde con una modifica di una riga.
"""

from core.developer_studio.admin_agent import (
    STATE_TAIL_ACT,
    STATE_TAIL_SUMMARISE,
    _with_state_block,
)

SYS = "Sei un ingegnere del software autonomo."


def _conversazione(turni: int):
    """Sistema, obiettivo, e `turni` scambi assistente/osservazione."""
    messaggi = [
        {"role": "system", "content": SYS},
        {"role": "user", "content": "Correggi la funzione somma."},
    ]
    for i in range(turni):
        messaggi.append({"role": "assistant", "content": f"chiamata tool {i}"})
        messaggi.append({"role": "user", "content": f"Risultati dei Tool: esito {i}"})
    return messaggi


def _testo(messaggi):
    """La conversazione come la vedrebbe il tokenizer, in forma lineare."""
    return "\n".join(f"{m['role']}:{m['content']}" for m in messaggi)


def _prefisso_comune(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


class TestCollocazione:
    def test_lo_stato_finisce_nell_ultimo_messaggio(self):
        reso = _with_state_block(_conversazione(1), "## STATO DEL LAVORO\n- letto x.py")
        assert "## STATO DEL LAVORO" in reso[-1]["content"]

    def test_il_system_prompt_non_viene_toccato(self):
        """E' la meta' del prefisso riusabile: se cambia, non si riusa nulla."""
        reso = _with_state_block(_conversazione(3), "stato che cambia")
        assert reso[0]["content"] == SYS
        assert "stato che cambia" not in reso[0]["content"]

    def test_l_istruzione_finale_resta_in_fondo(self):
        """Lo stato non deve seppellire l'ordine di emettere il tool successivo."""
        reso = _with_state_block(_conversazione(1), "stato")
        assert reso[-1]["content"].rstrip().endswith(STATE_TAIL_ACT)

    def test_a_lavoro_finito_l_istruzione_cambia(self):
        reso = _with_state_block(_conversazione(1), "stato", STATE_TAIL_SUMMARISE)
        assert reso[-1]["content"].rstrip().endswith(STATE_TAIL_SUMMARISE)

    def test_il_ruolo_dell_ultimo_messaggio_e_preservato(self):
        """Aggiungere un messaggio in piu' romperebbe l'alternanza dei template."""
        originale = _conversazione(2)
        reso = _with_state_block(originale, "stato")
        assert len(reso) == len(originale)
        assert reso[-1]["role"] == originale[-1]["role"]

    def test_la_conversazione_originale_non_viene_mutata(self):
        """Il transcritto accumulato non deve mai contenere lo stato.

        Se lo contenesse, i blocchi di stato di tutti i turni si
        accumulerebbero nella cronologia — ognuno vecchio e contraddetto dal
        successivo, tutti dentro la finestra.
        """
        originale = _conversazione(2)
        copia = [dict(m) for m in originale]
        _with_state_block(originale, "stato")
        assert originale == copia


class TestPrefissoRiusabile:
    def test_due_turni_condividono_tutta_la_cronologia(self):
        """La proprieta' che rende utile la cache, misurata.

        Fra il turno N e il turno N+1 il prompt diverge solo dove comincia il
        blocco di stato del turno N: tutto cio' che viene prima — system
        prompt, obiettivo, ogni scambio precedente — e' identico.
        """
        turno_n = _conversazione(2)
        reso_n = _testo(_with_state_block(turno_n, "STATO: 2 file letti"))

        # Il turno successivo aggiunge uno scambio e ha uno stato diverso.
        turno_n1 = turno_n + [
            {"role": "assistant", "content": "chiamata tool 2"},
            {"role": "user", "content": "Risultati dei Tool: esito 2"},
        ]
        reso_n1 = _testo(_with_state_block(turno_n1, "STATO: 3 file letti"))

        condiviso = _prefisso_comune(reso_n, reso_n1)
        # Tutto il turno N, fino all'inizio del suo blocco di stato.
        atteso = len(_testo(turno_n))
        assert condiviso >= atteso

    def test_uno_stato_che_cambia_non_sposta_il_prefisso(self):
        """Lo stato cresce a ogni tool: non deve invalidare cio' che lo precede."""
        conversazione = _conversazione(3)
        a = _testo(_with_state_block(conversazione, "STATO: poco"))
        b = _testo(_with_state_block(conversazione, "STATO: molto piu lungo di prima"))
        assert _prefisso_comune(a, b) >= len(_testo(conversazione))


class TestCasiLimite:
    def test_uno_stato_vuoto_lascia_tutto_com_e(self):
        conversazione = _conversazione(1)
        assert _with_state_block(conversazione, "") == conversazione

    def test_una_conversazione_vuota_non_solleva(self):
        assert _with_state_block([], "stato") == []

    def test_funziona_al_primo_turno(self):
        """Al primo giro l'ultimo messaggio e' l'obiettivo dell'utente."""
        reso = _with_state_block(_conversazione(0), "STATO: nulla di fatto")
        assert reso[-1]["role"] == "user"
        assert "Correggi la funzione somma." in reso[-1]["content"]
        assert "STATO: nulla di fatto" in reso[-1]["content"]
