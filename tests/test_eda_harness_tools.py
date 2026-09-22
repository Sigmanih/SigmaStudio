# ==============================================================================
# tests/test_eda_harness_tools.py — I tool EDA visti dall'harness
# ==============================================================================
"""Che un agente possa disegnare un circuito dipende da tre cose che si possono
provare senza EasyEDA aperto: che i tool siano dichiarati e smistati, che la
policy sappia quali scrivono, e che i pin si risolvano per nome.

La terza e' quella che conta. Un modello che deve ricordare il numero di pin di
VOUT fra due chiamate lo sbaglia, e lo sbaglia in un modo che non si vede: il
circuito si disegna, la netlist torna, e il collegamento e' sul pin sbagliato.
Risolvere per nome sposta quell'errore da silenzioso a impossibile.
"""
import pytest

from core.harness import eda_tools, policy
from core.harness.roles import DEV_ROLES
from core.harness.tool_schema import TOOL_SCHEMAS, schemas_for


# ---------------------------------------------------------------------------
# Dichiarazione e smistamento
# ---------------------------------------------------------------------------

class TestCatalogo:

    def test_tutti_gli_esecutori_sono_dichiarati(self):
        """Un tool eseguibile ma non dichiarato non esiste per il modello, e un
        tool dichiarato ma non eseguibile e' una promessa che il run non
        mantiene. I due elenchi devono coincidere."""
        dichiarati = {s["function"]["name"] for s in TOOL_SCHEMAS
                      if s["function"]["name"].startswith("eda_")}
        assert dichiarati == set(eda_tools.ESECUTORI)

    def test_ogni_schema_eda_e_valido(self):
        for s in TOOL_SCHEMAS:
            if not s["function"]["name"].startswith("eda_"):
                continue
            par = s["function"]["parameters"]
            assert par["type"] == "object"
            assert set(par.get("required", [])) <= set(par["properties"])
            assert s["function"]["description"].strip()

    def test_il_dispatcher_delega_i_tool_eda(self):
        """La diramazione in loop.py deve riconoscerli, altrimenti finiscono
        nel ramo 'Tool sconosciuto'."""
        esito = eda_tools.esegui("eda_status", {})
        assert esito is not None and esito["tool"] == "eda_status"

    def test_il_dispatcher_ignora_gli_altri(self):
        assert eda_tools.esegui("read_file", {"path": "x"}) is None

    def test_argomenti_sbagliati_non_esplodono(self):
        esito = eda_tools.esegui("eda_pins", {"sbagliato": 1})
        assert esito["success"] is False
        assert "eda_pins" in esito["error"]


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class TestPolicy:

    @pytest.mark.parametrize("alias,atteso", [
        ("eda_connect", "eda_connect"), ("collega", "eda_connect"),
        ("pista", "eda_wire"), ("verifica_circuito", "eda_verify"),
        ("cerca_componente", "eda_search_part"),
        ("piazza_componente", "eda_place_part"),
    ])
    def test_alias_italiani(self, alias, atteso):
        assert policy.canonical(alias) == atteso

    def test_le_letture_sono_sola_lettura(self):
        assert eda_tools.EDA_READ_TOOLS <= policy.READ_ONLY_TOOLS

    def test_le_scritture_non_lo_sono(self):
        """Il punto del cancello: chi ha solo lettura non deve poter piazzare."""
        assert not (eda_tools.EDA_WRITE_TOOLS & policy.READ_ONLY_TOOLS)

    def test_verify_e_una_lettura(self):
        """La prova di un collegamento deve poterla chiedere anche un ruolo che
        non ha il permesso di scrivere: e' cosi' che un revisore controlla."""
        assert "eda_verify" in policy.READ_ONLY_TOOLS

    def test_i_due_insiemi_coprono_tutto(self):
        assert eda_tools.EDA_READ_TOOLS | eda_tools.EDA_WRITE_TOOLS == set(eda_tools.ESECUTORI)


# ---------------------------------------------------------------------------
# Il ruolo
# ---------------------------------------------------------------------------

