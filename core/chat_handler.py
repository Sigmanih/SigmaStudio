"""Chat handler for Sigma Studio — AI conversation, streaming, actions, web search."""
import os
import json
import re
import datetime
from core.ai_providers import load_ai_config, resolve_provider_config, call_ollama, call_ollama_stream, call_openai_compatible, call_openai_compatible_stream, call_anthropic
from core.task_handler import execute_ai_actions
from core.agent_memory import get_memory_context, save_session_memory, save_decision_memory, load_memory
from core.agent_registry import increment_usage, get_agent
from core.ai_providers import detect_execution_profile, apply_execution_profile

_TAG_PATTERNS = {
    'thinking': [
        r'<thinking>(.*?)</thinking>',
        r'<Thought>(.*?)</Thought>',
        r'<reasoning>(.*?)</reasoning>',
        r'<Rationale>(.*?)</Rationale>',
        r'<scratchpad>(.*?)</scratchpad>',
    ],
    'container': [
        r'</?response>',
        r'</?Response>',
        r'</?output>',
        r'</?Output>',
        r'</?answer>',
        r'</?Answer>',
        r'</?result>',
        r'</?Result>',
        r'</?tool_call>',
        r'</?ToolCall>',
        r'</?function_call>',
        r'</?FunctionCall>',
    ],
}


def _extract_english_thinking(content):
    """Detect and extract English thinking process text from model responses.
    
    Some models (especially Gemma-based, some fine-tunes) produce inline 
    English self-analysis like:
      "Here's a thinking process that leads to the suggested response:
       1. Analyze the Request: ...
       2. Check Contextual Information: ...
       ...
       (final response in Italian)"
    
    This function detects such patterns and splits them into thinking + response.
    """
    if not content or not isinstance(content, str):
        return content, None
    
    # Detection patterns for thinking process in English
    # These patterns mark the START of a self-analysis section
    thinking_starters = [
        r'^Here\'?s\s+a\s+thinking\s+process\b',
        r'^Here\s+is\s+the\s+thinking\s+process\b',
        r'^Thinking\s+Process:',
        r'^Let\s+me\s+think\s+(?:about|through|step\s+by\s+step)',
        r'^I\'?ll\s+approach\s+this\s+',
        r'^Let\s+me\s+analyze\s+',
    ]
    
    for starter in thinking_starters:
        if re.search(starter, content.strip(), re.IGNORECASE):
            # We found a thinking process in English
            # Strategy: find the end of thinking section by looking for the 
            # actual response start (text in Italian, the answer to the user)
            # Common patterns: the thinking ends before the actual answer
            
            lines = content.strip().split('\n')
            thinking_lines = []
            response_lines = []
            
            in_thinking = True
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    if in_thinking:
                        thinking_lines.append(line)
                    else:
                        response_lines.append(line)
                    continue
                
                if in_thinking:
                    # Check if this line signals the end of thinking
                    # The actual answer doesn't start with numbering, bullet points,
                    # meta-analysis phrases, or english self-reflection
                    
                    # Signals that thinking is over:
                    is_end_signal = (
                        stripped.startswith('Oggi è') or
                        stripped.startswith('Il link') or
                        stripped.startswith('[SYSTEM') or
                        stripped.startswith('[ANALISI') or
                        stripped.startswith('[SOURCE') or
                        (stripped.startswith('**') and '**' in stripped[2:]) or
                        # Italian text that's answering the user (not analyzing)
                        re.match(r'^[A-ZÀÈÉÌÒÙ][a-zàèéìòù]', stripped) and
                        not re.match(r'^(Here|Let|Think|Analyze|Check|Determine|Formulate|Refine|Self|I\'?ll|I will|Consider|Evaluate|Identify|Note|Observe|Plan|Prepare|Step|The\s+(user|request|query|answer))', stripped, re.IGNORECASE)
                    )
                    
                    if is_end_signal and not re.match(r'^\d+\.\s', stripped):
                        in_thinking = False
                        response_lines.append(line)
                    else:
                        thinking_lines.append(line)
                else:
                    response_lines.append(line)
            
            thinking_text = '\n'.join(thinking_lines).strip()
            response_text = '\n'.join(response_lines).strip()
            
            if thinking_text and response_text and len(thinking_text) > len(response_text) * 0.3:
                # Significant thinking found — extract it
                return response_text, thinking_text
    
    return content, None


