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
import logging

log = logging.getLogger("sigma.response_parser")

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
                        stripped.startswith("Oggi \u00e8")
                        or stripped.startswith("Il link")
                        or stripped.startswith("[SYSTEM")
                        or stripped.startswith("[ANALISI")
                        or stripped.startswith("[SOURCE")
                        or (stripped.startswith("**") and "**" in stripped[2:])
                        or (
                            re.match(r"^[A-Z\u00c0\u00c8\u00c9\u00cc\u00d2\u00d9][a-z\u00e0\u00e8\u00e9\u00ec\u00f2\u00f9]", stripped)
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


_ENGLISH_STOPWORDS = {"the", "of", "to", "and", "a", "in", "is", "it", "you", "that", "for", "on", "are", "with", "this", "have", "from", "be"}
_ITALIAN_STOPWORDS = {"il", "la", "di", "dei", "della", "del", "in", "con", "su", "per", "tra", "fra", "un", "una", "che", "si", "sono", "\u00e8", "ad", "al", "alla", "allo", "ai", "gli", "le", "lo"}

def _detect_language(text: str) -> str:
    """Return 'en' or 'it' or 'unknown' based on stopword frequency."""
    words = re.findall(r"\b[a-z\u00e0\u00e8\u00e9\u00ec\u00f2\u00f9\']+\b", text.lower())
    if not words:
        return "unknown"
    en_count = sum(1 for w in words if w in _ENGLISH_STOPWORDS)
    it_count = sum(1 for w in words if w in _ITALIAN_STOPWORDS)
    if en_count > it_count:
        return "en"
    elif it_count > en_count:
        return "it"
    return "unknown"


def _split_by_language_transition(content: str) -> tuple[str, str | None]:
    """Detect and split English thinking block from Italian response."""
    if not content or not isinstance(content, str):
        return content, None

    lines = content.split("\n")
    split_idx = -1
    consecutive_italian = 0

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        clean_line = re.sub(r"^[\s#\-\*\d\.\(\)]+", "", stripped).strip()
        if len(clean_line) < 15:
            continue

        lang = _detect_language(clean_line)
        if lang == "it":
            consecutive_italian += 1
            if split_idx == -1:
                split_idx = idx
            if consecutive_italian >= 2:
                break
        elif lang == "en":
            split_idx = -1
            consecutive_italian = 0

    if split_idx > 0:
        preceding = "\n".join(lines[:split_idx]).strip()
        following = "\n".join(lines[split_idx:]).strip()
        if len(preceding) > 30 and len(following) > 30:
            return following, preceding

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

def _extract_thinking_process(content: str) -> tuple[str, str | None]:
    """Detect 'Here's a thinking process:' / 'Here is the thinking process' block
    and extract everything before the JSON as thinking.
    
    This is the main pattern used by qwen/deepseek models — they output
    a long English analysis before the Italian response JSON.
    
    Strategy: Find the LAST occurrence of '{"response"' in the content.
    Everything before it is thinking, everything from it onward is the response JSON.
    """
    if not content or not isinstance(content, str):
        return content, None
    
    # Check if there's a thinking starter
    has_starter = False
    for starter in _THINKING_STARTERS:
        if re.search(starter, content.strip(), re.IGNORECASE):
            has_starter = True
            break
    
    if not has_starter:
        return content, None
    
    # Find the LAST occurrence of {"response"  — that's where the real JSON starts
    resp_pos = content.rfind('{"response"')
    if resp_pos < 0:
        # Try just the last {" that precedes a "response" somewhere after
        # Or try to find "response" and work backwards to the nearest {
        resp_keyword = content.rfind('"response"')
        if resp_keyword >= 0:
            # Find the { that opens this JSON by scanning backwards
            for p in range(resp_keyword, -1, -1):
                if content[p] == '{':
                    resp_pos = p
                    break
    
    if resp_pos > 50:  # Must have significant thinking text before
        thinking_text = content[:resp_pos].strip()
        response_text = content[resp_pos:].strip()
        if thinking_text and response_text and len(response_text) > 50:
            return response_text, thinking_text
    
    return content, None


def _clean_all_tags(content: str) -> tuple[str, str | None]:
    """Remove all container/thinking tags and extract thinking text.

    Multi-stage pipeline:
    0. Extract "Here's a thinking process:" block (most common for qwen models).
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

    # 0 — Extract "Here's a thinking process:" block first (most common issue)
    remaining, process_thinking = _extract_thinking_process(remaining)
    if process_thinking:
        extracted = process_thinking

    # 1 \u2014 Extract thinking from XML tags
    if not extracted:
        for pattern in _TAG_PATTERNS["thinking"]:
            match = re.search(pattern, remaining, re.DOTALL | re.IGNORECASE)
            if match:
                extracted = match.group(1).strip()
                remaining = re.sub(pattern, "", remaining, flags=re.DOTALL | re.IGNORECASE).strip()
                break

    # 2 \u2014 Remove container tags
    for pattern in _TAG_PATTERNS["container"]:
        remaining = re.sub(pattern, "", remaining, flags=re.IGNORECASE).strip()

    # 3 \u2014 ...done thinking. marker
    if not extracted:
        remaining, done_thinking = _extract_done_thinking(remaining)
        if done_thinking:
            extracted = done_thinking

    # 4 \u2014 Bullet-point thinking
    if not extracted:
        remaining, bullet_thinking = _extract_bullet_thinking(remaining)
        if bullet_thinking:
            extracted = bullet_thinking

    # 5 \u2014 English thinking process
    if not extracted:
        remaining, english_thinking = _extract_english_thinking(remaining)
        if english_thinking:
            extracted = english_thinking

    # 5.5 \u2014 Language transition splitting (English to Italian)
    if not extracted:
        remaining, transition_thinking = _split_by_language_transition(remaining)
        if transition_thinking:
            extracted = transition_thinking

    # 6 \u2014 Generic XML tag cleanup
    remaining = re.sub(r"</?[a-zA-Z_][a-zA-Z0-9_]*>", "", remaining).strip()

    # 7 \u2014 Excessive blank lines
    remaining = re.sub(r"\n{3,}", "\n\n", remaining)
    remaining = re.sub(r"(\n\s*){3,}", "\n\n", remaining)

    return remaining, extracted


# ---------------------------------------------------------------------------
# JSON repair helper — fixes malformed JSON from local Ollama models
# ---------------------------------------------------------------------------

def _repair_quotes_in_content_field(candidate: str) -> str:
    """Repair unescaped quotes inside the 'content' field value.
    
    The problem: the AI model outputs HTML like:
      "content": "<div class="test">..."
    
    The quotes around 'test' break the JSON. This function finds the
    content field value and escapes any unescaped internal quotes.
    
    Strategy: 
    1. Find "content":  pattern
    2. Capture until the REAL closing quote (before , or } or ])
    3. Inside, replace " with \"
    4. Preserve already-escaped \"
    """
    result = []
    i = 0
    
    while i < len(candidate):
        # Look for common patterns: "content": "
        if (candidate[i:i+1] == '"' and 
            candidate[i:i+9].lower() in ('"content', '"content')):
            
            # Check it's really "content" key (not "content_something")
            after_key = candidate[i+9:i+12]
            if after_key in ('"', '" ', '" ', '":'):
                # Found "content" key — copy it
                while i < len(candidate) and candidate[i] != ':':
                    result.append(candidate[i])
                    i += 1
                
                # Copy colon
                result.append(candidate[i])
                i += 1
                
                # Skip whitespace
                while i < len(candidate) and candidate[i] in ' \t\n\r':
                    result.append(candidate[i])
                    i += 1
                
                # Next must be opening quote
                if i < len(candidate) and candidate[i] == '"':
                    result.append('"')
                    i += 1
                    
                    # Now scan the content value
                    # Collect until we find a closing quote followed by , or } or ]
                    content_buffer = []
                    escaped = False
                    
                    while i < len(candidate):
                        c = candidate[i]
                        
                        if escaped:
                            content_buffer.append(c)
                            escaped = False
                        elif c == '\\':
                            content_buffer.append(c)
                            escaped = True
                        elif c == '"':
                            # Check if this is the real closing quote
                            # Look ahead past whitespace for , } ]
                            rest = candidate[i+1:].lstrip()
                            if rest and rest[0] in ',}]':
                                # Real closing quote — done
                                result.append(''.join(content_buffer))
                                result.append('"')
                                i += 1
                                break
                            else:
                                # Unescaped quote inside content — escape it
                                content_buffer.append('\\"')
                        elif c in '\n\r':
                            content_buffer.append('\\n' if c == '\n' else '\\r')
                        else:
                            content_buffer.append(c)
                        i += 1
                    
                    if i >= len(candidate):
                        # No closing quote found — use what we have
                        result.append(''.join(content_buffer))
                    continue
        
        result.append(candidate[i])
        i += 1
    
    return ''.join(result)


def _cleanup_json(candidate: str) -> str:
    """Clean common JSON formatting issues: trailing commas, braces."""
    # Remove trailing commas before } and ]
    candidate = re.sub(r',\s*}', '}', candidate)
    candidate = re.sub(r',\s*]', ']', candidate)
    
    # Balance braces
    open_c = candidate.count('{')
    close_c = candidate.count('}')
    if open_c > close_c:
        candidate += '}' * (open_c - close_c)
    
    return candidate


def _attempt_json_repair(text: str) -> str | None:
    """Try to repair common JSON issues from local AI model output.

    Local models (llama3.2, etc.) often produce JSON with:
    - Unescaped quotes inside string values (especially in 'content' fields with HTML)
    - Unescaped newlines/tabs inside strings
    - Trailing commas
    - Missing closing braces
    - Thinking text before the JSON block

    Returns repaired JSON string or None if repair fails.
    """
    if not text or not isinstance(text, str):
        return None

    # Step 0: Try direct parse first
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Step 1: Find the JSON block
    first_brace = text.find('{')
    if first_brace < 0:
        return None
    
    last_brace = -1
    depth = 0
    for i in range(first_brace, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                last_brace = i
                break
    
    candidate = text[first_brace:last_brace + 1] if last_brace >= 0 else text[first_brace:]
    
    # Step 2: Fix content field quotes (main issue with HTML)
    candidate = _repair_quotes_in_content_field(candidate)
    
    # Step 3: Cleanup
    candidate = _cleanup_json(candidate)
    
    # Step 4: Try parse
    try:
        json.loads(candidate)
        log.debug("JSON repair succeeded after content field quote repair")
        return candidate
    except json.JSONDecodeError as e:
        log.debug("JSON repair attempt 1 failed: %s", e)
    
    # Step 5: More aggressive — extract individual action blocks and rebuild
    try:
        resp_match = re.search(r'"response"\s*:\s*"([^"]*)"', candidate)
        if not resp_match:
            return None
        
        resp_val = resp_match.group(0)
        
        # Find action blocks
        action_blocks = []
        depth = 0
        start = -1
        for i, c in enumerate(candidate):
            if c == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0 and start >= 0:
                    blk = candidate[start:i+1]
                    if '"type"' in blk and '"content"' in blk:
                        blk = _repair_quotes_in_content_field(blk)
                        blk = _cleanup_json(blk)
                        action_blocks.append(blk)
                    start = -1
        
        if action_blocks:
            rebuilt = '{' + resp_val + ', "actions": [' + ','.join(action_blocks) + '], "done": true}'
            try:
                json.loads(rebuilt)
                log.debug("JSON repair succeeded via block rebuild (%d actions)", len(action_blocks))
                return rebuilt
            except json.JSONDecodeError:
                pass
    except Exception:
        pass
    
    return None


# ---------------------------------------------------------------------------
# JSON extractor
# ---------------------------------------------------------------------------

# Accepted keys that indicate a valid action/planning JSON
_VALID_CONTENT_KEYS = frozenset({
    '"actions"', '"action"', '"tasks"', '"done"', '"summary"', '"thinking"',
    '"reasoning"', '"command"', '"commands"', '"operations"', '"micro_objectives"',
    '"new_objectives"',
})


def _extract_json_from_response(content: str):
    """Robust JSON extractor with balanced brace matching and repair.

    Accepts JSON objects that contain ``"response"`` plus at least one of:
    ``"actions"``, ``"action"``, ``"tasks"``, ``"done"``, ``"summary"``,
    ``"thinking"``, ``"reasoning"``, ``"command"``, etc.

    If direct JSON loading fails, attempts automatic repair via
    :func:`_attempt_json_repair`.

    Returns:
        A match-like object with ``.group(0)`` returning the JSON string,
        or ``None`` if no valid JSON is found.
    """
    if not content or not isinstance(content, str):
        return None

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
                    # Check if this candidate has useful keys
                    has_response = '"response"' in candidate
                    has_action_keys = any(k in candidate for k in _VALID_CONTENT_KEYS)
                    if has_response and has_action_keys:
                        try:
                            json.loads(candidate)
                            class _FakeMatch:
                                def group(self, n=0):
                                    return candidate
                            return _FakeMatch()
                        except json.JSONDecodeError:
                            # Try repair
                            repaired = _attempt_json_repair(candidate)
                            if repaired:
                                class _RepairedMatch:
                                    def group(self, n=0):
                                        return repaired
                                return _RepairedMatch()
                    break
            elif ch in ('"', "'"):
                quote, j = ch, i + 1
                while j < len(content) and content[j] != quote:
                    if content[j] == "\\":
                        j += 1
                    j += 1
                i = j
        idx = content.find("{", idx + 1)

    # Fallback: regex
    regex_match = re.search(
        r"\{[\s\S]*\"response\"[\s\S]*(\"actions\"|\"action\"|\"tasks\"|\"done\"|\"summary\"|\"thinking\"|\"reasoning\"|\"command\")[\s\S]*\}",
        content,
    )
    if regex_match:
        candidate = regex_match.group(0)
        try:
            json.loads(candidate)
            return regex_match
        except json.JSONDecodeError:
            repaired = _attempt_json_repair(candidate)
            if repaired:
                class _RepairedMatch2:
                    def group(self, n=0):
                        return repaired
                return _RepairedMatch2()

    return None


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