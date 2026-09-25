# ==============================================================================
# tests/test_tool_providers.py — I tool dei moduli visti dal kernel
# ==============================================================================
"""Il kernel non nomina i moduli, e qui si prova che sia vero.

Fino al 25 settembre 2026 l'elenco dei tool KiCad stava in `tool_schema.py`, la
loro classificazione in `policy.py`, il ruolo che li concedeva in `roles.py`, e
l'esecuzione in `core/harness/kicad_tools.py` — che per funzionare importava
`core.modules.sigma_kicad_lab`. Il kernel dipendeva da un modulo opzionale: con
il modulo disinstallato restavano ventisette tool dichiarati al modello e nessuno
in grado di eseguirli.

Adesso il verso e' uno solo: il modulo chiama `register()`, il kernel chiede
`dispatch()`. Questo file difende quel verso da quattro lati:

- un provider registrato compare davvero nel catalogo, nei permessi e nei ruoli;
- un provider incoerente viene rifiutato *prima* di sporcare il catalogo;
- un provider che solleva non uccide il turno;
- e nessun file del kernel, tolto `core/modules/`, nomina piu' il modulo KiCad.
"""
import ast
from pathlib import Path

import pytest

from core.harness import policy
from core.harness import roles as ruoli
from core.harness import tool_providers as tp
from core.harness import tool_schema as ts


# --- utensili di prova ---------------------------------------------------------

def _schema(nome: str, chiave: str = "value") -> dict:
    return ts.function_schema(nome, f"Tool di prova '{nome}'.",
                              {chiave: ts.STRINGA}, [])


def _provider(id: str = "prova", esecutore=None, letture=(), scritture=(),
              aliases=None, ruoli=()) -> tp.ToolProvider:
    nomi = list(letture) + list(scritture)
    return tp.ToolProvider(
        id=id,
        label="Prova",
        schemas=tuple(_schema(n) for n in nomi),
        execute=esecutore or (lambda nome, args: {"tool": nome, "success": True}),
        read_only=frozenset(letture),
        write=frozenset(scritture),
        aliases=dict(aliases or {}),
        roles=tuple(ruoli),
    )


@pytest.fixture
def pulito():
    """Registra e poi stacca il provider di prova: nessun residuo per gli altri."""
    yield
    tp.unregister("prova")


# --- 1. un provider registrato esiste per il kernel ---------------------------

def test_provider_registrato_entra_in_catalogo_permessi_e_alias(pulito):
    letture = ("prova_alpha",)
    scritture = ("prova_beta",)
    ruoli.register_role(ruoli.DevRole(
        id="prova_ruolo", name="Ruolo di prova", icon="🧪",
        system_prompt="Sei un ruolo di prova.", tools=letture + scritture))

    nomi = tp.register(_provider(letture=letture, scritture=scritture,
                                aliases={"alpha": "prova_alpha"},
                                ruoli=(ruoli.DEV_ROLES["prova_ruolo"],)))
    try:
        assert set(nomi) == {"prova_alpha", "prova_beta"}
        # Il catalogo che il modello vede
        assert {"prova_alpha", "prova_beta"} <= ts.declared_tools()
        assert len(ts.schemas_for(["prova_alpha"])) == 1
        # I permessi
        assert "prova_alpha" in policy.READ_ONLY_TOOLS
        assert "prova_beta" not in policy.READ_ONLY_TOOLS
        assert "prova_beta" in tp.write_tools()
        # Gli alias, compreso quello italiano
        assert policy.canonical("alpha") == "prova_alpha"
        # Il ruolo
        assert "prova_ruolo" in ruoli.DEV_ROLES
    finally:
        ruoli.DEV_ROLES.pop("prova_ruolo", None)


def test_dispatch_esegue_solo_i_tool_dei_provider(pulito):
    tp.register(_provider(letture=("prova_alpha",)))
    assert tp.dispatch("prova_alpha", {}) == {"tool": "prova_alpha",
                                              "success": True}
    # Un tool del kernel non e' di nessun provider: None, cosi' il ciclo
    # prosegue e non ruba la chiamata a chi la sa eseguire.
    assert tp.dispatch("read_file", {}) is None
    assert tp.dispatch("tool_che_non_esiste", {}) is None