class TestRuolo:

    def test_esiste(self):
        assert "eda_engineer" in DEV_ROLES

    def test_ha_tutti_i_tool_eda(self):
        ruolo = DEV_ROLES["eda_engineer"]
        assert set(eda_tools.ESECUTORI) <= set(ruolo.tools)

    def test_ogni_tool_concesso_ha_uno_schema(self):
        """Un tool concesso senza schema non arriva mai al modello."""
        ruolo = DEV_ROLES["eda_engineer"]
        assert len(schemas_for(ruolo.tools)) == len(ruolo.tools)

    def test_non_puo_modificare_il_codice(self):
        """Disegna circuiti, non tocca il repository: se potesse scrivere file
        un giro andato male modificherebbe il kernel invece dello schematico."""
        ruolo = DEV_ROLES["eda_engineer"]
        assert not ({"write_file", "edit_file", "terminal", "delete"} & set(ruolo.tools))

    def test_il_prompt_impone_la_verifica(self):
        prompt = DEV_ROLES["eda_engineer"].system_prompt
        assert "eda_verify" in prompt
        assert "complete_goal" in prompt

    def test_abbastanza_turni_per_un_circuito(self):
        """Piazzare, leggere i pin, collegare e verificare sono quattro giri per
        componente: con dodici turni non si finisce niente."""
        assert DEV_ROLES["eda_engineer"].max_turns >= 30


# ---------------------------------------------------------------------------
# Risoluzione dei pin — il cuore
# ---------------------------------------------------------------------------

PIN_FINTI = [
    {"pinNumber": "1", "pinName": "VOUT", "x": 10, "y": 20},
    {"pinNumber": "2", "pinName": "-VS", "x": 10, "y": 30},
    {"pinNumber": "5", "pinName": "+VS", "x": 20, "y": 30},
]


@pytest.fixture
def pin_in_cache(monkeypatch):
    monkeypatch.setitem(eda_tools._pin_cache, "U1", PIN_FINTI)
    return "U1"


class TestRisoluzionePin:

    def test_per_nome(self, pin_in_cache):
        assert eda_tools._risolvi(pin_in_cache, "VOUT") == "1"
        assert eda_tools._risolvi(pin_in_cache, "+VS") == "5"

    def test_per_numero(self, pin_in_cache):
        assert eda_tools._risolvi(pin_in_cache, "2") == "2"

    def test_il_numero_vince_sul_nome(self, pin_in_cache):
        """Un pezzo con un pin chiamato '2' e un pin numero 2 e' raro ma esiste.
        Il numero e' l'identita', il nome e' un'etichetta: vince il numero."""
        assert eda_tools._risolvi(pin_in_cache, "2") == "2"

    def test_maiuscole_indifferenti(self, pin_in_cache):
        assert eda_tools._risolvi(pin_in_cache, "vout") == "1"

    def test_nome_inesistente_spiega_quali_ci_sono(self, pin_in_cache):
        """L'errore deve insegnare al modello, non solo fermarlo."""
        with pytest.raises(eda_tools.EdaError) as e:
            eda_tools._risolvi(pin_in_cache, "VCC")
        assert "VOUT" in str(e.value)

    def test_connect_rifiuta_un_pin_sbagliato(self, monkeypatch, pin_in_cache):
        """Nessuna scrittura deve partire se anche un solo pin non si risolve:
        una net collegata a meta' e' peggio di una non collegata."""
        chiamate = []
        monkeypatch.setattr(eda_tools, "_project_id", lambda force=False: "p")
        monkeypatch.setattr(eda_tools, "_chiama",
                            lambda *a, **k: chiamate.append(a) or {})
        esito = eda_tools.eda_connect("VCC", [
            {"part": "U1", "pin": "VOUT"},
            {"part": "U1", "pin": "NON_ESISTE"},
        ])
        assert esito["success"] is False
        assert chiamate == []

    def test_connect_passa_i_numeri_risolti(self, monkeypatch, pin_in_cache):
        visti = {}
        monkeypatch.setattr(eda_tools, "_project_id", lambda force=False: "p")

        def finta(tool, args=None, scrittura=False, tentativi=1):
            visti["tool"] = tool
            visti["args"] = args
            return {}

        monkeypatch.setattr(eda_tools, "_chiama", finta)
        esito = eda_tools.eda_connect("VCC", [{"part": "U1", "pin": "VOUT"},
                                              {"part": "U1", "pin": "+VS"}])
        assert esito["success"] is True
        assert visti["tool"] == "easyeda_schematic_connect_pins_by_net"
        assert visti["args"]["pins"] == [
            {"primitiveId": "U1", "pinNumber": "1"},
            {"primitiveId": "U1", "pinNumber": "5"},
        ]


