# ==============================================================================
# core/chat/response_parser.py — AI Response Cleaning & JSON Extraction
# Extracted from core/chat_handler.py for Single Responsibility
# ==============================================================================
"""Parse, clean and extract structured data from raw AI model responses.

Responsibilities:
    - Strip XML-like thinking/container tags from responses.
    - Detect and separate inline English "thinking process" text.
    - Extract valid operational JSON from free-form model output.
    - Format text for consistent display.
"""

import re
import json

# ---------------------------------------------------------------------------
# Tag pattern registry
# ---------------------------------------------------------------------------

_TAG_PATTERNS: dict[str, list[str]] = {
    "thinking": [
        r"<thinking>(.*?)</thinking>",
        r"<Thought>(.*?)</Thought>",
        r"<reasoning>(.*?)</reasoning>",
        r"<Rationale>(.*?)</Rationale>",
        r"<scratchpad>(.*?)</scratchpad>",
    ],
    "container": [
        r"</?response>", r"</?Response>",
        r"</?output>",   r"</?Output>",
        r"</?answer>",   r"</?Answer>",
        r"</?result>",   r"</?Result>",
        r"</?tool_call>",       r"</?ToolCall>",
        r"</?function_call>",   r"</?FunctionCall>",
    ],
}

# Phrases that signal the START of an English self-analysis section
_THINKING_STARTERS: list[str] = [
    r"^Here\'?s\s+a\s+thinking\s+process\b",
    r"^Here\s+is\s+the\s+thinking\s+process\b",
    r"^Thinking\s+Process:",
    r"^Let\s+me\s+think\s+(?:about|through|step\s+by\s+step)",
    r"^I\'?ll\s+approach\s+this\s+",
    r"^Let\s+me\s+analyze\s+",
]


# ---------------------------------------------------------------------------
# Thinking extractors
# ---------------------------------------------------------------------------

def _extract_english_thinking(content: str) -> tuple[str, str | None]:
    """Detect and extract English 'thinking process' from model responses.

    Some models (Gemma-based, some fine-tunes) produce inline self-analysis
    in English before the actual Italian reply.  This function splits them.

    Returns:
        ``(response_text, thinking_text)`` — *thinking_text* is ``None`` when
        no thinking block was found.
    """
    if not content or not isinstance(content, str):
        return content, None

    for starter in _THINKING_STARTERS:
        if re.search(starter, content.strip(), re.IGNORECASE):
            lines = content.strip().split("\n")
            thinking_lines, response_lines = [], []
            in_thinking = True

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    (thinking_lines if in_thinking else response_lines).append(line)
                    continue

                if in_thinking:
                    is_end = (
                        stripped.startswith("Oggi è")
                        or stripped.startswith("Il link")
                        or stripped.startswith("[SYSTEM")
                        or stripped.startswith("[ANALISI")
                        or stripped.startswith("[SOURCE")
                        or (stripped.startswith("**") and "**" in stripped[2:])
                        or (
                            re.match(r"^[A-ZÀÈÉÌÒÙ][a-zàèéìòù]", stripped)
                            and not re.match(
                                r"^(Here|Let|Think|Analyze|Check|Determine|Formulate|"
                                r"Refine|Self|I\'?ll|I will|Consider|Evaluate|Identify|"
                                r"Note|Observe|Plan|Prepare|Step|The\s+(user|request|"
                                r"query|answer))",
                                stripped, re.IGNORECASE,
                            )
                        )
                    )
                    if is_end and not re.match(r"^\d+\.\s", stripped):
                        in_thinking = False
                        response_lines.append(line)
                    else:
                        thinking_lines.append(line)
                else:
                    response_lines.append(line)

            thinking_text = "\n".join(thinking_lines).strip()
            response_text = "\n".join(response_lines).strip()
            if thinking_text and response_text and len(thinking_text) > len(response_text) * 0.3:
                return response_text, thinking_text

    return content, None


