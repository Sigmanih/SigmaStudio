"""P3 — Foglio 4: MCU di Supervisione & Bus Digitale.

Collega la RP2350 (MCU di supervisione) con:
- Clock 12MHz (XIN/XOUT)
- Reset (RUN)
- USB-C (USB_DM/USB_DP)
- Bus SPI verso DAC8811 e AD9648
- Chip select dedicati: DAC_CS0, DAC_CS1, ADC_CSB
- Alimentazione IOVDD/DVDD dai rami +3V3A/+1V8D
- GND su tutti i pin di massa

Poi esegue la verifica ERC.
"""
import sys
sys.path.insert(0, ".")

from core.harness.eda_tools import esegui

# ID componenti (da eda_list_parts)
RP2350 = "07aeab213ebe8405"
DAC8811 = "f95c87deebf1a972"
AD9648 = "182e35395bda2ab1"


def collega(net: str, pins: list) -> None:
    r = esegui("eda_connect", {"net": net, "pins": pins})
    status = r.get("success")
    err = r.get("error", "")
    print(f"connect net={net} pins={len(pins)}: {status} {err}")
    if not status:
        raise SystemExit(f"ERRORE collegamento {net}: {err}")


def main() -> int:
    # --- Alimentazione MCU ---
    collega("+3V3A", [
        {"part": RP2350, "pin": "IOVDD"},   # pin 1,11,20,30,38,45 (tutti IOVDD)
    ])
    collega("+1V8D", [
        {"part": RP2350, "pin": "DVDD"},    # pin 6,23,39
    ])
    collega("GND", [
        {"part": RP2350, "pin": "GND"},       # pin 61
        {"part": RP2350, "pin": "VREG_PGND"}, # pin 47
    ])

    # --- Clock 12MHz ---
    collega("CLK_12MHZ_XIN", [{"part": RP2350, "pin": "XIN"}])   # pin 21
    collega("CLK_12MHZ_XOUT", [{"part": RP2350, "pin": "XOUT"}]) # pin 22

    # --- Reset / RUN ---
    collega("RESET_N", [{"part": RP2350, "pin": "RUN"}])  # pin 26

    # --- USB-C ---
    collega("USB_DM", [{"part": RP2350, "pin": "USB_DM"}])  # pin 51
    collega("USB_DP", [{"part": RP2350, "pin": "USB_DP"}])  # pin 52

    # --- Bus SPI verso DAC8811 (DAC_CS0) ---
    collega("SPI_SCLK", [
        {"part": RP2350, "pin": "GPIO17"},   # pin 28 → SCLK
        {"part": DAC8811, "pin": "CLK"},     # pin 1
    ])
    collega("SPI_MOSI", [
        {"part": RP2350, "pin": "GPIO18"},   # pin 29 → MOSI
        {"part": DAC8811, "pin": "SDI"},     # pin 2
    ])
    collega("DAC_CS0", [
        {"part": RP2350, "pin": "GPIO19"},   # pin 31 → CS0
        {"part": DAC8811, "pin": "CS#"},     # pin 8
    ])

    # --- Bus SPI verso AD9648 (ADC_CSB) ---
    collega("ADC_SCLK", [
        {"part": RP2350, "pin": "GPIO20"},   # pin 32 → SCLK ADC
        {"part": AD9648, "pin": "SCLK/DFS"}, # pin 45
    ])
    collega("ADC_CSB", [
        {"part": RP2350, "pin": "GPIO21"},   # pin 33 → CS ADC
        {"part": AD9648, "pin": "CSB"},      # pin 46
    ])

    # --- DAC_CS1 (riservato per secondo DAC) ---
    collega("DAC_CS1", [
        {"part": RP2350, "pin": "GPIO22"},   # pin 34 → CS1
    ])

    # --- QSPI verso flash (opzionale) ---
    collega("QSPI_SCLK", [{"part": RP2350, "pin": "QSPI_SCLK"}])  # pin 56
    collega("QSPI_SS", [{"part": RP2350, "pin": "QSPI_SS"}])      # pin 60

    # --- Verifica ERC finale ---
    r = esegui("eda_verify", {})
    print("verify:", r)
    return 0 if r.get("success") and not r.get("erc_errors") else 1


if __name__ == "__main__":
    raise SystemExit(main())