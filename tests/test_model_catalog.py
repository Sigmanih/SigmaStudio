# ==============================================================================
# tests/test_model_catalog.py — Scegliere il modello di partenza
# ==============================================================================
"""Copre core/training/model_catalog.py.

Il catalogo esiste per una ragione sola: dire in anticipo cosa si può fare con
un modello. Sbagliare l'accoppiamento tra il tag Ollama e i pesi, o dichiarare
addestrabile un repo di soli GGUF, si paga un'ora dopo — a metà di una
profilazione, quando il training non parte.
"""

import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.training import model_catalog as mc


# ==============================================================================
# ACCOPPIAMENTO DELLE DUE IDENTITÀ
# ==============================================================================

@pytest.mark.parametrize("ollama, repo", [
    ("qwen2.5:0.5b-instruct", "Qwen/Qwen2.5-0.5B-Instruct"),
    ("gemma4:12b", "google/Gemma4-12B"),
    ("sigma_Qwythos_gsm8k:latest", "sigma_qwythos_gsm8k"),
])
def test_stesso_modello_scritto_dalle_due_comunita(ollama, repo):
    """Ollama e HuggingFace nominano lo stesso modello in modo diverso."""
    assert mc._fingerprint(ollama) == mc._fingerprint(repo)


def test_modelli_diversi_non_si_accoppiano():
    """L'impronta non deve appiattire distinzioni che contano."""
    assert mc._fingerprint("qwen3:8b") != mc._fingerprint("qwen3:14b")
    assert mc._fingerprint("llama-3.2-1b") != mc._fingerprint("llama-3.2-3b")


# ==============================================================================
# COSA SI PUÒ FARE CON UNA VOCE
# ==============================================================================

def test_voce_completa_e_pronta():
    e = mc._entry("cache", "Qwen/Q", train_model="Qwen/Q", eval_model="q:latest")
    assert e["ready"] and e["can_train"] and e["can_eval"]
    assert e["missing"] == ""


def test_solo_ollama_si_misura_ma_non_si_specializza():
    e = mc._entry("ollama", "misterioso:latest", train_model="", eval_model="misterioso:latest")
    assert e["can_eval"] and not e["can_train"] and not e["ready"]
    assert "non individuati" in e["missing"]


def test_solo_pesi_avverte_che_manca_ollama():
    e = mc._entry("hf", "org/modello", train_model="org/modello", eval_model="")
    assert e["can_train"] and not e["can_eval"] and not e["ready"]
    assert "Ollama" in e["missing"]


def test_l_import_e_annunciato_col_suo_costo():
    """L'import lo fa il ciclo, ma quanto costa cambia: un GGUF si scarica e
    basta, dei safetensors vanno anche convertiti. Chi guarda deve saperlo
    prima di premere Avvia, non dopo venti minuti."""
    con = mc._entry("hf", "org/m", train_model="org/m", eval_model="", gguf=True)
    senza = mc._entry("hf", "org/m", train_model="org/m", eval_model="", gguf=False)
    assert "si scarica e basta" in con["missing"]
    assert "conversione" in senza["missing"]


def test_un_modello_senza_nessuna_delle_due_identita_e_inutilizzabile():
    e = mc._entry("hf", "org/solo-gguf", train_model="", eval_model="", gguf=True)
    assert not e["can_train"] and not e["can_eval"]
    assert "né misurare né specializzare" in e["missing"]


# ==============================================================================
# RICONOSCERE UN MODELLO DI LINGUAGGIO
# ==============================================================================

def scrivi_config(tmp_path, payload):
    f = tmp_path / "config.json"
    f.write_text(json.dumps(payload), encoding="utf-8")
    return f


@pytest.mark.parametrize("arch", [
    "Qwen2ForCausalLM",
    "GPT2LMHeadModel",
    # Qwythos, il modello da cui partiamo davvero, si dichiara cosi'.
    "Qwen3_5ForConditionalGeneration",
])
def test_i_generatori_di_testo_entrano_nel_catalogo(tmp_path, arch):
    assert mc._is_causal_lm(scrivi_config(tmp_path, {"architectures": [arch]}))


