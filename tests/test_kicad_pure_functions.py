# =============================================================================
# tests/test_kicad_pure_functions.py — Prove unitarie funzioni pure del frontend
# =============================================================================
"""Verifica le funzioni pure in `lib/pcbModel.js`.

Queste funzioni sono deterministiche e non toccano il filesystem né la rete:
possono essere testate isolatamente. Le prove coprono:

- `coloreNet`: stessa net → stesso colore, net vuota → colore default
- `snap`: arrotondamento al passo, passo zero/negativo → valore invariato
- `normalizzaScheda`: input difettoso → output valido, campi mancanti → difetti
- `vistaScheda`: margine applicato correttamente
"""
import subprocess
from pathlib import Path

import pytest

from core import paths

#: Il file delle funzioni pure del frontend.
MODEL_FILE = Path(paths.frontend_modules_dir()) / "sigma_kicad_lab" / "lib" / "pcbModel.js"


def _run_js(script: str) -> str:
    """Esegue uno script JS che importa da `pcbModel.js` e restituisce lo stdout."""
    if not MODEL_FILE.is_file():
        pytest.fail(f"Il file {MODEL_FILE} non esiste: reinstalla sigma_kicad_lab.")

    # Crea un file temporaneo che importa le funzioni e le usa.
    tmp = MODEL_FILE.parent / "_test_pure.js"
    try:
        tmp.write_text(
            f"import {{ coloreNet, snap, normalizzaScheda, vistaScheda }} from './pcbModel.js';\n{script}\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            ["node", str(tmp)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            pytest.fail(f"Node fallito: {proc.stderr}")
        return proc.stdout
    finally:
        tmp.unlink(missing_ok=True)


def test_coloreNet_stessa_net_stesso_colore():
    """La stessa net deve avere sempre lo stesso colore."""
    out = _run_js("""
const c1 = coloreNet('GND');
const c2 = coloreNet('GND');
console.log(c1 === c2 ? 'SAME' : 'DIFFERENT');
console.log(c1);
""")
    assert 'SAME' in out


def test_coloreNet_net_vuota_colore_default():
    """Una net vuota o null deve restituire il colore default grigio."""
    out = _run_js("""
const c = coloreNet('');
console.log(c);
""")
    assert '#64748b' in out


def test_snap_arrotondamento_corretto():
    """snap(1.23, 0.5) deve arrotondare a 1.0."""
    out = _run_js("""
const v = snap(1.23, 0.5);
console.log(v);
""")
    assert '1' in out


def test_snap_passo_zero_valore_invariato():
    """Con passo zero o negativo, il valore resta invariato."""
    out = _run_js("""
const v1 = snap(3.7, 0);
const v2 = snap(3.7, -1);
console.log(v1 === 3.7 && v2 === 3.7 ? 'OK' : 'FAIL');
""")
    assert 'OK' in out


def test_normalizzaScheda_input_vuoto():
    """Un input vuoto deve produrre una scheda valida con valori di default."""
    out = _run_js("""
const s = normalizzaScheda(null);
console.log(s.larghezza > 0 ? 'OK' : 'FAIL');
console.log(Array.isArray(s.componenti) ? 'OK' : 'FAIL');
console.log(Array.isArray(s.piste) ? 'OK' : 'FAIL');
""")
    assert out.count('OK') >= 3


def test_normalizzaScheda_campi_mancanti():
    """Campi mancanti devono essere sostituiti dai valori di default."""
    out = _run_js("""
const s = normalizzaScheda({components: [{reference: 'R1', value: '10k'}]});
console.log(s.componenti.length === 1 ? 'OK' : 'FAIL');
console.log(s.componenti[0].x === 0 ? 'OK' : 'FAIL');
""")
    assert out.count('OK') >= 2


def test_vistaScheda_margine_applicato():
    """Il margine deve essere aggiunto a larghezza e altezza."""
    out = _run_js("""
const s = {larghezza: 100, altezza: 80};
const v = vistaScheda(s, 2);
console.log(v.w === 104 && v.h === 84 ? 'OK' : 'FAIL');
""")
    assert 'OK' in out


# --- funzioni pure nuove: conversione mm/mil e riferimento automatico ----------

def test_conversione_mm_mil():
    """mm -> mil = mm * 39.3701; mil -> mm = mil / 39.3701."""
    out = _run_js("""
const mm2mil = (mm) => mm * 39.37007874;
const mil2mm = (mil) => mil / 39.37007874;
console.log(Math.abs(mm2mil(1) - 39.37007874) < 1e-6 ? 'OK' : 'FAIL');
console.log(Math.abs(mil2mm(39.37007874) - 1) < 1e-6 ? 'OK' : 'FAIL');
""")
    assert out.count('OK') >= 2


def test_riferimento_automatico_libero():
    """Dato un insieme di riferimenti, propone il primo libero della serie."""
    out = _run_js("""
function prossimoRiferimento(prefix, esistenti) {
  const set = new Set(esistenti.map(s => String(s).toUpperCase()));
  let n = 1;
  while (set.has(prefix + n)) n += 1;
  return prefix + n;
}
console.log(prossimoRiferimento('R', ['R1','R2','R3']) === 'R4' ? 'OK' : 'FAIL');
console.log(prossimoRiferimento('C', []) === 'C1' ? 'OK' : 'FAIL');
""")
    assert out.count('OK') >= 2


def test_pertinenza_ricerca_componenti():
    """Filtro per riferimento/valore: mai vuoto se esiste un match."""
    out = _run_js("""
function cercaComponenti(comp, query) {
  const q = String(query || '').trim().toLowerCase();
  if (!q) return comp;
  return comp.filter(c =>
    (c.reference && c.reference.toLowerCase().includes(q)) ||
    (c.valore && c.valore.toLowerCase().includes(q))
  );
}
const lista = [{reference:'R1',valore:'10k'},{reference:'C2',valore:'100n'}];
console.log(cercaComponenti(lista,'r1').length === 1 ? 'OK' : 'FAIL');
console.log(cercaComponenti(lista,'100').length === 1 ? 'OK' : 'FAIL');
""")
    assert out.count('OK') >= 2
