# -*- coding: utf-8 -*-
"""Diagnosi concreta: Spark-X2.5 (spark2_5) e pipeline GGUF di Sigma Studio.

Verifica, con output leggibile e riga SIGMA-CHECK finale:
 1. se il backend riconosce l'architettura spark2_5 (convertible_models / compatibilita);
 2. se esiste un percorso di quantizzazione Python puro (llama_cpp) indipendente dal binario motore;
 3. se il frontend espone una via d'azione quando il tooling non e pronto.

Uso:  python tools/verifica_spark.py
Esci con codice != 0 se c'e un problema, e stampa sempre la riga SIGMA-CHECK.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

problemi = []
controllati = 0

# --- 1) Riconoscimento architettura spark2_5 nel backend ---------------------
try:
    from core.engine.gguf_converter import GgufConverter as G
    modelli = set()
    try:
        cm = G.convertible_models
        if callable(cm):
            cm = cm()
        for m in (cm or []):
            nome = m.get("name") if isinstance(m, dict) else getattr(m, "name", None)
            arch = m.get("architecture") if isinstance(m, dict) else getattr(m, "architecture", None)
            if arch:
                modelli.add(str(arch).lower())
            if nome:
                modelli.add(str(nome).lower())
    except Exception as e:  # noqa: BLE001
        problemi.append(f"convertible_models non leggibile: {e}")
    controllati += 1
    ha_spark = any("spark" in x for x in modelli)
    print(f"[1] convertible_models: {len(modelli)} voci, spark presente={ha_spark}")
    if not ha_spark:
        problemi.append("l'architettura spark2_5 non compare tra i modelli convertibili dichiarati")
except Exception as e:  # noqa: BLE001
    controllati += 1
    problemi.append(f"import GgufConverter fallito: {e}")

# --- 2) Percorso quantizzazione Python puro (llama_cpp) ----------------------
try:
    import inspect
    from core.engine.gguf_converter import GgufConverter as G
    src = inspect.getsource(G._quantize)
    controllati += 1
    usa_llamacpp = "llama_cpp" in src or "Llama" in src
    usa_binario = ("_quantize_binario" in src) or ("subprocess" in src) or ("Popen" in src)
    print(f"[2] _quantize: usa_llama_cpp={usa_llamacpp}, usa_binario={usa_binario}")
    if not usa_llamacpp:
        problemi.append("_quantize non contiene un fallback Python puro (llama_cpp) indipendente dal binario")
except Exception as e:  # noqa: BLE001
    controllati += 1
    problemi.append(f"ispezione _quantize fallita: {e}")

# --- 3) Frontend: via d'azione quando il tooling non e pronto ----------------
try:
    jsx = ROOT / "sigma_studio/src/modules/sigma_model_hub/GgufConverter.jsx"
    testo = jsx.read_text(encoding="utf-8") if jsx.exists() else ""
    controllati += 1
    ha_autoinstall = ("autoInstallTooling" in testo) or ("installTooling" in testo)
    sempre_cliccabile = ("!tooling?.ready" not in testo.split("disabled=")[-1][:200]) if "disabled=" in testo else False
    print(f"[3] frontend: autoInstallTooling={ha_autoinstall}, sempre_cliccabile={sempre_cliccabile}")
    if not ha_autoinstall:
        problemi.append("il frontend non espone una via d'azione (auto-install) quando il tooling non e pronto")
except Exception as e:  # noqa: BLE001
    controllati += 1
    problemi.append(f"lettura frontend fallita: {e}")

# --- Esito ------------------------------------------------------------------
print()
if problemi:
    print("PROBLEMI TROVATI:")
    for p in problemi:
        print(f"  - {p}")
else:
    print("TUTTI I CONTROLLI OK: la pipeline Spark-X2.5 e coperta (riconoscimento + fallback Python + via d'azione UI).")

print(json.dumps({"check": "spark2_5_pipeline", "checked": controllati, "problems": len(problemi)}))
sys.exit(1 if problemi else 0)