@pytest.mark.parametrize("arch", ["CLIPModel", "DiffusionGemmaForBlockDiffusion"])
def test_la_cache_e_piena_di_roba_che_non_e_un_llm(tmp_path, arch):
    """Stable Diffusion e CLIP passano dalla stessa cache: proporli come base
    di un ciclo di training testuale sarebbe solo rumore."""
    assert not mc._is_causal_lm(scrivi_config(tmp_path, {"architectures": [arch]}))


def test_config_illeggibile_non_fa_esplodere_il_catalogo(tmp_path):
    rotto = tmp_path / "config.json"
    rotto.write_text("{ non e' json", encoding="utf-8")
    assert not mc._is_causal_lm(rotto)
    assert not mc._is_causal_lm(tmp_path / "inesistente.json")


# ==============================================================================
# RICERCA SU HUGGINGFACE
# ==============================================================================

class FintaRisposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def hf(monkeypatch):
    """Sostituisce la rete: la ricerca si prova sulle risposte, non su HuggingFace."""
    catturato = {}

    def risposte(payload):
        def fake_urlopen(req, timeout=None):
            catturato["url"] = req.full_url
            return FintaRisposta(json.dumps(payload).encode("utf-8"))
        monkeypatch.setattr(mc, "_urlopen", lambda: fake_urlopen)
        monkeypatch.setattr(mc, "_ollama_index", lambda: {})
        return catturato

    return risposte


def repo(rid, files, downloads=10, **extra):
    return {"id": rid, "downloads": downloads, "likes": 1,
            "siblings": [{"rfilename": f} for f in files], **extra}


def test_un_repo_di_soli_gguf_non_e_addestrabile(hf):
    hf([repo("org/solo-gguf", ["model.Q4_K_M.gguf", "README.md"])])
    m = mc.search_hf_models("qualcosa")["models"][0]
    assert m["gguf"] and not m["can_train"]
    assert m["train_model"] == ""


def test_un_repo_con_safetensors_e_addestrabile(hf):
    hf([repo("org/pesi", ["model-00001-of-00002.safetensors", "config.json"])])
    m = mc.search_hf_models("qualcosa")["models"][0]
    assert m["can_train"] and m["train_model"] == "org/pesi"


def test_i_repo_privati_non_entrano_in_lista(hf):
    hf([repo("org/pubblico", ["model.safetensors"]),
        repo("org/privato", ["model.safetensors"], private=True)])
    ids = [m["label"] for m in mc.search_hf_models("x")["models"]]
    assert ids == ["org/pubblico"]


def test_la_ricerca_chiede_solo_modelli_generativi(hf):
    catturato = hf([])
    mc.search_hf_models("qwen3")
    # Senza il filtro la lista si riempie di encoder e classificatori, che nel
    # ciclo non servono a niente.
    assert "text-generation" in catturato["url"]
    assert "sort=downloads" in catturato["url"]


def test_un_modello_gia_in_ollama_arriva_accoppiato(hf, monkeypatch):
    hf([repo("Qwen/Qwen2.5-0.5B-Instruct", ["model.safetensors"])])
    monkeypatch.setattr(mc, "_ollama_index",
                        lambda: {mc._fingerprint("qwen2.5:0.5b-instruct"):
                                 {"id": "qwen2.5:0.5b-instruct"}})
    m = mc.search_hf_models("qwen")["models"][0]
    assert m["eval_model"] == "qwen2.5:0.5b-instruct"
    assert m["ready"], "entrambe le identita' ci sono: si puo' partire subito"


def test_rete_giu_non_lascia_la_ui_senza_spiegazione(monkeypatch):
    from urllib.error import URLError

    def esplode(req, timeout=None):
        raise URLError("niente rete")
    monkeypatch.setattr(mc, "_urlopen", lambda: esplode)
    monkeypatch.setattr(mc, "_ollama_index", lambda: {})
    out = mc.search_hf_models("qwen")
    assert not out["success"] and out["models"] == []
    assert "HuggingFace" in out["error"]


# ==============================================================================
# CATALOGO LOCALE
# ==============================================================================

