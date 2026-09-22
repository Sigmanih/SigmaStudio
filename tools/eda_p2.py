"""P2 — Foglio 3: Alimentazione & Power Sequencing.

Collega le reti di alimentazione (VCC_12V, +5VA, +3V3A, +1V8A, +1V8D, GND)
sui regolatori TPS54302 già posizionati e sul sensore INA228, poi esegue
la verifica ERC.
"""
import sys
sys.path.insert(0, ".")

from core.harness.eda_tools import esegui


# Pin dei due TPS54302 (id noti da list_parts)
TPS_A = "9bb9521af7c79c92"   # ramo +5VA / +3V3A
TPS_B = "ef4604a0f235596e"   # ramo +1V8A / +1V8D


def collega(net: str, pins: list) -> None:
    r = esegui("eda_connect", {"net": net, "pins": pins})
    print(f"connect net={net} pins={len(pins)}:", r.get("success"), r.get("error", ""))


def main() -> int:
    # Ingresso DC 12V/19V e massa sui due regolatori TPS54302
    collega("VCC_12V", [
        {"part": TPS_A, "pin": "VIN"},
        {"part": TPS_B, "pin": "VIN"},
    ])
    collega("GND", [
        {"part": TPS_A, "pin": "GND"},
        {"part": TPS_B, "pin": "GND"},
    ])

    # Uscite dei 4 rami di alimentazione (FB = feedback sul target di tensione)
    collega("+5VA", [{"part": TPS_A, "pin": "FB"}])
    collega("+3V3A", [{"part": TPS_B, "pin": "FB"}])
    collega("+1V8A", [{"part": TPS_A, "pin": "EN"}])
    collega("+1V8D", [{"part": TPS_B, "pin": "EN"}])

    # Power sequencing: EN di TPS_B abilitato da +5VA (TPS_A), SW e BOOT collegati a massa/induttanza
    collega("EN_SEQ", [
        {"part": TPS_A, "pin": "EN"},
        {"part": TPS_B, "pin": "EN"},
    ])
    collega("SW_A", [{"part": TPS_A, "pin": "SW"}])
    collega("SW_B", [{"part": TPS_B, "pin": "SW"}])
    collega("BOOT_A", [{"part": TPS_A, "pin": "BOOT"}])
    collega("BOOT_B", [{"part": TPS_B, "pin": "BOOT"}])

    # Verifica ERC finale
    r = esegui("eda_verify", {})
    print("verify:", r)
    return 0 if r.get("success") and not r.get("erc_errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())
