"""OCR leggero delle vignette MX0 usando cv2 + PIL (no dipendenze pesanti).

Estrae i blocchi di testo dalle nuvolette dei dialoghi e li salva in JSON.
Uso: python tools/_mx0_ocr.py <cartella_capitolo>
"""
import sys
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


def trova_nuvolette(img_path):
    """Rileva le nuvolette dei dialoghi (aree bianche con bordo scuro)."""
    img = cv2.imread(str(img_path))
    if img is None:
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Soglia: bianco alto = nuvoletta
    _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    # Dilata per unire i bordi
    kernel = np.ones((15, 15), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=3)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []
    h, w = gray.shape
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        # Filtra: deve essere abbastanza grande ma non l'intera pagina
        if 5000 < area < (w * h * 0.6) and bw > 80 and bh > 40:
            boxes.append((x, y, bw, bh))
    # Ordina da alto a basso, sinistra a destra (ordine di lettura)
    boxes.sort(key=lambda b: (b[1] // 100, b[0]))
    return boxes


def estrai_testo_nuvoletta(img_path, box):
    """Cerca testo scuro dentro la nuvoletta. Senza OCR vero, restituisce
    un placeholder con le dimensioni dell'area di testo rilevata."""
    x, y, bw, bh = box
    img = cv2.imread(str(img_path))
    if img is None:
        return ""
    crop = img[y:y+bh, x:x+bw]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Conta pixel scuri (probabile testo)
    dark = np.sum(gray < 100)
    total = gray.size
    ratio = dark / max(total, 1)
    if ratio > 0.02:
        return f"[testo rilevato: {int(dark)} px scuri in area {bw}x{bh}]"
    return ""


def main():
    if len(sys.argv) < 2:
        print("Uso: python tools/_mx0_ocr.py <cartella_capitolo>")
        sys.exit(1)
    cartella = Path(sys.argv[1])
    pagine = sorted(cartella.glob("*.jpg")) + sorted(cartella.glob("*.png"))
    if not pagine:
        print(f"Nessuna immagine in {cartella}")
        sys.exit(1)

    risultati = []
    for p in pagine:
        boxes = trova_nuvolette(p)
        voci = []
        for i, box in enumerate(boxes):
            testo = estrai_testo_nuvoletta(p, box)
            voci.append({
                "indice": i + 1,
                "posizione": list(box),
                "testo_rilevato": testo,
                "note": "OCR completo non disponibile: serve easyocr o tesseract"
            })
        risultati.append({
            "pagina": p.name,
            "nuvolette_trovate": len(boxes),
            "dialoghi": voci
        })
        print(f"{p.name}: {len(boxes)} nuvolette")

    out = cartella / "ocr_risultati.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(risultati, f, ensure_ascii=False, indent=2)
    print(f"\nSalvato in {out}")


if __name__ == "__main__":
    main()