# ==============================================================================
# core/pdf_extractor.py — Estrazione testo universale da file PDF
# Sigma Studio v8
# ==============================================================================
"""Estrae testo leggibile e formattato da documenti PDF.

Utilizza PyMuPDF (`fitz`), la libreria C++ ad alte prestazioni gia' presente
nell'ambiente, gestendo sia percorsi su disco, sia buffer di byte grezzi,
sia stringhe codificate in Base64 / Data URL provenienti dal frontend.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Optional, Union

from core.logger import get_logger

log = get_logger("pdf_extractor")


def estrai_testo_pdf(
    sorgente: Union[str, Path, bytes],
    max_pagine: int = 100,
    max_caratteri: int = 120000,
) -> str:
    """Estrae il testo da un PDF (percorso, bytes o data-URL base64).

    Restituisce una stringa Markdown strutturata pagina per pagina,
    adatta al contesto degli LLM.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        log.warning("[PDFExtractor] PyMuPDF non disponibile: %s", exc)
        return "[PDF: modulo di estrazione PyMuPDF non disponibile]"

    doc = None
    try:
        if isinstance(sorgente, bytes):
            doc = fitz.open(stream=sorgente, filetype="pdf")
        elif isinstance(sorgente, Path):
            if not sorgente.is_file():
                return f"[PDF non trovato: {sorgente}]"
            doc = fitz.open(str(sorgente))
        elif isinstance(sorgente, str):
            testo = sorgente.strip()
            # Gestione Data URL (es. data:application/pdf;base64,JVBERi0xLjQK...)
            if testo.startswith("data:") and "base64," in testo:
                parte_b64 = testo.split("base64,", 1)[1]
                dati_binari = base64.b64decode(parte_b64)
                doc = fitz.open(stream=dati_binari, filetype="pdf")
            # Gestione stringa base64 pura (inizia con magic bytes PDF '%PDF' in b64: JVBERi)
            elif testo.startswith("JVBERi") or (len(testo) > 100 and not "\n" in testo and re.match(r"^[A-Za-z0-9+/=]+$", testo)):
                try:
                    dati_binari = base64.b64decode(testo)
                    doc = fitz.open(stream=dati_binari, filetype="pdf")
                except Exception:
                    p = Path(sorgente)
                    if p.is_file():
                        doc = fitz.open(str(p))
                    else:
                        return f"[PDF non decodificabile: {sorgente[:100]}...]"
            else:
                p = Path(sorgente)
                if p.is_file():
                    doc = fitz.open(str(p))
                else:
                    return f"[PDF non trovato: {sorgente}]"
        else:
            return "[PDF: tipo di sorgente non supportato]"

        tot_pagine = len(doc)
        if tot_pagine == 0:
            return "[PDF: documento privo di pagine]"

        sezioni = []
        tot_caratteri = 0
        pagine_da_leggere = min(tot_pagine, max_pagine)

        for idx in range(pagine_da_leggere):
            pagina = doc[idx]
            testo_pagina = pagina.get_text("text").strip()
            if testo_pagina:
                sezioni.append(f"### Pagina {idx + 1} di {tot_pagine}\n{testo_pagina}")
                tot_caratteri += len(testo_pagina)
                if tot_caratteri >= max_caratteri:
                    sezioni.append(
                        f"\n*[Estratto limitato a {tot_caratteri} caratteri per rispettare il limite di contesto. "
                        f"Totale pagine lette: {idx + 1}/{tot_pagine}]*"
                    )
                    break

        if not sezioni:
            return (
                f"[PDF: nessuna informazione testuale estraibile su {tot_pagine} pagine. "
                f"Il documento potrebbe contenere esclusivamente immagini scansionate o vettoriali senza layer OCR.]"
            )

        intestazione = f"**Documento PDF** ({tot_pagine} pagine)\n\n"
        return intestazione + "\n\n".join(sezioni)

    except Exception as exc:
        log.error("[PDFExtractor] Errore durante l'elaborazione del PDF: %s", exc)
        return f"[Errore lettura PDF: {exc}]"
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