def _extract_bullet_thinking(content):
    if not content or not isinstance(content, str):
        return content, None
    
    # Universal detection: count asterisk-prefixed phrases
    # This works for both inline and multi-line formats
    star_count = content.count('* ')
    has_thinking_keywords = bool(re.search(r'\*\s+(User|Role|Context|System|Option|Creator|Specialization|Tone|Step)', content, re.IGNORECASE))
    
    if star_count >= 2 and has_thinking_keywords:
        # Find transition from thinking to response
        # Strategy: locate the last "*. " or "*:" phrase, everything after is response
        parts = re.split(r'\*\s+\w+[\w\s,:]*\.\s*(?=[A-Z\(\[\*\"])', content)
        if len(parts) >= 2:
            # parts[0] = thinking, parts[1:] = response fragments
            # Take everything except the first thinking part
            thinking_text = parts[0].strip()
            response_text = ''
            # The response starts at the first Italian greeting or non-asterisk text
            response_match = re.search(r'(?:(?:Sono|Buongiorno|Salve|Ciao|Ecco|Benvenuto|Il mio|Posso)[^.!?]*[.!?])', content[len(thinking_text):])
            if response_match:
                response_start = len(thinking_text) + response_match.start()
                thinking_text = content[:response_start].strip()
                response_text = content[response_start:].strip()
            elif len(parts) > 1:
                response_text = ''.join(parts[1:]).strip()
            
            if thinking_text and response_text and len(thinking_text) > 30 and len(thinking_text) > len(response_text) * 0.2:
                return response_text, thinking_text
        
        # Fallback: take everything after last "* " sequence
        last_star = content.rfind('* ')
        if last_star > 0:
            # Find end of sentence containing that last star
            after = content[last_star:]
            sentence_end = max(after.find('. '), after.find('). '))
            if sentence_end > 0:
                split = last_star + sentence_end + 2
            else:
                split = last_star + len(after)
            if split < len(content) and split > len(content) * 0.3:
                thinking_text = content[:split].strip()
                response_text = content[split:].strip()
                if thinking_text and response_text and len(thinking_text) > 30:
                    return response_text, thinking_text
    
    lines = content.strip().split(chr(10))
    if len(lines) < 3:
        return content, None
    bullet_count = 0
    for line in lines[:30]:
        s = line.strip()
        if (s.startswith('* ') or s.startswith('- ') or
            (s and len(s) > 3 and s.lstrip()[0].isdigit() and '. ' in s[:5]) or
            s.startswith('Option ') or s.startswith('Step ') or
            s.startswith('Self-') or
            ':' in s[:20]):
            bullet_count += 1
    has_thinking_starter = any(re.search(p, content, re.IGNORECASE) for p in [
        r'^\*\s+User\s+says', r'^\*\s+Context',
        r'^\*\s+System', r'^\*\s+Role', r'^\*\s+Option',
        r'^Here\s+is\s+a\s+thinking', r'^Let\s+me\s+think',
        r'^Thinking\s+Process'])
    if has_thinking_starter or bullet_count >= max(3, len(lines[:20]) // 3):
        th, resp = [], []
        in_th = True
        for line in lines:
            s = line.strip()
            if in_th:
                is_th = (s.startswith('* ') or s.startswith('- ') or
                    (s and s[0].isdigit() and '. ' in s[:4]) or
                    s == '' or
                    s.lower().startswith(('option ', 'step ', 'self-', 'i ', 'my ', 'we ',
                        'the ', 'this ', 'it ', 'note:', 'in ', 'for ', 'keep ', 'make ',
                        'a ', 'an ', 'be ', 'to ', 'is ', 'are ', 'was ', 'were ',
                        'has ', 'have ', 'had ', 'can ', 'will ', 'may ', 'should ',
                        'but ', 'so ', 'if ', 'then ', 'else ', 'when ', 'where ', 'how ')))
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


def _format_response(text):
    """Force proper formatting on model responses: line breaks after sentences,
    bullet points on new lines, numbered lists on new lines.
    This ensures even poorly formatted model outputs become readable."""
    if not text or not isinstance(text, str):
        return text
    
    # 1. Ensure newline after each sentence ending
    # Split on ". " followed by uppercase letter or asterisk, add newlines
    text = re.sub(r'(?<=[.!?])\s+(?=[A-Z\*\(\[\d\"\'])', r'\n', text)
    
    # 2. Ensure stars are on their own line
    text = re.sub(r'(?<!\n)\s*\*\s+', r'\n* ', text)
    
    # 3. Ensure numbered items (1., 2., etc.) are on their own line
    text = re.sub(r'(?<!\n)\s*(\d+\.\s+)', r'\n\1', text)
    
    # 4. Ensure dashed items are on their own line
    text = re.sub(r'(?<!\n)\s*-\s+', r'\n- ', text)
    
    # 5. Break long lines (>120 chars) at word boundaries
    lines = text.split('\n')
    new_lines = []
    for line in lines:
        if len(line) > 120:
            # Find break points at ". " within the line
            parts = re.split(r'(?<=[.!?])\s+', line)
            if len(parts) > 1:
                new_lines.extend(parts)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    text = '\n'.join(new_lines)
    
    # 6. Clean up excessive blank lines (max 1)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def _extract_done_thinking(content):
    """Extract thinking from Ollama models that use '...done thinking.' delimiter.
    
    Some models (like Gemma via Ollama) output:
      Thinking... [reasoning] ...done thinking. [response]
    This function splits at the '...done thinking.' marker."""
    if not content or not isinstance(content, str):
        return content, None
    
    marker = '...done thinking.'
    idx = content.find(marker)
    if idx > 0:
        thinking = content[:idx].strip()
        response = content[idx + len(marker):].strip()
        # Remove "Thinking..." prefix from thinking if present
        if thinking.lower().startswith('thinking'):
            thinking = thinking[9:].strip()
        if thinking and response and len(thinking) > 20:
            return response, thinking
    
    # Also check for "Thinking..." without the done marker
    lower = content.lower()
    if lower.startswith('thinking...') or lower.startswith('thinking...'):
        # Find where thinking ends - typically before the actual response
        # Look for patterns like ". " followed by a greeting or response
        idx = 10  # Skip "Thinking..."
        rest = content[idx:]
        # The thinking usually ends before a greeting in Italian
        greetings = ['Ciao', 'Buongiorno', 'Salve', 'Ecco', 'Sono', 'Il mio']
        for greeting in greetings:
            g_idx = rest.find(greeting)
            if g_idx > 20:
                thinking = rest[:g_idx].strip()
                response = rest[g_idx:].strip()
                if thinking and response and len(thinking) > 20:
                    return response, thinking
    
    return content, None


def _clean_all_tags(content):
    """Universally remove all container tags and English thinking processes.
    
    Multi-stage cleaning:
    1. Extract thinking from XML-like tags (<thinking>, <Thought>, etc.)
    2. Remove all container tags (thinking, response, output, etc.)
    3. Extract English thinking process text (Gemma, fine-tuned models)
    4. Generic XML tag cleanup
    5. Clean up excessive blank lines
    """
    if not content or not isinstance(content, str):
        return content, None
    
    extracted = None
    remaining = content
    
    # Phase 1: Extract thinking from thinking-like tags
    for pattern in _TAG_PATTERNS['thinking']:
        match = re.search(pattern, remaining, re.DOTALL | re.IGNORECASE)
        if match:
            extracted = match.group(1).strip()
            remaining = re.sub(pattern, '', remaining, flags=re.DOTALL | re.IGNORECASE).strip()
            break
    
    # Phase 2: Remove all container tags (open and close)
    for pattern in _TAG_PATTERNS['container']:
        remaining = re.sub(pattern, '', remaining, flags=re.IGNORECASE).strip()
    
    # Phase 3: Extract thinking using "...done thinking." marker (Ollama Gemma)
    if not extracted:
        remaining, done_thinking = _extract_done_thinking(remaining)
        if done_thinking:
            extracted = done_thinking
    
    # Phase 4: Extract bullet-point thinking (Ollama inline)
    if not extracted:
        remaining, bullet_thinking = _extract_bullet_thinking(remaining)
        if bullet_thinking:
            extracted = bullet_thinking
    
    # Phase 4: Extract English thinking process (Gemma/other models)
    # But only if we haven't already found native thinking
    if not extracted:
        remaining, english_thinking = _extract_english_thinking(remaining)
        if english_thinking:
            extracted = english_thinking
    
    # Phase 5: Remove any remaining XML-ish tags (generic catch-all for odd cases)
    remaining = re.sub(r'</?[a-zA-Z_][a-zA-Z0-9_]*>', '', remaining).strip()
    
    # Phase 6: Clean up excessive blank lines from removals
    remaining = re.sub(r'\n{3,}', '\n\n', remaining)
    remaining = re.sub(r'(\n\s*){3,}', '\n\n', remaining)
    
    return remaining, extracted


def _extract_json_from_response(content):
    """Robust JSON extractor with balanced brace matcher.
    
    Accepts JSON objects containing:
    - "response" + "actions" (execution mode)
    - "response" + "tasks" (planning mode)
    - "response" + "done" (completion signal, e.g. {"done": true, "response": "..."})
    - "response" + "summary" (completion with summary)
    """
    if not content or not isinstance(content, str):
        return None
    
    # Accepted keys that indicate a valid operational JSON
    # "thinking" is valid for Ask mode responses
    valid_pair_keys = ['"actions"', '"tasks"', '"done"', '"summary"', '"thinking"']
    
    idx = content.find('{')
    while idx >= 0:
        depth = 0
        start = idx
        for i in range(idx, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    candidate = content[start:i+1]
                    if '"response"' in candidate and any(k in candidate for k in valid_pair_keys):
                        try:
                            json.loads(candidate)
                            class FakeMatch:
                                def group(self, n=0):
                                    return candidate
                            return FakeMatch()
                        except json.JSONDecodeError:
                            pass
                    break
            elif content[i] in ('"', "'"):
                quote = content[i]
                j = i + 1
                while j < len(content) and content[j] != quote:
                    if content[j] == '\\':
                        j += 1
                    j += 1
                i = j
        idx = content.find('{', idx + 1)
    return re.search(r'\{[\s\S]*"response"[\s\S]*("actions"|"tasks"|"done"|"summary"|"thinking")[\s\S]*\}', content)

def _scrape_url(url):
    try:
        import requests as req
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "it-IT,it;q=0.9",
        }
        resp = req.get(url, headers=headers, timeout=10, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(resp.text, 'lxml')
        title = soup.title.get_text(strip=True) if soup.title else ""
        desc = ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            desc = meta_desc['content']
        texts = []
        for tag in soup.find_all(['h1', 'h2', 'h3', 'p']):
            text = tag.get_text(strip=True)
            if len(text) > 30:
                texts.append(text)
            if len('\n'.join(texts)) > 2000:
                break
        c = f"Titolo pagina: {title}\n"
        if desc: c += f"Descrizione: {desc}\n"
        c += f"Contenuto:\n" + '\n'.join(texts[:15])
        return {"title": title or url.split("/")[-1], "body": c[:2000], "href": url}
    except Exception as e:
        return {"title": url, "body": f"Impossibile accedere a {url}: {str(e)}", "href": url}


def _search_duckduckgo(query):
    try:
        import requests as req
        from bs4 import BeautifulSoup
        session = req.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "it-IT,it;q=0.9",
        })
        try: session.get("https://duckduckgo.com/", timeout=10)
        except: pass
        resp = session.get("https://html.duckduckgo.com/html/", params={"q": query}, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')
        results = []
        for result in soup.select('.result')[:5]:
            title_el = result.select_one('.result__title a, .result__a')
            snippet_el = result.select_one('.result__snippet')
            link_el = result.select_one('a.result__url')
            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            href = link_el.get('href', '') if link_el else ""
            if title: results.append({"title": title[:150], "body": snippet[:300], "href": href})
        return results
    except: return []


def _perform_web_search(query):
    url_match = re.search(r'(https?://[^\s]+)', query)
    if url_match:
        url = url_match.group(1).rstrip('.,;:!?')
        result = _scrape_url(url)
        if result and "Impossibile accedere" not in result.get("body", ""):
            return [result]
    domains_map = {
        'corriere': 'https://www.corriere.it/', 'repubblica': 'https://www.repubblica.it/',
        'ansa': 'https://www.ansa.it/', 'gazzetta': 'https://www.gazzetta.it/',
        'il sole': 'https://www.ilsole24ore.com/', 'wikipedia': 'https://it.wikipedia.org/',
        'github': 'https://github.com/', 'youtube': None,
    }
    for keyword, domain_url in domains_map.items():
        if domain_url and keyword in query.lower():
            result = _scrape_url(domain_url)
            if result and "Impossibile accedere" not in result.get("body", ""):
                return [result]
    ddg = _search_duckduckgo(query)
    if ddg: return ddg
    try:
        import requests as req
        import urllib.parse
        r = req.get("https://it.wikipedia.org/w/api.php",
            params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": 5},
            headers={"User-Agent": "SigmaStudio/7.0"}, timeout=10)
        results = []
        for p in r.json().get("query", {}).get("search", [])[:5]:
            t = p.get("title", "")
            s = re.sub(r'<[^>]+>', '', p.get("snippet", ""))
            url = f"https://it.wikipedia.org/wiki/{urllib.parse.quote(t.replace(' ', '_'))}"
            results.append({"title": f"Wikipedia: {t}", "body": s[:300], "href": url})
        if results: return results
    except: pass
    return [{"title": "Nessun risultato", "body": f"Nessun risultato per: {query}", "href": ""}]


def _get_time_context():
    from datetime import datetime
    now = datetime.now()
    giorni = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    mesi = ["Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"]
    return f"## 📅 Oggi è {giorni[now.weekday()]} {now.day} {mesi[now.month-1]} {now.year}, ore {now.strftime('%H:%M')}.\n"


def _get_manifesto_content(manifesto_path):
    try:
        if manifesto_path and os.path.exists(manifesto_path):
            with open(manifesto_path, 'r', encoding='utf-8') as f:
                return f.read()
    except: pass
    return ""


def _build_filesystem_context():
    lines = []
    data_dir = 'data'
    if os.path.isdir(data_dir):
        for topic in sorted(os.listdir(data_dir)):
            topic_path = os.path.join(data_dir, topic)
            if not os.path.isdir(topic_path): continue
            lines.append(f"\n📂 {topic}/")
            for mod in sorted(os.listdir(topic_path)):
                mod_path = os.path.join(topic_path, mod)
                if not os.path.isdir(mod_path): continue
                mod_label = mod[3:] if mod[:2].isdigit() and len(mod) > 3 else mod
                lines.append(f"  📁 {mod} ({mod_label})")
                for section in ['teoria', 'test', 'viz', 'docs']:
                    sec_path = os.path.join(mod_path, section)
                    if os.path.isdir(sec_path):
                        files = sorted(os.listdir(sec_path))
                        if files:
                            lines.append(f"    {section}/")
                            for f in files:
                                fpath = os.path.join(sec_path, f).replace('\\', '/')
                                lines.append(f"      {f}  → {fpath}")
    return '\n'.join(lines) if lines else ""


def _collect_context_files(self, open_files):
    context_str = ""
    if not open_files: return context_str
    for file_path in open_files[:5]:
        if self._is_path_allowed(file_path) and os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                context_str += f"\n--- FILE: {file_path} ---\n{content[:5000]}\n"
            except: pass
    return context_str


def _resolve_manifesto_for_model(model_name):
    base_name = model_name.replace(':latest', '').replace(':', '_')
    for candidate in [f"manifesti/{model_name}.md", f"manifesti/{base_name}.md",
                      f"manifesti/{model_name.split(':')[0]}.md"]:
        candidate = candidate.replace(':', '_')
        if os.path.exists(candidate): return candidate
    manifesti_dir = 'manifesti'
    if os.path.isdir(manifesti_dir):
        for f in sorted(os.listdir(manifesti_dir)):
            if f.endswith('.md'):
                fname = f[:-3].lower()
                mname = model_name.lower()
                if fname in mname or mname.startswith(fname):
                    return os.path.join(manifesti_dir, f)
    return ""


def handle_chat(self):
    """POST /api/chat — Send message to AI agent and execute actions."""
    try:
        req = self.read_json_body()
        message = req.get("message", "").strip()
        if not message:
            return self.send_json_response({"error": "Messaggio vuoto"}, 400)

        bot_name = req.get("bot_name", "SigmaBot")
        manifesto_path = req.get("manifesto_path", "")
        model_override = req.get("model", "")
        allow_actions = req.get("allow_actions", True)
        planning_mode = req.get("planning_mode", False)
        execute_task_id = req.get("execute_task_id", "")
        context_files = req.get("context", {}).get("open_files", [])
        history = req.get("context", {}).get("history", [])
        uploaded_files = req.get("uploaded_files", [])

        if not manifesto_path or manifesto_path == "MANIFESTO.md":
            manifesto_path = _resolve_manifesto_for_model(model_override or req.get("model", ""))
        if not manifesto_path:
            manifesto_path = "MANIFESTO.md"

        ai_cfg = load_ai_config()
        model = model_override or ai_cfg.get("model", "llama3.2")
        provider = ai_cfg.get("active_provider", "ollama")
        providers_config = ai_cfg.get("providers", {})
        active_prov_cfg = providers_config.get(provider, {})
        endpoint = active_prov_cfg.get("endpoint", "http://localhost:11434/api/chat")
        api_url = active_prov_cfg.get("api_url", "")
        api_key = active_prov_cfg.get("api_key", "")
        temperature = active_prov_cfg.get("temperature", 0.7)
        max_tokens = active_prov_cfg.get("max_tokens", 4096)
        top_p = active_prov_cfg.get("top_p", 0.9)
        request_timeout = active_prov_cfg.get("timeout", 300)

        model_provider = req.get("model_provider", "")
        model_endpoint = req.get("model_endpoint", "")
        model_api_url = req.get("model_api_url", "")
        model_api_key = req.get("model_api_key", "")

        if model_provider:
            provider = model_provider
            if model_endpoint: endpoint = model_endpoint
            if model_api_url: api_url = model_api_url
            if model_api_key: api_key = model_api_key
            pv = providers_config.get(provider, {})
            if pv:
                temperature = pv.get("temperature", temperature)
                max_tokens = pv.get("max_tokens", max_tokens)
                top_p = pv.get("top_p", top_p)
        else:
            detected_provider, detected_prov = resolve_provider_config(ai_cfg, model)
            if detected_prov:
                provider = detected_provider
                if detected_prov.get("endpoint"): endpoint = detected_prov["endpoint"]
                if detected_prov.get("api_url"): api_url = detected_prov["api_url"]
                if detected_prov.get("api_key"): api_key = detected_prov["api_key"]
                temperature = detected_prov.get("temperature", temperature)
                max_tokens = detected_prov.get("max_tokens", max_tokens)
                top_p = detected_prov.get("top_p", top_p)
                request_timeout = detected_prov.get("timeout", request_timeout)

        frontend_timeout = req.get("timeout", 0)
        if frontend_timeout and frontend_timeout > 0:
            request_timeout = int(frontend_timeout)

        system_prompt = _get_manifesto_content(manifesto_path)
        if not system_prompt.strip():
            system_prompt = """Sei Sigma AI Studio, un assistente AI integrato in Sigma Studio.
Rispondi in italiano in modo chiaro, diretto e strutturato.
## FORMATO RISPOSTA
In modalità CHIEDI rispondi SEMPRE con JSON: {"response": "La risposta all'utente...", "thinking": "Il tuo ragionamento passo-passo..."}
- "response": solo la risposta finale, ben formattata
- "thinking": il processo logico separato (verrà mostrato con toggle "Mostra ragionamento")
MAI mischiare thinking e response. MAI usare tag XML."""

        # --- BUILD SYSTEM PROMPT ---
        if allow_actions or planning_mode:
            action_prompt = """
## 🛑 REGOLA PIÙ IMPORTANTE — FORMATO JSON OBBLIGATORIO + STRUTTURA MODULARE

SEI IN MODALITÀ AZIONI. DEVI RISPONDERE SOLO CON UN OGGETTO JSON VALIDO.
NON usare <thinking> o <response>. SOLO JSON puro.

### STRUTTURA MODULARE OBBLIGATORIA — REGOLA WHITELIST
Le cartelle dentro i moduli sono SOLO 5, NESSUNA ALTRA:

  ✅ teoria/  ✅ test/  ✅ viz/  ✅ docs/  ✅ whitepapers/

   ❌ QUALSIASI altra cartella è automaticamente VIETATA

Struttura corretta:
  data/<argomento>/<NN_sottoargomento>/<sezione>/<file>

#### FILE VIETATI direttamente nella root del modulo (NON CREARLI MAI):
  data/argomento/NN_sottoargomento/file.py  ❌
  data/argomento/NN_sottoargomento/report.md ❌

#### FILE VIETATI direttamente nella root del topic (NON CREARLI MAI):
  data/argomento/report.md ❌

#### ESEMPI CORRETTI:
  data/esempio/01_modulo/teoria/analisi.md ✅
  data/esempio/01_modulo/test/verifica.py ✅
  data/esempio/01_modulo/viz/grafico.html ✅

### AZIONI
1. create_module: crea modulo con sottocartelle. "topic", "number", "name"
2. create_file: crea file DENTRO un modulo. "path", "content"
3. edit_file, rename_file, delete_file, update_task

### FLUSSO: create_module PRIMA, poi create_file dentro il modulo.

### REGOLE PER MODIFICA CODICE (HTML/CSS/JS/PYTHON)
- Temperatura consigliata: 0.3 (bassa, per preservare struttura e logica esistente)
- MAI rimuovere: DOCTYPE, <html>, <head>, <title>, <body> da file HTML
- MAI rompere la struttura DOM: preserva <table>, <colgroup>, <thead>, <tbody> se presenti
- Quando modifichi HTML: altera SOLO ciò che serve, NON ricostruire da zero
- Dopo ogni modifica a codice, verifica mentalmente che il file sia valido e funzionante
- Per file HTML: assicurati che tutti i tag siano chiusi e la struttura sia valida

ESEMPIO:
{"response": "Creo modulo e file", "actions": [
  {"type": "create_module", "topic": "Marketing", "number": "01", "name": "Fondamenti"},
  {"type": "create_file", "path": "data/marketing/01_fondamenti/teoria/intro.md", "content": "# Intro\\n\\n..."}
]}
"""
            full_system = f"{system_prompt}\n\n{action_prompt}"
        else:
            full_system = system_prompt  # Nessun formato richiesto per risposte normali

        context_str = _collect_context_files(self, context_files)
        tasks_context = ""
        if os.path.exists('tasks.json'):
            try:
                with open('tasks.json', 'r', encoding='utf-8') as f:
                    all_tasks = json.load(f)
                tasks_context = json.dumps(all_tasks, indent=2)
            except: tasks_context = "[]"
        topics_context = _build_filesystem_context()
        time_ctx = _get_time_context()

        system_parts = [full_system, time_ctx]
        if context_str: system_parts.append(f"File aperti:\n{context_str}")
        if uploaded_files:
            us = ""
            for uf in uploaded_files[:10]:
                fn = uf.get("filename", "sconosciuto")
                ct = uf.get("content", "")
                us += f"\n--- FILE CARICATO: {fn} ---\n{ct[:8000]}\n"
            system_parts.append(f"File caricati dal PC:\n{us}")
        if topics_context: system_parts.append(f"Struttura:\n{topics_context}")
        if tasks_context: system_parts.append(f"Tasks:\n{tasks_context}")

        # --- Inject agent memory context ---
        # Determine agent ID from model name or manifesto
        agent_id = None
        model_lower = model.lower()
        for candidate_id in ['agente0', 'math1', 'code_architect']:
            if candidate_id in model_lower:
                agent_id = candidate_id
                break
        if not agent_id and manifesto_path:
            for candidate_id in ['agente0', 'math1', 'code_architect']:
                if candidate_id in manifesto_path.lower():
                    agent_id = candidate_id
                    break
        
        # If we found the agent, inject memory context
        memory_context = ""
        if agent_id:
            memory_context = get_memory_context(agent_id)
            if memory_context:
                system_parts.append(memory_context)
        
        messages = [{"role": "system", "content": "\n\n".join(system_parts)}]
        for h in history[-10:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

        user_prompt = message
        if allow_actions:
            user_prompt += "\n\nRemember to respond with a JSON object containing 'response' and 'actions' fields."
        if planning_mode:
            user_prompt += """
## MODALITÀ PIANIFICAZIONE — REGOLE OBBLIGATORIE
Rispondi con JSON: {"response": "...", "tasks": [...]}

IMPORTANTE — STRUTTURA MINIMA DI OGNI TASK:
- "titolo": DESCRITTIVO e specifico. MAI "Nuovo task". Esempio: "Dimostrare Lemma di Saturazione" o "Analizzare distribuzione Mod 24"
- "descrizione": ALMENO una frase che spiega cosa fare e perché. MAI vuota.
- "moduli": array di stringhe con i numeri dei moduli coinvolti. Es: ["01", "02"]. Se non specifico per un modulo, usa [].
- "priorita": una tra "critica", "alta", "media", "bassa". Spiega brevemente perché in descrizione.
"""
        if execute_task_id:
            task_detail = ""
            if os.path.exists('tasks.json'):
                try:
                    with open('tasks.json', 'r', encoding='utf-8') as f:
                        all_tasks = json.load(f)
                    task = next((t for t in all_tasks if t.get('id') == execute_task_id or t.get('titolo') == execute_task_id), None)
                    if task: task_detail = f"\n\nTask da eseguire: {task.get('titolo','')}\n{task.get('descrizione','')}"
                except: pass
            if task_detail: user_prompt += task_detail
        messages.append({"role": "user", "content": user_prompt})

        ai_response = ""
        ai_thinking = None
        error = None
        route_provider = provider
        if route_provider not in ('ollama', 'api', 'anthropic'):
            route_provider = 'api' if 'anthropic' not in api_url.lower() else 'anthropic'

        web_search = req.get("web_search", False)
        if web_search and not planning_mode:
            search_results = _perform_web_search(message)
            if search_results and not search_results[0].get("body", "").startswith("Nessun risultato"):
                st = "\n\n====================================================\n"
                st += "## 🌐 RICERCA WEB COMPLETATA\n"
                for i, r in enumerate(search_results[:5], 1):
                    st += f"\n{i}. **{r['title']}**\n   {r['body'][:300]}\n   {r['href']}\n"
                st += "====================================================\n"
                messages[0]["content"] += st

        stream_mode = req.get("stream", False)
        if stream_mode and not allow_actions and not planning_mode:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            def _sw(chunks):
                try:
                    for chunk in chunks:
                        if chunk is None: self.wfile.write(b"data: [ERROR]\n\n"); break
                        if chunk.get("error"): self.wfile.write(f"data: {json.dumps({'error': chunk['message']})}\n\n".encode()); self.wfile.flush(); break
                        if chunk.get("done"): self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush(); break
                        payload = {}
                        if "token" in chunk: payload["token"] = chunk["token"]
                        if "thinking" in chunk: payload["thinking"] = chunk["thinking"]
                        if payload: self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode()); self.wfile.flush()
                    else: self.wfile.write(b"data: [DONE]\n\n"); self.wfile.flush()
                except: self.wfile.write(b"data: [ERROR]\n\n"); self.wfile.flush()
            if route_provider == "ollama":
                num_ctx = active_prov_cfg.get("num_ctx", 8192)
                top_k = active_prov_cfg.get("top_k", 40)
                repeat_penalty = active_prov_cfg.get("repeat_penalty", 1.1)
                seed = active_prov_cfg.get("seed", 0)
                chunks = call_ollama_stream(messages, model, endpoint, temperature, max_tokens, top_p, top_k, repeat_penalty, num_ctx, seed, request_timeout)
                _sw(chunks); return
            elif route_provider == "api":
                chunks = call_openai_compatible_stream(messages, model, api_url, api_key, temperature, max_tokens, top_p, request_timeout)
                _sw(chunks); return

        if route_provider == "ollama":
            num_ctx = active_prov_cfg.get("num_ctx", 8192)
            top_k = active_prov_cfg.get("top_k", 40)
            repeat_penalty = active_prov_cfg.get("repeat_penalty", 1.1)
            seed = active_prov_cfg.get("seed", 0)
            ai_response, ai_thinking, error = call_ollama(messages, model, endpoint, temperature, max_tokens, top_p, top_k, repeat_penalty, num_ctx, seed, request_timeout)
        elif route_provider == "api":
            ai_response, ai_thinking, error = call_openai_compatible(messages, model, api_url, api_key, temperature, max_tokens, top_p, request_timeout)
        elif route_provider == "anthropic":
            ai_response, error = call_anthropic(messages, model, api_url, api_key, temperature, max_tokens, top_p)
        else:
            error = f"Provider sconosciuto: {provider}"

        if error:
            manifesto_name = os.path.basename(manifesto_path).replace('.md', '') if manifesto_path else ''
            return self.send_json_response({"response": f"⚠️ Errore IA ({provider}): {error}", "actions_log": [], "error": error, "manifesto_used": manifesto_name})

        actions_log = []
        clean_response = ai_response

        # Universally remove all container tags from the response
        # This handles models (Gemma, fine-tuned, etc.) that produce <thinking>, <response>, etc.
        # Native model thinking (DeepSeek) is already extracted by ai_providers.py
        clean_response, extracted_tags_thinking = _clean_all_tags(clean_response)
        
        # Use native thinking first, fallback to thinking extracted from tags
        thinking = ai_thinking or extracted_tags_thinking

        if allow_actions or planning_mode:
            print(f"\n[SIGMA_CHAT_DEBUG] allow_actions={allow_actions} planning_mode={planning_mode}", flush=True)
            print(f"[SIGMA_CHAT_DEBUG] AI response cleaned (first 2000 chars): {clean_response[:2000]}", flush=True)

        # SEMPRE prova a estrarre JSON con response/thinking, anche in modalità Chiedi
        # I modelli DeepSeek via API restituiscono thinking nativamente (ai_thinking)
        # Per Ollama, proviamo a parsare manualmente il formato {"response":..., "thinking":...}
        json_match = _extract_json_from_response(clean_response)
        if json_match and not allow_actions and not planning_mode:
            try:
                parsed = json.loads(json_match.group())
                resp_text = parsed.get("response", "")
                think_text = parsed.get("thinking", parsed.get("reasoning", ""))
                if resp_text:
                    clean_response = _format_response(resp_text)
                if think_text and not thinking:
                    thinking = think_text
            except:
                pass

        if json_match:
            try:
                parsed = json.loads(json_match.group())
                # In Ask mode, response has already been extracted above — skip overwrite
                if allow_actions or planning_mode:
                    clean_response = parsed.get("response", ai_response)
                    clean_response = _format_response(clean_response)
                json_thinking = parsed.get("thinking", parsed.get("reasoning", None))
                if json_thinking and not ai_thinking:
                    thinking = json_thinking
                actions = parsed.get("actions", []) if (allow_actions or planning_mode) else []
                if not allow_actions and not planning_mode:
                    print(f"[SIGMA_CHAT_DEBUG] Ask mode JSON: response='{clean_response[:80]}...', thinking={'yes' if thinking else 'no'}", flush=True)

                if planning_mode and "tasks" in parsed:
                    plan_tasks = parsed.get("tasks", [])
                    if plan_tasks:
                        tasks_list = []
                        if os.path.exists('tasks.json'):
                            try:
                                with open('tasks.json', 'r', encoding='utf-8') as f:
                                    tasks_list = json.load(f)
                            except: tasks_list = []
                        for t in plan_tasks:
                            titolo = t.get("titolo", "Nuovo task")
                            descrizione = t.get("descrizione", "")
                            priorita = t.get("priorita", "media")
                            moduli = t.get("moduli", [])
                            
                            # Validazione: se titolo e' generico, usa contesto per arricchirlo
                            if titolo.lower() in ("nuovo task", "task", "nuovo", "new task", ""):
                                titolo = f"Task: {message[:60]}"
                            if not descrizione or descrizione.strip() == "":
                                descrizione = f"Task pianificato dall'AI in risposta a: {message[:200]}"
                            if priorita not in ("critica", "alta", "media", "bassa"):
                                priorita = "media"
                            if not isinstance(moduli, list):
                                moduli = []
                            
                            tasks_list.append({
                                "titolo": titolo,
                                "descrizione": descrizione,
                                "status": "in_corso", "priorita": priorita,
                                "moduli": moduli,
                                "id": int(datetime.datetime.now().timestamp() * 1000) + len(tasks_list),
                                "notifiche": [{
                                    "da": bot_name,
                                    "messaggio": f"Task pianificato da {bot_name}",
                                    "timestamp": datetime.datetime.now().isoformat()
                                }]
                            })
                        with open('tasks.json', 'w', encoding='utf-8') as f:
                            json.dump(tasks_list, f, indent=4)
                        actions_log.append({"type": "plan_tasks", "success": True, "message": f"{len(plan_tasks)} task creati"})

                if allow_actions and actions:
                    print(f"[SIGMA_CHAT_DEBUG] Executing {len(actions)} actions...", flush=True)
                    actions_log = execute_ai_actions(self, actions, bot_name)
                    print(f"[SIGMA_CHAT_DEBUG] Actions result: {actions_log}", flush=True)
                    
                    # Save session memory for the agent
                    if agent_id:
                        success_count = sum(1 for a in actions_log if a.get("success"))
                        fail_count = sum(1 for a in actions_log if not a.get("success"))
                        try:
                            save_session_memory(agent_id, {
                                "goal": message[:200],
                                "actions_performed": actions_log,
                                "success_count": success_count,
                                "fail_count": fail_count,
                                "learning": "",
                                "summary": f"{success_count} azioni riuscite, {fail_count} fallite"
                            })
                            # Update agent usage stats
                            increment_usage(agent_id, success=fail_count == 0)
                        except Exception as mem_err:
                            print(f"[SIGMA_CHAT_DEBUG] Memory save error: {mem_err}", flush=True)
                    
                    # Auto-update task when execute_task_id is present
                    # Se siamo in modalità completa task, aggiorna automaticamente lo stato
                    if execute_task_id and actions_log:
                        try:
                            tasks_list = []
                            if os.path.exists('tasks.json'):
                                with open('tasks.json', 'r', encoding='utf-8') as f:
                                    tasks_list = json.load(f)
                            
                            task_found = None
                            for t in tasks_list:
                                if t.get('id') == execute_task_id or t.get('titolo') == execute_task_id:
                                    task_found = t
                                    break
                            
                            if task_found:
                                task_found["status"] = "done"
                                # Add notification for each successful action
                                for entry in actions_log:
                                    if entry.get("success") and entry.get("type") in ("create_file", "edit_file", "delete_file", "rename_file", "create_module", "run_test"):
                                        if "notifiche" not in task_found:
                                            task_found["notifiche"] = []
                                        task_found["notifiche"].append({
                                            "da": bot_name,
                                            "messaggio": f"[{entry['type']}] {entry.get('message', '')}",
                                            "timestamp": datetime.datetime.now().isoformat()
                                        })
                                # Add summary notification
                                success_count = sum(1 for e in actions_log if e.get("success"))
                                fail_count = sum(1 for e in actions_log if not e.get("success"))
                                summary = f"Task completato: {success_count} azioni riuscite"
                                if fail_count:
                                    summary += f", {fail_count} fallite"
                                if "notifiche" not in task_found:
                                    task_found["notifiche"] = []
                                task_found["notifiche"].append({
                                    "da": bot_name,
                                    "messaggio": summary,
                                    "timestamp": datetime.datetime.now().isoformat()
                                })
                                
                                with open('tasks.json', 'w', encoding='utf-8') as f:
                                    json.dump(tasks_list, f, indent=4)
                                
                                actions_log.append({
                                    "type": "complete_task",
                                    "success": True,
                                    "message": f"Task '{task_found.get('titolo', '')}' completato automaticamente"
                                })
                        except Exception as e:
                            print(f"[SIGMA_CHAT_DEBUG] Auto-update task error: {e}", flush=True)
            except json.JSONDecodeError as e:
                print(f"[SIGMA_CHAT_DEBUG] JSON decode ERROR: {e}", flush=True)
        elif allow_actions or planning_mode:
            print(f"[SIGMA_CHAT_DEBUG] No JSON match found in response!", flush=True)

        if allow_actions and not actions_log:
            diag = "\n\n---\n⚠️ **Diagnostica:** La risposta dell'AI non conteneva azioni JSON valide."
            diag += " Riprova riformulando la richiesta in modo più diretto."
            clean_response += diag

        # Include manifesto info in response
        manifesto_name = os.path.basename(manifesto_path).replace('.md', '') if manifesto_path else ''
        self.send_json_response({"response": clean_response, "thinking": thinking, "actions_log": actions_log, "error": None, "manifesto_used": manifesto_name})
    except Exception as e:
        self.send_json_response({"error": str(e)}, 500)