# --- 2. i provider incoerenti si rifiutano prima di sporcare il catalogo -------

def test_un_provider_che_non_dice_chi_scrive_viene_rifiutato(pulito):
    incompleto = tp.ToolProvider(
        id="prova", label="Prova", schemas=(_schema("prova_alpha"),),
        execute=lambda n, a: {"tool": n, "success": True})
    with pytest.raises(tp.ProviderError) as errore:
        tp.register(incompleto)
    assert "prova_alpha" in str(errore.value)
    # E non ha lasciato niente dietro di se'.
    assert "prova_alpha" not in ts.declared_tools()


def test_un_nome_gia_del_kernel_non_si_rivendica(pulito):
    with pytest.raises(tp.ProviderError) as errore:
        tp.register(_provider(letture=("read_file",)))
    assert "read_file" in str(errore.value)
    assert tp.owner("read_file") is None


def test_un_alias_verso_un_tool_inesistente_viene_rifiutato(pulito):
    with pytest.raises(tp.ProviderError) as errore:
        tp.register(_provider(letture=("prova_alpha",),
                              aliases={"alpha": "prova_gamma"}))
    assert "prova_gamma" in str(errore.value)


def test_un_provider_senza_esecutore_viene_rifiutato(pulito):
    with pytest.raises(tp.ProviderError):
        tp.register(tp.ToolProvider(id="prova", label="Prova",
                                    schemas=(_schema("prova_alpha"),),
                                    execute=None))


# --- 3. un provider che sbaglia non uccide il turno ---------------------------

def test_un_provider_che_solleva_torna_come_esito_fallito(pulito):
    def esplode(nome, args):
        raise RuntimeError("la scheda non si apre")

    tp.register(_provider(letture=("prova_alpha",), esecutore=esplode))
    esito = tp.dispatch("prova_alpha", {})
    assert esito["success"] is False
    assert "la scheda non si apre" in esito["error"]
    assert esito["tool"] == "prova_alpha"


def test_un_provider_che_non_esegue_lo_dichiara(pulito):
    tp.register(_provider(letture=("prova_alpha",),
                          esecutore=lambda n, a: None))
    esito = tp.dispatch("prova_alpha", {})
    assert esito["success"] is False
    assert "prova" in esito["error"]


# --- 4. registrare due volte aggiorna, non duplica ---------------------------

def test_la_seconda_registrazione_sostituisce_la_prima(pulito):
    tp.register(_provider(letture=("prova_alpha",)))
    tp.register(_provider(letture=("prova_alpha",), scritture=("prova_beta",)))
    assert tp.owner("prova_alpha") == "prova"
    assert tp.owner("prova_beta") == "prova"
    nomi = [s["function"]["name"] for s in ts.TOOL_SCHEMAS]
    assert nomi.count("prova_alpha") == 1, "lo schema e' rimasto due volte"


def test_unregister_toglie_tutto(pulito):
    tp.register(_provider(letture=("prova_alpha",)))
    assert tp.unregister("prova") is True
    assert tp.owner("prova_alpha") is None
    assert "prova_alpha" not in ts.declared_tools()
    assert tp.unregister("prova") is False


# --- 5. il kernel non nomina il modulo, e non lo importa ---------------------

def _file_del_kernel() -> list:
    """I file Python del kernel: tutto `core/`, meno `core/modules/`."""
    from core import paths
    radice = Path(paths.project_root()) / "core"
    return sorted(p for p in radice.rglob("*.py")
                  if "modules" not in p.relative_to(radice).parts
                  and "__pycache__" not in p.parts)


#: Cio' che il kernel non deve contenere. `sigma_model_hub` non compare qui: e'
#: un modulo del kernel per scelta dichiarata in `architettura.md`, e il suo
#: import da `fastapi_app.py` e' precedente a questa regola e fuori da questo
#: lavoro. Il controllo qui sotto lo lascia passare di proposito.
VIETATO_NEL_KERNEL = ("kicad_", "sigma_kicad_lab", "kicad_tools")

