# ==============================================================================
# tests/test_response_parser.py — Unit tests for core/chat/response_parser.py
# ==============================================================================
"""Test JSON extraction, tag cleaning, and thinking extraction."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.chat.response_parser import (
    _clean_all_tags,
    _extract_json_from_response,
    _extract_done_thinking,
    _format_response,
)


class TestExtractJsonFromResponse:
    def test_valid_actions_json(self):
        content = '{"response": "ok", "actions": []}'
        match = _extract_json_from_response(content)
        assert match is not None
        assert '"response"' in match.group()

    def test_valid_tasks_json(self):
        content = '{"response": "planned", "tasks": [{"titolo": "t"}]}'
        match = _extract_json_from_response(content)
        assert match is not None

    def test_valid_done_json(self):
        content = '{"response": "done!", "done": true}'
        match = _extract_json_from_response(content)
        assert match is not None

    def test_no_response_key_returns_none(self):
        content = '{"actions": ["create_file"]}'
        match = _extract_json_from_response(content)
        assert match is None

    def test_invalid_json_returns_none(self):
        # Strings without braces should always return None
        content = "This is plain text with no JSON at all."
        match = _extract_json_from_response(content)
        assert match is None

    def test_json_missing_valid_pair_key_returns_none(self):
        # Has 'response' but no valid paired key
        content = '{"response": "hello", "other": "stuff"}'
        match = _extract_json_from_response(content)
        assert match is None

    def test_json_with_preamble_text(self):
        content = "Sure! Here's the response:\n{\"response\": \"ok\", \"actions\": []}\nDone."
        match = _extract_json_from_response(content)
        assert match is not None

    def test_empty_string_returns_none(self):
        assert _extract_json_from_response("") is None

    def test_none_returns_none(self):
        assert _extract_json_from_response(None) is None


class TestCleanAllTags:
    def test_removes_thinking_tag(self):
        content = "<thinking>I should do X</thinking>The real answer."
        cleaned, thinking = _clean_all_tags(content)
        assert "thinking>" not in cleaned
        assert thinking is not None
        assert "I should do X" in thinking

    def test_removes_response_container_tag(self):
        content = "<response>Hello!</response>"
        cleaned, _ = _clean_all_tags(content)
        assert "<response>" not in cleaned
        assert "Hello!" in cleaned

    def test_done_thinking_marker(self):
        # The exact marker is '...done thinking.' — shorter prefix won't match
        content = "I need to think...done thinking. Here is the answer."
        cleaned, thinking = _clean_all_tags(content)
        assert "Here is the answer" in cleaned

    def test_cleans_excessive_blank_lines(self):
        content = "Line 1\n\n\n\n\nLine 2"
        cleaned, _ = _clean_all_tags(content)
        assert "\n\n\n" not in cleaned

    def test_plain_text_unchanged(self):
        content = "Questa è una risposta normale senza tag."
        cleaned, thinking = _clean_all_tags(content)
        assert cleaned == content
        assert thinking is None


class TestExtractDoneThinking:
    def test_splits_on_marker(self):
        content = "I reasoned about this...done thinking. The actual answer is here."
        response, thinking = _extract_done_thinking(content)
        assert thinking is not None and "I reasoned" in thinking
        assert "actual answer" in response

    def test_no_marker_returns_unchanged(self):
        content = "No marker here at all."
        response, thinking = _extract_done_thinking(content)
        assert response == content
        assert thinking is None


class TestFormatResponse:
    def test_trims_whitespace(self):
        assert _format_response("  hello  ") == "hello"

    def test_cleans_excessive_newlines(self):
        result = _format_response("a\n\n\n\nb")
        assert "\n\n\n" not in result

    def test_none_returns_none(self):
        assert _format_response(None) is None

    def test_bold_span_survives_bullet_normalisation(self):
        """The closing '**' must not be rewritten into a new list item.

        Regression: '* **progetto** — descrizione' came out as
        '* **progetto*' + newline + '* — descrizione', losing one asterisk and
        splitting the line in two.
        """
        text = "* **congettura_di_collatz** — il celebre problema matematico"
        assert _format_response(text) == text

    def test_multiple_bold_spans_in_a_sentence_are_untouched(self):
        text = "Progetti: **sigma_studio** e **formazione_ines** sono attivi."
        assert _format_response(text) == text

    def test_arithmetic_is_not_turned_into_a_list(self):
        text = "Il risultato di 2 * 3 = 6 e l'intervallo 2020 - 2021."
        assert _format_response(text) == text

    def test_inline_bullets_are_still_promoted_to_their_own_line(self):
        assert _format_response("Elenco: * uno * due") == "Elenco:\n* uno\n* due"
        assert _format_response("Voci: - alfa - beta") == "Voci:\n- alfa\n- beta"


class TestFileExtractorDirectPath:
    def test_extract_direct_path_without_backticks(self, tmp_path):
        from core.chat.file_extractor import _extract_and_create_files_from_text
        import shutil
        text = """Ecco una documentazione strutturata per il modulo test_temp_analisi_1/01_base, pronta da salvare in 📄 data/test_temp_analisi_1/01_base/teoria/esponenziali.md. Il contenuto è calibrato sul livello di Analisi Matematica I.