def test_i_modelli_gia_coperti_dai_pesi_non_si_ripetono(monkeypatch, tmp_path):
    """Un modello con pesi in cache e tag Ollama e' una voce sola, non due: in
    lista comparirebbe due volte con capacita' diverse."""
    monkeypatch.setattr(mc, "_hf_cache_dir", lambda: tmp_path)
    monkeypatch.setattr(mc, "_job_models", lambda _o: [])
    monkeypatch.setattr(mc, "_ollama_index",
                        lambda: {mc._fingerprint("modello:latest"):
                                 {"id": "modello:latest", "size_gb": 1.0}})
    snap = tmp_path / "models--org--Modello" / "snapshots" / "abc"
    snap.mkdir(parents=True)
    (snap / "config.json").write_text(json.dumps({"architectures": ["LlamaForCausalLM"]}),
                                      encoding="utf-8")
    (snap / "model.safetensors").write_bytes(b"x")

    models = mc.local_models()["models"]
    assert len(models) == 1
    assert models[0]["source"] == "cache" and models[0]["ready"]


def test_i_pronti_stanno_in_cima(monkeypatch):
    """La lista serve a partire: chi e' utilizzabile subito va visto per primo."""
    monkeypatch.setattr(mc, "_cached_models", lambda _o: [
        mc._entry("cache", "solo-pesi", train_model="org/x", eval_model=""),
        mc._entry("cache", "pronto", train_model="org/y", eval_model="y:latest"),
    ])
    monkeypatch.setattr(mc, "_job_models", lambda _o: [])
    monkeypatch.setattr(mc, "_ollama_index", lambda: {mc._fingerprint("z:latest"): {"id": "z:latest"}})
    etichette = [m["label"] for m in mc.local_models()["models"]]
    assert etichette[0] == "pronto"
    assert etichette.index("solo-pesi") < etichette.index("z:latest")


# ==============================================================================
# PORTARE UN MODELLO IN OLLAMA
# ==============================================================================

def test_un_repo_huggingface_va_nominato_come_tale(monkeypatch):
    """`ollama pull org/repo` cerca nella libreria di Ollama e risponde
    'not found': il prefisso hf.co non e' un dettaglio estetico."""
    avviati = []
    monkeypatch.setattr(mc.threading, "Thread",
                        lambda **kw: type("T", (), {"start": lambda _s: avviati.append(kw["args"])})())
    out = mc.pull_to_ollama("org/repo")
    assert out["success"] and out["model"] == "hf.co/org/repo"
    mc._pull_state["running"] = False


def test_un_tag_ollama_resta_intatto(monkeypatch):
    monkeypatch.setattr(mc.threading, "Thread",
                        lambda **kw: type("T", (), {"start": lambda _s: None})())
    assert mc.pull_to_ollama("qwen3:8b")["model"] == "qwen3:8b"
    mc._pull_state["running"] = False


def test_due_download_insieme_non_si_avviano(monkeypatch):
    monkeypatch.setattr(mc.threading, "Thread",
                        lambda **kw: type("T", (), {"start": lambda _s: None})())
    mc.pull_to_ollama("org/uno")
    secondo = mc.pull_to_ollama("org/due")
    assert not secondo["success"] and "già un download" in secondo["error"]
    mc._pull_state["running"] = False


def test_senza_modello_non_si_scarica_niente():
    assert not mc.pull_to_ollama("")["success"]


# ==============================================================================
# IMPORT AUTOMATICO DA HUGGINGFACE
# ==============================================================================

@pytest.mark.parametrize("repo, atteso", [
    ("sapienzanlp/Minerva-1B-base-v1.0", "sigma-minerva-1b-base-v1.0"),
    ("Qwen/Qwen2.5-0.5B-Instruct", "sigma-qwen2.5-0.5b-instruct"),
    ("gpt2", "sigma-gpt2"),
])
def test_il_nome_ollama_si_ricava_dal_repo(repo, atteso):
    """Ollama rifiuta le maiuscole e legge lo slash come namespace: il nome va
    tradotto, non copiato."""
    assert mc.ollama_name_for(repo) == atteso