#: Debito noto: file del kernel che importano un modulo, con il motivo per cui
#: sono ancora li'. Sono tutti precedenti al 25 settembre 2026 e ognuno e' un
#: lavoro a se': il ponte MCP del Developer Studio e quello Blender di Creative,
#: il valutatore del protocollo di Benchmark, le route di Sigma Network, e i
#: tool EDA — che sono lo stesso caso di KiCad, con sette import invece di
#: ventinove. Vanno tolti uno per volta, e questo elenco e' la lista delle cose
#: da fare: quando un file smette di comparire, la riga qui va cancellata.
DEBITO_DI_IMPORT = {
    "app_manager.py": "core/integrations: il ponte Blender di Creative Lab",
    "eda_tools.py": "i tool EDA stanno ancora nel kernel, come stava KiCad",
    "fastapi_app.py": "le route di Sigma Network accanto a quelle di Model Hub",
    "loop.py": "il ponte MCP del Developer Studio, letto per comporre i tool",
    "protocol_bench.py": "il valutatore del protocollo di Benchmark Lab",
}


def test_il_kernel_non_nomina_il_modulo_kicad():
    file_esaminati = _file_del_kernel()
    assert file_esaminati, "nessun file esaminato: il controllo non ha guardato niente"
    colpevoli = {}
    for percorso in file_esaminati:
        testo = percorso.read_text(encoding="utf-8", errors="replace")
        for parola in VIETATO_NEL_KERNEL:
            if parola in testo:
                colpevoli[percorso.name] = parola
    print(f'SIGMA-CHECK {{"check": "kernel-senza-kicad", '
          f'"checked": {len(file_esaminati)}, "problems": {len(colpevoli)}}}')
    assert not colpevoli, (
        f"Il kernel nomina il modulo KiCad in {len(colpevoli)} file su "
        f"{len(file_esaminati)}: {colpevoli}")


def test_il_kernel_non_importa_i_moduli():
    """Nessun `import` di `core.modules.*` sotto `core/`, tolto `core/modules/`.

    Letto con `ast` e non col testo: un commento che nomina un modulo non e' una
    dipendenza, e un controllo che confonde i due si impara a ignorarlo.

    Il controllo e' una cricca, non un ideale: il debito qui sotto e' reale e
    dichiarato, e un file che non sta nell'elenco e importa un modulo fa
    fallire la prova. Cosi' il prossimo accoppiamento non entra di nascosto —
    che e' come e' entrato quello di KiCad, con un file alla volta.
    """
    file_esaminati = _file_del_kernel()
    assert file_esaminati, "nessun file esaminato: il controllo non ha guardato niente"
    colpevoli = {}
    for percorso in file_esaminati:
        try:
            albero = ast.parse(percorso.read_text(encoding="utf-8",
                                                  errors="replace"))
        except SyntaxError as exc:      # pragma: no cover - non deve accadere
            colpevoli[percorso.name] = {f"illeggibile: {exc}"}
            continue
        for nodo in ast.walk(albero):
            if isinstance(nodo, ast.ImportFrom):
                moduli = [nodo.module or ""]
            elif isinstance(nodo, ast.Import):
                moduli = [alias.name for alias in nodo.names]
            else:
                continue
            for modulo in moduli:
                if modulo.startswith("core.modules") and \
                        not modulo.startswith("core.modules.sigma_model_hub"):
                    colpevoli.setdefault(percorso.name, set()).add(modulo)
    nuovi = {nome: moduli for nome, moduli in colpevoli.items()
             if nome not in DEBITO_DI_IMPORT}
    print(f'SIGMA-CHECK {{"check": "kernel-senza-import-di-moduli", '
          f'"checked": {len(file_esaminati)}, "problems": {len(nuovi)}, '
          f'"debito_noto": {len(colpevoli) - len(nuovi)}}}')
    assert not nuovi, (
        f"{len(nuovi)} file del kernel importano un modulo senza che sia debito "
        f"dichiarato: {nuovi}")
    # Il debito dichiarato resta visibile: se sparisce, va tolto da qui.
    svaniti = set(DEBITO_DI_IMPORT) - set(colpevoli)
    assert not svaniti, (
        f"questi file non importano piu' moduli: toglieteli da DEBITO_DI_IMPORT "
        f"({', '.join(sorted(svaniti))})")