# Funzioni Esponenziali in Analisi Matematica I
📌 *Modulo: test_temp_analisi_1/01_base | Argomento: Teoria delle funzioni elementari
"""
        try:
            created, actions = _extract_and_create_files_from_text(text, prompt_topic="scrivimi una documentazione sugli esponenziali")
            assert len(created) > 0
            assert "esponenziali.md" in created[0]
            assert os.path.exists(created[0])
        finally:
            if os.path.exists("data/test_temp_analisi_1"):
                shutil.rmtree("data/test_temp_analisi_1", ignore_errors=True)

    def test_extract_with_reasoning_monologue(self, tmp_path):
        from core.chat.file_extractor import _extract_and_create_files_from_text
        import shutil
        text = """Here's a thinking process:
Analyze User Input:
- I'll use: 📄 data/test_temp_frattali/01_base/teoria/frattali.md
Final Output Generation: ✅
Path: 📄 data/test_temp_frattali/01_base/teoria/frattali.md

# Frattali: Introduzione, Proprietà e Applicazioni

## 📌 Cos'è un frattale?
Un frattale è una figura geometrica...
"""
        try:
            created, actions = _extract_and_create_files_from_text(text, prompt_topic="scrivimi un file sui frattali")
            assert len(created) > 0
            assert "frattali.md" in created[0]
            assert os.path.exists(created[0])
            with open(created[0], "r", encoding="utf-8") as f:
                content = f.read()
            assert "Frattali: Introduzione" in content
            assert "thinking process" not in content
        finally:
            if os.path.exists("data/test_temp_frattali"):
                shutil.rmtree("data/test_temp_frattali", ignore_errors=True)

    def test_complex_english_thinking_extraction(self):
        sample = """The user is asking "che ne pensi dei moduli?" (what do you think about the modules?). This is a follow-up to the previous conversation about Sigma Studio. The user is Diego Saitta, the developer and creator.

I need to respond in Italian, as Sigma Assistant (front-desk) or perhaps as Sigma Architect since the system prompt has a strong identity as "Sigma Architect, il Lead System Architect e Coordinatore dell'Orchestrazione Cognitiva di Sigma Studio."

Wait, let me re-read the system prompt carefully. There are two identities mixed:
The second one is more specific and detailed.

Let me think about what "moduli" refers to. In the previous response, I listed many modules.
Let me write the final response now.

Ciao Diego Saitta! Come Sigma Architect, ti do la mia lettura architetturale dei moduli di Sigma Studio.

La mia opinione: un'architettura a moduli ben pensata
I moduli di Sigma Studio rappresentano la decisione più importante del sistema."""

        cleaned, thinking = _clean_all_tags(sample)
        assert thinking is not None
        assert "Wait, let me re-read" in thinking
        assert "The user is asking" in thinking
        assert cleaned.startswith("Ciao Diego Saitta!")
        assert "La mia opinione: un'architettura a moduli ben pensata" in cleaned
        assert "Wait, let me re-read" not in cleaned

    def test_need_maybe_thinking_extraction(self):
        sample = """"Ciao, Diego Saitta! Sigma Studio è..."

Need maybe mention "oggi"? Could say "In questo momento, Sigma Studio è..." Not necessary.

Need maybe mention "Sono Sigma Assistant...".

Need maybe mention "Il cuore di Sigma Studio è l'idea che ogni agente AI abbia un'identità operativa definita da un Manifesto/Modelfile...".

Need maybe mention "Puoi usarlo per: conversare, studiare, sviluppare, analizzare dati, creare contenuti, gestire domotica, marketplace, galleria manifesti...".

Need final phrase exactly. Ensure no hidden internal. final.

Ciao, Diego Saitta!

**Sigma Studio** è la piattaforma cognitiva e di laboratorio tecnologico in cui risiedo."""

        cleaned, thinking = _clean_all_tags(sample)
        assert thinking is not None
        assert "Need maybe mention" in thinking
        assert "Ensure no hidden internal" in thinking
        assert cleaned.startswith("Ciao, Diego Saitta!")
        assert "**Sigma Studio** è la piattaforma" in cleaned
        assert "Need maybe" not in cleaned

    def test_think_tag_router_streaming(self):
        from core.chat.chat_runner import _ThinkTagRouter
        router = _ThinkTagRouter()
        
        chunks = [
            "<think>\nNeed maybe ",
            "mention 'oggi'? ",
            "Not necessary.\n",
            "Need final phrase.</think>\n\n",
            "Ciao, Diego Saitta!\n\n",
            "**Sigma Studio** è la piattaforma."
        ]
        
        thinking_parts = []
        token_parts = []
        
        for c in chunks:
            for ch, text in router.feed(c):
                if ch == "thinking":
                    thinking_parts.append(text)
                else:
                    token_parts.append(text)
        for ch, text in router.flush():
            if ch == "thinking":
                thinking_parts.append(text)
            else:
                token_parts.append(text)
                
        full_thinking = "".join(thinking_parts)
        full_token = "".join(token_parts)
        
        assert "Need maybe mention" in full_thinking
        assert "Ciao, Diego Saitta!" in full_token
        assert "**Sigma Studio**" in full_token
        assert "Need maybe" not in full_token
        assert "<think>" not in full_thinking
        assert "</think>" not in full_thinking
        assert "<think>" not in full_token