# ---------------------------------------------------------------------------
# Si piazza solo cio' che si e' trovato
# ---------------------------------------------------------------------------

class TestPiazzamentoVincolato:
    """Il primo run vero ha messo sul foglio un microcontrollore e due
    regolatori che non c'entravano col compito, senza che nessuna chiamata
    fallisse: la ricerca continuava a cadere e l'agente e' andato avanti lo
    stesso. Piazzare e' l'unico tool che crea qualcosa dal nulla, quindi e'
    l'unico dove un identificativo non verificato diventa un componente
    estraneo invece di un errore."""

    def test_un_uuid_mai_cercato_viene_rifiutato(self, monkeypatch):
        monkeypatch.setattr(eda_tools, "_uuid_trovati", set())
        chiamate = []
        monkeypatch.setattr(eda_tools, "_chiama",
                            lambda *a, **k: chiamate.append(a) or {})
        esito = eda_tools.eda_place_part("mai-visto", "lib", 100, 100)
        assert esito["success"] is False
        assert "eda_search_part" in esito["error"]
        assert chiamate == [], "nessuna scrittura deve partire"

    def test_un_uuid_trovato_passa(self, monkeypatch):
        monkeypatch.setattr(eda_tools, "_uuid_trovati", {"abc123"})
        monkeypatch.setattr(eda_tools, "_project_id", lambda force=False: "p")
        monkeypatch.setattr(eda_tools, "_chiama", lambda *a, **k: {
            "components": [{"primitiveId": "p1", "deviceName": "X", "x": 100, "y": 100}],
            "total": 1})
        assert eda_tools.eda_place_part("abc123", "lib", 100, 100)["success"] is True

    def test_la_ricerca_registra_gli_uuid(self, monkeypatch):
        monkeypatch.setattr(eda_tools, "_uuid_trovati", set())
        monkeypatch.setattr(eda_tools, "_project_id", lambda force=False: "p")
        monkeypatch.setattr(eda_tools, "_chiama", lambda *a, **k: {
            "devices": [{"name": "N", "uuid": "u1", "libraryUuid": "l1"}], "total": 1})
        eda_tools.eda_search_part("qualcosa")
        assert "u1" in eda_tools._uuid_trovati

    def test_una_ricerca_fallita_non_abilita_niente(self, monkeypatch):
        """Il caso esatto del primo run: se la ricerca cade, l'insieme resta
        vuoto e il piazzamento successivo non puo' passare."""
        monkeypatch.setattr(eda_tools, "_uuid_trovati", set())
        monkeypatch.setattr(eda_tools, "_project_id", lambda force=False: "p")

        def cade(*a, **k):
            raise RuntimeError("Stream SSE terminato senza una risposta")

        monkeypatch.setattr(eda_tools, "_chiama", cade)
        assert eda_tools.eda_search_part("ADA4938")["success"] is False
        assert eda_tools._uuid_trovati == set()
        assert eda_tools.eda_place_part("indovinato", "l", 1, 1)["success"] is False


# ---------------------------------------------------------------------------
# Scritture: nessun ritentativo
# ---------------------------------------------------------------------------

