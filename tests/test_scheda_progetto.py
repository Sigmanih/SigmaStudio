"""Il modello deve sapere cos'e' Sigma Studio senza leggerselo tutto ogni volta.

Chiedendo a Qwen dentro Sigma Studio «cos'e' l'harness e come si migliora», la
risposta descriveva **sette agenti che non esistono**, indicava la sandbox in
`data/` — che e' quella della chat, non quella dell'harness — e dei
trentacinque moduli del kernel non ne nominava uno.

Non era un difetto del modello: nessuno gli aveva dato i fatti. Il prompt di
sistema descrive un assistente, non questo programma, e da li' si puo' solo
dedurre. Il risultato ha la forma di una diagnosi e il contenuto di
un'immaginazione, che e' il modo piu' costoso di sbagliare.

Due pezzi, e la divisione fra i due e' tutto il punto:

- **la scheda**, corta e sempre nel prompt, dice *cosa esiste*;
- **`consulta_progetto`**, a richiesta, dice *perche'* e *cosa e' gia' successo*.

Tenere tutto in finestra sembra piu' sicuro ed e' il modo piu' rapido di non
avere spazio per il lavoro.
"""

import pytest

from core import scheda_progetto as S


class TestLaSchedaVieneDalCodice:
    """Un testo scritto a mano dice la verita' il giorno in cui lo si scrive e
    comincia a mentire il giorno dopo."""

    def test_nomina_i_ruoli_veri_e_solo_quelli(self):
        from core.harness.roles import DEV_ROLES

        testo = S.scheda()
        for ruolo in DEV_ROLES:
            assert ruolo in testo
        # I nomi che il modello si era inventato non devono comparire.
        for inventato in ("code_architect", "proof_reviewer", "sigma_architect",
                          "academic_examiner", "data_scientist"):
            assert inventato not in testo

    def test_nomina_i_tool_veri(self):
        from core.harness.tool_schema import TOOL_SCHEMAS

        testo = S.scheda()
        for schema in TOOL_SCHEMAS:
            assert schema["function"]["name"] in testo

    def test_distingue_i_ruoli_dell_harness_dagli_agenti_della_chat(self):
        """Era la confusione al centro della risposta sbagliata."""
        testo = S.scheda()
        assert "ruoli dell'harness" in testo
        assert "agenti della chat" in testo

    def test_dice_dove_si_scrive_davvero(self):
        testo = S.scheda()
        assert "data/" in testo
        assert "cartella di progetto" in testo, (
            "l'harness non lavora in data/, e crederlo porta lontano")

    def test_resta_corta(self):
        """Sta nel prefisso stabile, che e' anche il prefisso della cache KV:
        si paga una volta per conversazione, ma si paga."""
        assert len(S.scheda()) < 4000, "una scheda lunga smette di essere una scheda"

    def test_si_rigenera_quando_il_progetto_cambia(self, monkeypatch):
        prima = S.scheda()
        monkeypatch.setattr(S, "_ruoli_veri", lambda: ["architect", "nuovo_ruolo"])
        dopo = S.scheda()
        assert "nuovo_ruolo" in dopo and dopo != prima

    def test_un_pezzo_illeggibile_non_fa_sparire_la_scheda(self, monkeypatch):
        def esplode():
            raise RuntimeError("config non leggibile")

        monkeypatch.setattr(S, "_agenti_della_chat", esplode)
        # `_agenti_della_chat` cattura da solo: la scheda esce lo stesso.
        assert "L'harness dell'agente" in S.scheda()


class TestLaConsultazione:
    def test_senza_argomento_da_l_indice(self):
        esito = S.consulta()
        assert esito["ok"] is True
        nomi = [d["documento"] for d in esito["indice"]]
        assert "STATO_HARNESS.md" in nomi

    def test_cerca_parola_per_parola_non_la_frase(self):
        """«sandbox docker» come frase compare solo dove qualcuno l'ha scritta
        cosi'; le sezioni che servono parlano di «sandbox» in un punto e di
        «Docker» in un altro."""
        esito = S.consulta("sandbox docker")
        assert len(esito["sezioni"]) >= 2

    def test_ritorna_sezioni_intere(self):
        """Mezza sezione risponde alla domanda e nasconde il motivo, che in
        questi documenti sta quasi sempre nel paragrafo dopo."""
        esito = S.consulta("worktree")
        assert esito["sezioni"]
        assert esito["sezioni"][0]["testo"].lstrip().startswith("#")

    def test_una_ricerca_a_vuoto_dice_quanto_ha_guardato(self):
        """Senza, «non trovato» non distingue «non c'e'» da «non ho cercato»."""
        esito = S.consulta("zqxjkv_inesistente")
        assert esito["sezioni"] == []
        assert esito["esaminate"] > 0
        assert str(esito["esaminate"]) in esito["messaggio"]

    def test_si_puo_limitare_a_un_documento(self):
        esito = S.consulta("regole", documento="AGENTS.md")
        assert all(s["documento"] == "AGENTS.md" for s in esito["sezioni"])

    def test_la_risposta_ha_un_tetto(self):
        """Riversare un documento intero nel contesto non e' rispondere."""
        esito = S.consulta("e")  # parola cortissima: viene saltata
        caratteri = sum(len(s["testo"]) for s in esito.get("sezioni", []))
        assert caratteri <= S.MAX_CARATTERI_RISPOSTA + 4000

    def test_l_indice_elenca_solo_documenti_che_esistono(self):
        from pathlib import Path

        from core import paths

        for voce in S.indice():
            assert (Path(paths.project_root()) / voce["documento"]).is_file()


class TestTuttoEDavveroCollegato:
    """Il difetto piu' frequente di questo progetto e' la capacita' scritta e
    mai raggiungibile."""

    def test_la_scheda_sta_nel_prefisso_stabile_della_chat(self):
        import inspect

        from core.chat import chat_runner

        sorgente = inspect.getsource(chat_runner)
        assert "from core.scheda_progetto import scheda" in sorgente
        assert "{scheda_blocco}" in sorgente, "generata e non inserita nel prompt"

    def test_il_tool_e_fra_i_built_in_dell_hub(self):
        from core.mcp.mcp_hub import BUILTIN_SERVERS, MCPHub

        nomi = [c.__name__ for c in BUILTIN_SERVERS]
        assert "ProgettoMCPServer" in nomi, (
            "fra i built-in perche' deve esserci sempre: un modello che "
            "risponde a memoria su questo programma inventa i nomi")
        assert "consulta_progetto" in [t.get("name") for t in MCPHub().list_all_tools()]

    def test_il_tool_risponde_davvero_passando_dall_hub(self):
        from core.mcp.mcp_hub import MCPHub

        esito = MCPHub().execute_tool("consulta_progetto",
                                      {"argomento": "cancello di completamento"})
        assert esito.get("status") == "ok", esito
        assert esito["server"] == "Progetto MCP"
        testo = esito["result"]["content"][0]["text"]
        assert "sezioni" in testo and "cancello" in testo.lower()