def test_un_repo_con_gguf_evita_del_tutto_la_conversione(monkeypatch):
    """La via corta esiste e va presa: convertire quando non serve costa
    minuti di CPU e il doppio dello spazio su disco."""
    chiamate = []
    monkeypatch.setattr(mc, "_has_gguf", lambda r: True)
    monkeypatch.setattr(mc, "_pull_worker", lambda m, url: chiamate.append(m))
    mc._import_worker("org/con-gguf", "sigma-x", "q4_K_M")
    assert chiamate == ["hf.co/org/con-gguf"]


def test_senza_gguf_si_scarica_e_si_registra(monkeypatch, tmp_path):
    import types

    monkeypatch.setattr(mc, "_has_gguf", lambda r: False)
    hub = types.ModuleType("huggingface_hub")
    hub.snapshot_download = lambda repo, **k: str(tmp_path)
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    registrati = []
    jobs = types.ModuleType("core.training.jobs")
    jobs.register_ollama_model = lambda p, n, **k: (registrati.append((str(p), n, k)),
                                                    {"success": True})[1]
    monkeypatch.setitem(sys.modules, "core.training.jobs", jobs)

    mc._pull_state.update(running=True, error="", done=False)
    mc._import_worker("org/pesi", "sigma-pesi", "q4_K_M")
    assert registrati and registrati[0][1] == "sigma-pesi"
    assert mc._pull_state["done"] and not mc._pull_state["error"]
    mc._pull_state.update(running=False, done=False)


def test_un_import_fallito_lascia_il_motivo(monkeypatch, tmp_path):
    import types

    monkeypatch.setattr(mc, "_has_gguf", lambda r: False)
    hub = types.ModuleType("huggingface_hub")
    hub.snapshot_download = lambda repo, **k: str(tmp_path)
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    jobs = types.ModuleType("core.training.jobs")
    jobs.register_ollama_model = lambda p, n, **k: {"success": False,
                                                    "error": "architettura sconosciuta"}
    monkeypatch.setitem(sys.modules, "core.training.jobs", jobs)

    mc._pull_state.update(running=True, error="", done=False)
    mc._import_worker("org/pesi", "sigma-pesi", "")
    assert "architettura sconosciuta" in mc._pull_state["error"]
    assert not mc._pull_state["done"]
    mc._pull_state.update(running=False, error="")


def test_un_modello_gia_in_ollama_non_si_reimporta(monkeypatch):
    """Ricominciare un ciclo su un modello gia' importato non deve riscaricare
    dieci giga."""
    monkeypatch.setattr(mc, "_ollama_index",
                        lambda: {mc._fingerprint("sigma-gpt2"): {"id": "sigma-gpt2"}})
    monkeypatch.setattr(mc, "import_hf_model",
                        lambda *a, **k: pytest.fail("non deve reimportare"))
    out = mc.ensure_ollama_identity("gpt2")
    assert out["success"] and out["already"] and out["model_name"] == "sigma-gpt2"


def test_i_link_della_cache_diventano_file_veri(tmp_path, monkeypatch):
    """`ollama create` rifiuta i file della cache HuggingFace — sono link a
    ../../blobs e il percorso esce dalla cartella del modello: *insecure path*.
    Vanno materializzati, ma senza pagarli una seconda volta in spazio."""
    monkeypatch.setattr(mc, "BASE_DIR", tmp_path)
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    (blobs / "sha123").write_bytes(b"pesi veri")
    snap = tmp_path / "snap"
    snap.mkdir()
    try:
        (snap / "model.safetensors").symlink_to(blobs / "sha123")
    except (OSError, NotImplementedError):
        pytest.skip("questo sistema non concede i symlink")
    (snap / "config.json").write_text("{}", encoding="utf-8")

    dest = mc._flatten(snap, "org/Modello")
    assert (dest / "model.safetensors").read_bytes() == b"pesi veri"
    assert not (dest / "model.safetensors").is_symlink()
    assert dest.name == "org--Modello"


def test_il_gguf_intermedio_non_resta_sul_disco(tmp_path):
    """Dopo `ollama create` il file e' copiato nell'archivio di Ollama: la
    nostra copia da qualche giga fa solo scendere lo spazio libero sotto la
    soglia a cui il ciclo si ferma."""
    (tmp_path / "org--M-f16.gguf").write_bytes(b"x" * 2048)
    (tmp_path / "org--M" ).mkdir()
    liberati = mc._scarta_intermedi(tmp_path, "org/M")
    assert not list(tmp_path.glob("*.gguf"))
    assert (tmp_path / "org--M").is_dir(), "i pesi in hardlink restano"
    assert liberati >= 0


