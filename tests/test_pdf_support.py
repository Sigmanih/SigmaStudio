# ==============================================================================
# tests/test_pdf_support.py — Test per estrazione PDF e conoscenza di Sigma Studio
# ==============================================================================
import base64
from pathlib import Path
import pytest
import fitz

from core.pdf_extractor import estrai_testo_pdf
from core.harness.fs_manager import read_file_content
from core.harness.loop import execute_admin_tool
from core.scheda_progetto import scheda, consulta, DOCUMENTI


@pytest.fixture
def pdf_di_test(tmp_path) -> Path:
    """Genera un file PDF reale con 2 pagine di contenuto strutturato."""
    file_path = tmp_path / "documento_test.pdf"
    doc = fitz.open()

    # Pagina 1
    p1 = doc.new_page()
    p1.insert_text(
        (50, 72),
        "Sigma Studio - Documento di Architettura e Sistemi\n"
        "Capitolo 1: Il Kernel di Sigma Studio\n"
        "Il kernel contiene paths, engine, chat, pipeline, mcp, module_loader.\n"
        "Le dipendenze puntano sempre verso il basso.",
        fontsize=12,
    )

    # Pagina 2
    p2 = doc.new_page()
    p2.insert_text(
        (50, 72),
        "Capitolo 2: Test di Lettura PDF per Agenti\n"
        "Questa e' la seconda pagina del documento di verifica.\n"
        "Verifichiamo che l'agente legga al 100% tutte le pagine del file allegato.",
        fontsize=12,
    )

    doc.save(str(file_path))
    doc.close()
    return file_path


class TestEstrazionePDF:
    def test_estrazione_da_file_path(self, pdf_di_test):
        """Verifica estrazione del testo passando un oggetto Path o str."""
        testo = estrai_testo_pdf(pdf_di_test)
        assert "**Documento PDF** (2 pagine)" in testo
        assert "Capitolo 1: Il Kernel di Sigma Studio" in testo
        assert "Capitolo 2: Test di Lettura PDF per Agenti" in testo
        assert "Pagina 1 di 2" in testo
        assert "Pagina 2 di 2" in testo

    def test_estrazione_da_buffer_bytes(self, pdf_di_test):
        """Verifica estrazione da buffer di byte grezzi."""
        dati_bytes = pdf_di_test.read_bytes()
        testo = estrai_testo_pdf(dati_bytes)
        assert "**Documento PDF** (2 pagine)" in testo
        assert "Le dipendenze puntano sempre verso il basso." in testo

    def test_estrazione_da_data_url_base64(self, pdf_di_test):
        """Verifica estrazione da Data URL generato da FileReader.readAsDataURL."""
        dati_bytes = pdf_di_test.read_bytes()
        b64 = base64.b64encode(dati_bytes).decode("utf-8")
        data_url = f"data:application/pdf;base64,{b64}"

        testo = estrai_testo_pdf(data_url)
        assert "**Documento PDF** (2 pagine)" in testo
        assert "Capitolo 1: Il Kernel di Sigma Studio" in testo
        assert "Verifichiamo che l'agente legga al 100%" in testo

    def test_estrazione_da_base64_puro(self, pdf_di_test):
        """Verifica estrazione da stringa base64 priva di prefisso data:."""
        dati_bytes = pdf_di_test.read_bytes()
        b64 = base64.b64encode(dati_bytes).decode("utf-8")

        testo = estrai_testo_pdf(b64)
        assert "**Documento PDF** (2 pagine)" in testo
        assert "Capitolo 2: Test di Lettura PDF per Agenti" in testo

    def test_file_pdf_inesistente(self, tmp_path):
        """Un file inesistente non deve sollevare eccezioni non gestite."""
        esito = estrai_testo_pdf(tmp_path / "fantasma.pdf")
        assert "PDF non trovato" in esito


class TestIntegrazioneHarnessEFSManager:
    def test_read_file_content_estrae_testo_pdf(self, pdf_di_test):
        """read_file_content deve restituire il contenuto estratto e non None."""
        risultato = read_file_content(str(pdf_di_test))
        assert risultato["success"] is True
        assert risultato["is_pdf"] is True
        assert risultato["content"] is not None
        assert "Capitolo 1: Il Kernel di Sigma Studio" in risultato["content"]
        assert "Capitolo 2: Test di Lettura PDF per Agenti" in risultato["content"]
        assert risultato["total_lines"] is not None
        assert risultato["total_lines"] > 0

    def test_admin_tool_read_file_estrae_testo_pdf(self, pdf_di_test):
        """execute_admin_tool('read_file') deve restituire il testo del PDF all'agente."""
        risultato = execute_admin_tool(
            "read_file",
            {"path": str(pdf_di_test)},
            workspace_root=str(pdf_di_test.parent),
        )
        assert risultato["success"] is True
        assert "Capitolo 1: Il Kernel di Sigma Studio" in risultato.get("content", "")


class TestConoscenzaSigmaStudio:
    def test_architettura_md_e_presente_tra_i_documenti_canonici(self):
        """architettura.md deve essere elencato nei documenti canonici del progetto."""
        nomi_doc = [nome for nome, _ in DOCUMENTI]
        assert "architettura.md" in nomi_doc

    def test_consulta_architettura_trova_sezioni_reali(self):
        """La consultazione su architettura deve estrarre le sezioni reali da architettura.md."""
        esito = consulta("architettura")
        assert esito["ok"] is True
        assert len(esito["sezioni"]) > 0
        testo_sezioni = " ".join(s.get("testo", "") for s in esito["sezioni"])
        assert "kernel" in testo_sezioni.lower() or "moduli" in testo_sezioni.lower()

    def test_scheda_progetto_include_kernel_e_ruoli_reali(self):
        """La scheda generata per la chat e l'harness deve contenere i fatti reali."""
        testo_scheda = scheda()
        assert "Sigma Studio" in testo_scheda
        assert "core/harness/" in testo_scheda
        assert "I ruoli dell'harness" in testo_scheda
        assert "architettura.md" in testo_scheda