class TestRitentativi:

    def test_una_scrittura_non_si_ritenta(self, monkeypatch):
        """Un errore di trasporto puo' arrivare DOPO che EasyEDA ha applicato la
        modifica. Ritentare piazzerebbe il componente due volte, e il doppione
        si scopre in fase di montaggio."""
        tentativi = {"n": 0}

        def esplode(tool, payload):
            tentativi["n"] += 1
            raise RuntimeError("trasporto caduto")

        import core.modules.sigma_eda_lab.bridge as bridge
        monkeypatch.setattr(bridge, "call", esplode)
        with pytest.raises(RuntimeError):
            eda_tools._chiama("qualunque", {}, scrittura=True, tentativi=5)
        assert tentativi["n"] == 1

    def test_una_lettura_si_ritenta(self, monkeypatch):
        tentativi = {"n": 0}

        def a_volte(tool, payload):
            tentativi["n"] += 1
            if tentativi["n"] < 3:
                raise RuntimeError("flusso troncato")
            return {"ok": True}

        import core.modules.sigma_eda_lab.bridge as bridge
        monkeypatch.setattr(bridge, "call", a_volte)
        monkeypatch.setattr(eda_tools.time, "sleep", lambda _s: None)
        assert eda_tools._chiama("lettura", {}, tentativi=4) == {"ok": True}
        assert tentativi["n"] == 3


# ---------------------------------------------------------------------------
# Forma delle risposte
# ---------------------------------------------------------------------------

class TestRisposte:

    def test_ogni_esito_dichiara_tool_e_success(self, monkeypatch):
        """Il loop legge `success` per decidere se il turno ha prodotto lavoro."""
        monkeypatch.setattr(eda_tools, "_project_id",
                            lambda force=False: (_ for _ in ()).throw(RuntimeError("giu'")))
        for nome in eda_tools.ESECUTORI:
            esito = eda_tools.esegui(nome, {})
            if esito is None:
                continue
            assert esito["tool"] == nome
            assert isinstance(esito["success"], bool)

    def test_un_guasto_non_solleva_mai(self, monkeypatch):
        """Un'eccezione che sfugge da un tool ferma il run dell'agente."""
        monkeypatch.setattr(eda_tools, "_project_id",
                            lambda force=False: (_ for _ in ()).throw(RuntimeError("giu'")))
        esito = eda_tools.eda_verify()
        assert esito["success"] is False and "giu'" in esito["error"]


class TestPcbTools:

    def test_make_45_deg_path_ortogonale(self):
        from core.modules.sigma_eda_lab.routing import make_45_deg_path
        pts = make_45_deg_path((10.0, 10.0), (50.0, 10.0))
        assert len(pts) == 2
        assert pts[0] == {"x": 10.0, "y": 10.0}
        assert pts[1] == {"x": 50.0, "y": 10.0}

    def test_make_45_deg_path_diagonale(self):
        from core.modules.sigma_eda_lab.routing import make_45_deg_path
        pts = make_45_deg_path((0.0, 0.0), (30.0, 40.0))
        assert len(pts) == 3
        # Tratto a 45 gradi dx=dy, poi ortogonale
        assert pts[0] == {"x": 0.0, "y": 0.0}
        assert pts[2] == {"x": 30.0, "y": 40.0}

    def test_pcb_tools_dispatch(self, monkeypatch):
        monkeypatch.setattr(eda_tools, "_project_id", lambda force=False: "p123")
        for nome in ["eda_pcb_drc", "eda_pcb_unrouted", "eda_pcb_outline"]:
            assert nome in eda_tools.ESECUTORI

    def test_nuovi_tool_nella_policy(self):
        from core.harness import policy
        assert "eda_pcb_drc" in policy.EDA_READ_TOOLS
        assert "eda_pcb_unrouted" in policy.EDA_READ_TOOLS
        assert "eda_pcb_route_net" in policy.EDA_WRITE_TOOLS
        assert "eda_pcb_route_all" in policy.EDA_WRITE_TOOLS
        assert "eda_pcb_mounting_holes" in policy.EDA_WRITE_TOOLS