def test_un_modello_importato_da_noi_resta_accoppiato(monkeypatch, tmp_path):
    """Dopo l'import il modello si chiama `sigma-<nome>`: cercarlo solo col
    nome originale lo faceva sembrare non accoppiato, e la voce Ollama
    ricompariva come una seconda riga."""
    monkeypatch.setattr(mc, "_hf_cache_dir", lambda: tmp_path)
    monkeypatch.setattr(mc, "_job_models", lambda _o: [])
    monkeypatch.setattr(mc, "_ollama_index",
                        lambda: {mc._fingerprint("sigma-minerva-1b-base-v1.0:latest"):
                                 {"id": "sigma-minerva-1b-base-v1.0:latest"}})
    snap = tmp_path / "models--sapienzanlp--Minerva-1B-base-v1.0" / "snapshots" / "a"
    snap.mkdir(parents=True)
    (snap / "config.json").write_text(json.dumps({"architectures": ["MistralForCausalLM"]}),
                                      encoding="utf-8")
    (snap / "model.safetensors").write_bytes(b"x")

    models = mc.local_models()["models"]
    assert len(models) == 1, "una voce sola, non due"
    assert models[0]["ready"]
    assert models[0]["eval_model"] == "sigma-minerva-1b-base-v1.0:latest"


# ==============================================================================
# MODELLI CON ARCHITETTURA PROPRIA
# ==============================================================================

def test_un_auto_map_significa_codice_da_eseguire(tmp_path):
    """`auto_map` rimanda a moduli Python che stanno nel repo: transformers li
    importa, e senza `trust_remote_code` si rifiuta. Va detto prima di lanciare
    il job, non scoperto dal traceback."""
    con = tmp_path / "con.json"
    con.write_text(json.dumps({
        "architectures": ["AILOLoopForCausalLM"],
        "auto_map": {"AutoConfig": "configuration_ailo.AILOConfig"},
    }), encoding="utf-8")
    senza = tmp_path / "senza.json"
    senza.write_text(json.dumps({"architectures": ["LlamaForCausalLM"]}), encoding="utf-8")
    assert mc._wants_custom_code(con)
    assert not mc._wants_custom_code(senza)


def test_la_ricerca_chiede_la_config_altrimenti_non_lo_saprebbe(hf):
    """Senza `config=true` la risposta di HuggingFace non porta `auto_map`, e
    un modello con architettura propria sembrerebbe normale."""
    catturato = hf([])
    mc.search_hf_models("ailo")
    assert "config=true" in catturato["url"]


def test_il_codice_proprio_arriva_nella_voce(hf):
    hf([{"id": "org/strano", "downloads": 1, "likes": 0,
         "siblings": [{"rfilename": "model.safetensors"},
                      {"rfilename": "modeling_strano.py"}],
         "config": {"auto_map": {"AutoModelForCausalLM": "modeling_strano.X"}}}])
    m = mc.search_hf_models("strano")["models"][0]
    assert m["custom_code"] is True


# ==============================================================================
# REPO SENZA TOKENIZER
# ==============================================================================

def test_un_repo_a_posto_non_viene_toccato(monkeypatch):
    """Il caso normale deve costare zero: nessun download, nessuna copia."""
    monkeypatch.setattr(mc, "_repo_files",
                        lambda r: ("model.safetensors", "tokenizer.json", "config.json"))
    monkeypatch.setattr(mc, "_flatten",
                        lambda *a: pytest.fail("non deve materializzare niente"))
    assert mc.prepare_trainable_weights("org/normale") == "org/normale"


def test_una_cartella_locale_e_gia_pronta(monkeypatch, tmp_path):
    monkeypatch.setattr(mc, "_repo_files", lambda r: pytest.fail("niente rete"))
    assert mc.prepare_trainable_weights(str(tmp_path)) == str(tmp_path)


