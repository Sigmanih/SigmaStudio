"""Crea una copia locale di AILO in safetensors -> ./ailo_backbone

Serve perche':
  - AILO e' pubblicato in formato .bin; transformers con torch < 2.6 (es. l'ambiente
    torch-directml per GPU AMD) rifiuta torch.load dei .bin. La copia safetensors
    aggira il problema.
  - Il generatore Gradus carica automaticamente ./ailo_backbone se presente.

Eseguire UNA volta con un torch >= 2.6 (es. l'ambiente CPU globale):
    python scripts/prepare_ailo_backbone.py
"""
from transformers import AutoModelForCausalLM
from gradus.config import AILO_BACKBONE

DST = "ailo_backbone"


def main():
    print(f"Scarico/converto {AILO_BACKBONE} -> {DST} (safetensors)...")
    m = AutoModelForCausalLM.from_pretrained(AILO_BACKBONE, trust_remote_code=True)
    m.save_pretrained(DST, safe_serialization=True)
    print(f"Fatto. File in ./{DST}/ (model.safetensors + codice custom).")


if __name__ == "__main__":
    main()