def _extract_bullet_thinking(content: str) -> tuple[str, str | None]:
    """Detect and extract bullet-point style inline thinking."""
    if not content or not isinstance(content, str):
        return content, None

    star_count = content.count("* ")
    has_kw = bool(re.search(
        r"\*\s+(User|Role|Context|System|Option|Creator|Specialization|Tone|Step)",
        content, re.IGNORECASE,
    ))

    if star_count >= 2 and has_kw:
        parts = re.split(r"\*\s+\w+[\w\s,:]*\.\s*(?=[A-Z\(\[\*\"])", content)
        if len(parts) >= 2:
            thinking_text = parts[0].strip()
            response_match = re.search(
                r"(?:(?:Sono|Buongiorno|Salve|Ciao|Ecco|Benvenuto|Il mio|Posso)[^.!?]*[.!?])",
                content[len(thinking_text):],
            )
            if response_match:
                response_start = len(thinking_text) + response_match.start()
                thinking_text = content[:response_start].strip()
                response_text = content[response_start:].strip()
            elif len(parts) > 1:
                response_text = "".join(parts[1:]).strip()
            else:
                response_text = ""

            if thinking_text and response_text and len(thinking_text) > 30 and len(thinking_text) > len(response_text) * 0.2:
                return response_text, thinking_text

        last_star = content.rfind("* ")
        if last_star > 0:
            after = content[last_star:]
            sentence_end = max(after.find(". "), after.find("). "))
            split = last_star + sentence_end + 2 if sentence_end > 0 else last_star + len(after)
            if split < len(content) and split > len(content) * 0.3:
                thinking_text = content[:split].strip()
                response_text = content[split:].strip()
                if thinking_text and response_text and len(thinking_text) > 30:
                    return response_text, thinking_text

    lines = content.strip().split(chr(10))
    if len(lines) < 3:
        return content, None

    bullet_count = sum(
        1 for line in lines[:30]
        if (s := line.strip()) and (
            s.startswith("* ") or s.startswith("- ")
            or (len(s) > 3 and s.lstrip()[0].isdigit() and ". " in s[:5])
            or s.startswith("Option ") or s.startswith("Step ")
            or s.startswith("Self-") or ":" in s[:20]
        )
    )
    has_starter = any(re.search(p, content, re.IGNORECASE) for p in [
        r"^\*\s+User\s+says", r"^\*\s+Context", r"^\*\s+System",
        r"^\*\s+Role", r"^\*\s+Option",
        r"^Here\s+is\s+a\s+thinking", r"^Let\s+me\s+think", r"^Thinking\s+Process",
    ])

    if has_starter or bullet_count >= max(3, len(lines[:20]) // 3):
        th, resp = [], []
        in_th = True
        for line in lines:
            s = line.strip()
            if in_th:
                is_th = (
                    s.startswith("* ") or s.startswith("- ")
                    or (s and s[0].isdigit() and ". " in s[:4])
                    or s == ""
                    or s.lower().startswith((
                        "option ", "step ", "self-", "i ", "my ", "we ",
                        "the ", "this ", "it ", "note:", "in ", "for ", "keep ",
                        "make ", "a ", "an ", "be ", "to ", "is ", "are ", "was ",
                        "were ", "has ", "have ", "had ", "can ", "will ", "may ",
                        "should ", "but ", "so ", "if ", "then ", "else ", "when ",
                        "where ", "how ",
                    ))
                )
                if is_th:
                    th.append(line)
                else:
                    in_th = False
                    resp.append(line)
            else:
                resp.append(line)

        tt = chr(10).join(th).strip()
        rt = chr(10).join(resp).strip()
        if tt and rt and len(tt) > 50:
            return rt, tt

    return content, None


def _extract_done_thinking(content: str) -> tuple[str, str | None]:
    """Split on the ``...done thinking.`` marker used by some Ollama models."""
    if not content or not isinstance(content, str):
        return content, None

    marker = "...done thinking."
    idx = content.find(marker)
    if idx > 0:
        thinking = content[:idx].strip()
        response = content[idx + len(marker):].strip()
        if thinking.lower().startswith("thinking"):
            thinking = thinking[9:].strip()
        if thinking and response and len(thinking) > 20:
            return response, thinking

    lower = content.lower()
    if lower.startswith("thinking..."):
        rest = content[10:]
        for greeting in ("Ciao", "Buongiorno", "Salve", "Ecco", "Sono", "Il mio"):
            g_idx = rest.find(greeting)
            if g_idx > 20:
                thinking = rest[:g_idx].strip()
                response = rest[g_idx:].strip()
                if thinking and response and len(thinking) > 20:
                    return response, thinking

    return content, None


# ---------------------------------------------------------------------------
# Tag cleaner
# ---------------------------------------------------------------------------

def _clean_all_tags(content: str) -> tuple[str, str | None]:
    """Remove all container/thinking tags and extract thinking text.

    Multi-stage pipeline:
    1. Extract thinking from XML-like tags.
    2. Remove container tags.
    3. Split on ``...done thinking.`` marker.
    4. Extract bullet-point thinking.
    5. Extract English thinking process.
    6. Generic XML catch-all.
    7. Clean up excessive blank lines.

    Returns:
        ``(cleaned_response, thinking_text)``
    """
    if not content or not isinstance(content, str):
        return content, None

    extracted: str | None = None
    remaining = content

    # 1 — Extract thinking from XML tags
    for pattern in _TAG_PATTERNS["thinking"]:
        match = re.search(pattern, remaining, re.DOTALL | re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            remaining = re.sub(pattern, "", remaining, flags=re.DOTALL | re.IGNORECASE).strip()
            break

    # 2 — Remove container tags
    for pattern in _TAG_PATTERNS["container"]:
        remaining = re.sub(pattern, "", remaining, flags=re.IGNORECASE).strip()

    # 3 — ...done thinking. marker
    if not extracted:
        remaining, done_thinking = _extract_done_thinking(remaining)
        if done_thinking:
            extracted = done_thinking

    # 4 — Bullet-point thinking
    if not extracted:
        remaining, bullet_thinking = _extract_bullet_thinking(remaining)
        if bullet_thinking:
            extracted = bullet_thinking

    # 5 — English thinking process
    if not extracted:
        remaining, english_thinking = _extract_english_thinking(remaining)
        if english_thinking:
            extracted = english_thinking

    # 6 — Generic XML tag cleanup
    remaining = re.sub(r"</?[a-zA-Z_][a-zA-Z0-9_]*>", "", remaining).strip()

    # 7 — Excessive blank lines
    remaining = re.sub(r"\n{3,}", "\n\n", remaining)
    remaining = re.sub(r"(\n\s*){3,}", "\n\n", remaining)

    return remaining, extracted


# ---------------------------------------------------------------------------
# JSON extractor
# ---------------------------------------------------------------------------

def _extract_json_from_response(content: str):
    """Robust JSON extractor with balanced brace matching.

    Accepts JSON objects that contain ``"response"`` plus at least one of:
    ``"actions"``, ``"tasks"``, ``"done"``, ``"summary"``, ``"thinking"``.

    Returns:
        A match-like object with ``.group(0)`` returning the JSON string,
        or ``None`` if no valid JSON is found.
    """
    if not content or not isinstance(content, str):
        return None

    valid_pair_keys = ('"actions"', '"tasks"', '"done"', '"summary"', '"thinking"')

    idx = content.find("{")
    while idx >= 0:
        depth = 0
        for i in range(idx, len(content)):
            ch = content[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = content[idx : i + 1]
                    is_coordinator = '"micro_objectives"' in candidate or '"new_objectives"' in candidate
                    is_agent_action = '"response"' in candidate and any(k in candidate for k in valid_pair_keys)
                    if is_coordinator or is_agent_action:
                        try:
                            json.loads(candidate)

                            class _FakeMatch:
                                def group(self, n=0):
                                    return candidate

                            return _FakeMatch()
                        except json.JSONDecodeError:
                            pass
                    break
            elif ch in ('"', "'"):
                quote, j = ch, i + 1
                while j < len(content) and content[j] != quote:
                    if content[j] == "\\":
                        j += 1
                    j += 1
                i = j  # noqa: F841 — loop var reassignment intentional
        idx = content.find("{", idx + 1)

    # Fallback: regex
    return re.search(
        r"\{[\s\S]*\"response\"[\s\S]*(\"actions\"|\"tasks\"|\"done\"|\"summary\"|\"thinking\")[\s\S]*\}",
        content,
    )


# ---------------------------------------------------------------------------
# Text formatter
# ---------------------------------------------------------------------------

def _format_response(text: str) -> str:
    """Ensure consistent formatting on model responses.

    - Line breaks after sentence-ending punctuation.
    - Stars/dashes on their own lines.
    - Numbered list items on their own lines.
    - Long lines broken at sentence boundaries.
    - At most one consecutive blank line.
    """
    if not text or not isinstance(text, str):
        return text

    text = re.sub(r"(?<=[.!?])\s+(?=[A-Z\*\(\[\d\"'])", r"\n", text)
    text = re.sub(r"(?<!\n)\s*\*\s+", r"\n* ", text)
    text = re.sub(r"(?<!\n)\s*(\d+\.\s+)", r"\n\1", text)
    text = re.sub(r"(?<!\n)\s*-\s+", r"\n- ", text)

    lines, new_lines = text.split("\n"), []
    for line in lines:
        if len(line) > 120:
            parts = re.split(r"(?<=[.!?])\s+", line)
            new_lines.extend(parts if len(parts) > 1 else [line])
        else:
            new_lines.append(line)
    text = "\n".join(new_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