def test_senza_niente_da_ricostruire_si_lascia_fallire_il_job(monkeypatch):
    """Inventarsi un vocabolario sarebbe peggio di un errore chiaro."""
    monkeypatch.setattr(mc, "_repo_files", lambda r: ("model.safetensors", "config.json"))
    monkeypatch.setattr(mc, "_flatten", lambda *a: pytest.fail("non deve provarci"))
    assert mc.prepare_trainable_weights("org/monco") == "org/monco"


def test_vocab_e_merges_bastano_a_ricostruire_il_tokenizer(monkeypatch, tmp_path):
    """`vocab.json` + `merges.txt` e' il formato di GPT-2: da li' il tokenizer
    si rifa'. Senza, transformers si ferma su *Couldn't instantiate the backend
    tokenizer* suggerendo di installare sentencepiece — che c'e' gia'."""
    monkeypatch.setattr(mc, "_repo_files",
                        lambda r: ("model.safetensors", "vocab.json", "merges.txt",
                                   "config.json"))
    monkeypatch.setattr(mc, "_cached_weights", lambda r: str(tmp_path))
    preparata = tmp_path / "pronta"
    preparata.mkdir()
    monkeypatch.setattr(mc, "_flatten", lambda snap, repo: preparata)
    (preparata / "config.json").write_text(json.dumps({"eos_token_id": 0}), encoding="utf-8")
    costruiti = []

    class FintoTokenizer:
        def save_pretrained(self, dove):
            costruiti.append(dove)

    monkeypatch.setattr(mc, "_build_bpe_tokenizer", lambda v, m, c: FintoTokenizer())
    out = mc.prepare_trainable_weights("org/senza-tokenizer")
    assert costruiti == [str(preparata)]
    assert out.endswith("pronta")


def test_l_elenco_dei_file_si_chiede_una_volta_sola(monkeypatch):
    """Senza memoria la chiamata parte a ogni creazione di job: la suite di
    test e' passata da 28 a 86 secondi per rileggere sempre gli stessi repo."""
    mc._repo_files.cache_clear()
    chiamate = []

    def finta(req, timeout=None):
        chiamate.append(req.full_url)
        return FintaRisposta(json.dumps({"siblings": [{"rfilename": "a.safetensors"}]})
                             .encode("utf-8"))

    monkeypatch.setattr(mc, "_urlopen", lambda: finta)
    for _ in range(4):
        mc._repo_files("org/ripetuto")
    assert len(chiamate) == 1
    mc._repo_files.cache_clear()


def test_il_riempimento_non_puo_coincidere_con_la_fine_sequenza(monkeypatch):
    """Se pad ed eos sono lo stesso token, nelle etichette non si distingue
    "qui finisce" da "qui non c'e' niente": Unsloth si rifiuta di partire.
    Aggiungerne uno nuovo allargherebbe il vocabolario, e un adapter
    addestrato su un modello allargato non si rifonde piu' sull'originale."""
    from transformers import PreTrainedTokenizerFast

    class FintoGrezzo:
        def __init__(self):
            self.pre_tokenizer = None
            self.decoder = None

        def id_to_token(self, i):
            return {50256: "<|endoftext|>", 188: "\u0100"}.get(i)

        def token_to_id(self, t):
            return 188 if t == "\u0100" else None

    costruito = {}
    monkeypatch.setattr(PreTrainedTokenizerFast, "__init__",
                        lambda self, **k: costruito.update(k))
    monkeypatch.setitem(sys.modules, "tokenizers",
                        _finta_libreria_tokenizers(FintoGrezzo()))

    mc._build_bpe_tokenizer(Path("v.json"), Path("m.txt"),
                            {"eos_token_id": 50256, "pad_token_id": 50256})
    assert costruito["eos_token"] == "<|endoftext|>"
    assert costruito["pad_token"] == "\u0100"
    assert costruito["pad_token"] != costruito["eos_token"]


def _finta_libreria_tokenizers(grezzo):
    import types

    mod = types.ModuleType("tokenizers")
    mod.Tokenizer = lambda modello: grezzo
    mod.models = types.SimpleNamespace(BPE=types.SimpleNamespace(from_file=lambda v, m: None))
    mod.pre_tokenizers = types.SimpleNamespace(ByteLevel=lambda **k: "pre")
    mod.decoders = types.SimpleNamespace(ByteLevel=lambda: "dec")
    return mod
