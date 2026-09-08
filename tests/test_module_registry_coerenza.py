"""Il `tabType` di un modulo deve portare alla cartella di quel modulo.

La stessa informazione sta in due posti: il campo `tabType` nel manifest di
ciascun modulo, e la mappa `TAB_TO_FOLDER` scritta a mano in
`sigma_studio/src/modules/registry.js`. Il codice che gira e' la seconda; la
prima e' quella che chi installa un modulo legge e crede.

Oggi concordano. Il problema non e' la divergenza di adesso, e' che niente la
impedisce: un modulo nuovo che dichiara un `tabType` e si dimentica la riga in
`registry.js` viene installato, compare nel catalogo, e apre una scheda vuota.

Unificarle davvero — far generare la mappa dai manifest — significherebbe
riscrivere il caricamento del frontend, che funziona. Questo test costa meno e
copre il caso che fa male: la divergenza diventa un test rosso invece di una
scheda vuota.

La mappa viene letta dal sorgente con un'espressione regolare. Non e' elegante,
ed e' l'unico modo che ha Python di sapere cosa dice un file JavaScript senza
un interprete JavaScript.
"""

import json
import re
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parents[1]
REGISTRY = RADICE / "sigma_studio" / "src" / "modules" / "registry.js"
MANIFEST = sorted((RADICE / "core" / "modules").glob("*/manifest.json"))


def _mappa_dal_registro() -> dict:
    testo = REGISTRY.read_text(encoding="utf-8")
    blocco = re.search(r"const TAB_TO_FOLDER\s*=\s*\{(.*?)\n\};", testo, re.S)
    assert blocco, "TAB_TO_FOLDER non trovata in registry.js"
    coppie = re.findall(r"([A-Za-z_][\w]*)\s*:\s*'([^']+)'", blocco.group(1))
    return dict(coppie)


def _moduli_con_tabtype():
    for percorso in MANIFEST:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        tab = str(dati.get("tabType") or "").strip()
        if tab:
            yield percorso.parent.name, tab


@pytest.mark.skipif(not REGISTRY.is_file(), reason="registry.js non installato")
class TestIlTabTypePortaAlModuloGiusto:
    @pytest.mark.parametrize("cartella,tab_type", list(_moduli_con_tabtype()))
    def test_ogni_modulo_e_raggiungibile_dal_suo_tab_type(self, cartella, tab_type):
        mappa = _mappa_dal_registro()
        assert tab_type in mappa, (
            f"'{cartella}' dichiara tabType '{tab_type}' e registry.js non lo "
            "conosce: il modulo si installa, compare nel catalogo, e apre una "
            "scheda vuota. Aggiungi la riga in TAB_TO_FOLDER."
        )
        assert mappa[tab_type] == cartella, (
            f"'{tab_type}' porta a '{mappa[tab_type]}' invece che a '{cartella}'"
        )

    def test_la_mappa_non_punta_a_moduli_che_non_esistono(self):
        """Un alias verso una cartella assente apre una scheda vuota, e chi lo
        legge crede che il modulo esista."""
        cartelle = {p.name for p in (RADICE / "sigma_studio" / "src" / "modules").iterdir()
                    if p.is_dir()}
        fantasmi = {tab: cart for tab, cart in _mappa_dal_registro().items()
                    if cart not in cartelle}
        # Un modulo non installato e' normale: si segnala solo se non esiste
        # nemmeno lato backend, cioe' se non esiste proprio.
        backend = {p.name for p in (RADICE / "core" / "modules").iterdir() if p.is_dir()}
        inesistenti = {t: c for t, c in fantasmi.items() if c not in backend}
        assert not inesistenti, (
            f"registry.js promette moduli che non esistono: {inesistenti}"
        )

    def test_la_mappa_esiste_e_non_e_vuota(self):
        """La guardia della guardia: se la lettura smettesse di funzionare, i
        test sopra passerebbero a vuoto."""
        assert len(_mappa_dal_registro()) > 10
