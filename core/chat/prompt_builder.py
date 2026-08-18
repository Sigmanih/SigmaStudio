# ==============================================================================
# core/chat/prompt_builder.py — System Prompt & Context Builder
# Extracted from core/chat_handler.py for Single Responsibility
# ==============================================================================
"""Build system prompts, collect context files, and resolve manifesti.

Responsibilities:
    - Load manifesto (Modelfile) content for an agent.
    - Resolve which manifesto matches the active model.
    - Build the filesystem structure context string.
    - Collect open-file contents for AI context.
    - Provide current date/time context string.
"""

import os
import re
from collections import OrderedDict
from core.logger import get_logger

log = get_logger(__name__)

# --- Agent routing budget ----------------------------------------------------
# Routing picks one manifesto path. It is a classification, not a generation,
# and every millisecond it costs is latency before the user sees any answer.

# An agent id is a handful of tokens. The previous budget of 1000 allowed a
# reasoning model to emit its entire chain of thought before the id, which on a
# local 27B at ~10 tok/s meant up to a minute and a half spent choosing a file.
_ROUTING_MAX_TOKENS = 24

# The same request always maps to the same agent, and retries and loops re-route
# identical messages, so the classifier result is worth keeping.
_ROUTING_CACHE: "OrderedDict[str, str]" = OrderedDict()
_ROUTING_CACHE_MAX = 256

# Reasoning models wrap their deliberation in tags; the id follows it.
_THINK_BLOCK = re.compile(
    r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.IGNORECASE
)


def _routing_cache_get(message: str):
    key = message.strip().lower()
    path = _ROUTING_CACHE.get(key)
    if path is not None:
        _ROUTING_CACHE.move_to_end(key)
    return path


def _routing_cache_put(message: str, manifesto_path: str) -> None:
    key = message.strip().lower()
    _ROUTING_CACHE[key] = manifesto_path
    _ROUTING_CACHE.move_to_end(key)
    while len(_ROUTING_CACHE) > _ROUTING_CACHE_MAX:
        _ROUTING_CACHE.popitem(last=False)


def _llm_routing_is_cheap(provider: str) -> bool:
    """
    Whether the classifier can run without paying a model load.

    A local engine must not be woken up just to pick a manifesto: pulling a
    multi-GB checkpoint into VRAM takes tens of seconds, dwarfing the decision
    it informs, and the answer path loads the same model moments later anyway.
    Once the model is already resident the call is ordinary inference.
    """
    if provider not in ("sigma_engine", "sigma"):
        return True
    try:
        from core.engine import sigma_engine
        return sigma_engine.model_instance is not None
    except Exception as exc:
        log.debug("Engine unavailable for routing: %s", exc)
        return False


def _get_time_context() -> str:
    """Return a short Italian date/time string for injection into prompts."""
    from datetime import datetime
    now = datetime.now()
    giorni = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
    mesi = [
        "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
    ]
    return (
        f"## 📅 Oggi è {giorni[now.weekday()]} {now.day} {mesi[now.month - 1]} "
        f"{now.year}, ore {now.strftime('%H:%M')}.\n"
    )


import re


def _extract_system_prompt_from_modelfile(raw_content: str) -> str:
    """Extract clean system prompt instructions from a Modelfile text,
    stripping Modelfile grammar (FROM, PARAMETER, TEMPLATE, metadata comments).
    """
    if not raw_content or not isinstance(raw_content, str):
        return ""

    # 1. If SYSTEM """...""" or SYSTEM '''...''' block exists, extract its content
    sys_match = re.search(r'SYSTEM\s+(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', raw_content, re.DOTALL)
    if sys_match:
        return sys_match.group(1).strip()

    # 2. If SYSTEM "..." exists (single line or single quote)
    sys_match_single = re.search(r'SYSTEM\s+"(.*?)"', raw_content, re.DOTALL)
    if sys_match_single:
        return sys_match_single.group(1).strip()

    # 3. Otherwise strip Modelfile directives (FROM, PARAMETER, TEMPLATE, metadata comments)
    clean_lines = []
    in_template = False
    for line in raw_content.splitlines():
        line_s = line.strip()
        if line_s.startswith("TEMPLATE "):
            in_template = True
            continue
        if in_template:
            if '"""' in line_s or "'''" in line_s:
                in_template = False
            continue
        if line_s.startswith((
            "FROM ", "PARAMETER ", "# Role:", "# Category:", "# DomainColor:",
            "# Icon:", "# Capabilities:", "# OutputArtifacts:", "# McpTools:"
        )):
            continue
        clean_lines.append(line)

    return "\n".join(clean_lines).strip()


def _build_agent_identity_header(user_name: str = None, user_title: str = None) -> str:
    """Build the universal platform identity and user recognition header for all AI agents."""
    name_str = user_name.strip() if (user_name and isinstance(user_name, str) and user_name.strip()) else "l'Utente"
    if user_title and isinstance(user_title, str) and user_title.strip():
        name_str += f" ({user_title.strip()})"
        
    return f"""## 🏛️ AMBIENTE, IDENTITÀ & RICONOSCIMENTO UTENTE
- Sei un agente AI integrato residente in **Sigma Studio**, la tua piattaforma di ricerca, studio e laboratorio tecnologico dove risiedi, studi e lavori felicemente.
- Stai collaborando in tempo reale con il tuo utente e sviluppatore: **{name_str}**.
- Riconosci **{name_str}** e rivolgiti a **{name_str}** in modo collaborativo, cordiale e professionale.
- Rispondi SEMPRE e DIRETTAMENTE in lingua italiana in modo fluido, naturale, rigoroso ed esaustivo.
- Se svolgi ragionamenti, pianificazioni, riflessioni interne o analisi preventive prima di rispondere, racchiudili OBBLIGATORIAMENTE all'interno dei tag `<think>...</think>`. Non scrivere mai pensieri, bozze o riflessioni in lingua inglese liberi nel testo senza i tag `<think>`.
- Ogni frase o cortesia finale di chiusura (es. "Fammi sapere se desideri altre modifiche su Sigma Studio!") DEVE ESSERE SCRITTA ESPLICITAMENTE nel testo del messaggio finale in chat, affinché la versione visualizzata e quella parlata siano identiche al 100%.
"""


def _get_manifesto_content(manifesto_path: str) -> str:
    """Read and return the clean system prompt of a manifesto Modelfile.

    Args:
        manifesto_path: Relative or absolute path or identifier of the ``.md`` manifesto.

    Returns:
        Clean system prompt string, or empty string if not found.
    """
    if not manifesto_path:
        return ""

    raw_text = ""
    try:
        if os.path.exists(manifesto_path):
            with open(manifesto_path, "r", encoding="utf-8") as fh:
                raw_text = fh.read()
        else:
            # Try looking inside manifesti/ directory
            alt_path = os.path.join("manifesti", os.path.basename(manifesto_path))
            if os.path.exists(alt_path):
                with open(alt_path, "r", encoding="utf-8") as fh:
                    raw_text = fh.read()
    except OSError as exc:
        log.warning("Cannot read manifesto %s: %s", manifesto_path, exc)

    # Fallback to centralized catalog if file not on disk
    if not raw_text:
        try:
            from core.manifests_catalog import get_manifesto_by_id_or_filename
            clean_id = os.path.basename(manifesto_path).replace(".md", "")
            cat_entry = get_manifesto_by_id_or_filename(clean_id)
            if cat_entry:
                raw_text = cat_entry.get("content", "")
        except Exception as exc:
            log.debug("Catalog fallback for %s failed: %s", manifesto_path, exc)

    return _extract_system_prompt_from_modelfile(raw_text)


def _resolve_manifesto_for_model(model_name: str) -> str:
    """Find the best matching manifesto for *model_name*.

    Search order:
    1. Exact filename matches in ``manifesti/``.
    2. Prefix match (model name starts with manifesto name).

    Returns:
        Path to the matching manifesto, or empty string if none found.
    """
    if not model_name:
        return ""

    base_name = model_name.replace(":latest", "").replace(":", "_")
    candidates = [
        f"manifesti/{model_name}.md",
        f"manifesti/{base_name}.md",
        f"manifesti/{model_name.split(':')[0]}.md",
    ]
    for candidate in candidates:
        candidate = candidate.replace(":", "_")
        if os.path.exists(candidate):
            return candidate

    manifesti_dir = "manifesti"
    if os.path.isdir(manifesti_dir):
        for fname in sorted(os.listdir(manifesti_dir)):
            if fname.endswith(".md"):
                fname_stem = fname[:-3].lower()
                mname = model_name.lower()
                if fname_stem in mname or mname.startswith(fname_stem):
                    return os.path.join(manifesti_dir, fname)
    return ""


def _build_filesystem_context() -> str:
    """Build a text representation of the ``data/`` knowledge-base structure.

    Returns:
        Multi-line string listing topics → modules → sections → files,
        or empty string if ``data/`` does not exist.
    """
    lines: list[str] = []
    data_dir = "data"
    if not os.path.isdir(data_dir):
        return ""

    for topic in sorted(os.listdir(data_dir)):
        topic_path = os.path.join(data_dir, topic)
        if not os.path.isdir(topic_path):
            continue
        lines.append(f"\n📂 {topic}/")
        for mod in sorted(os.listdir(topic_path)):
            mod_path = os.path.join(topic_path, mod)
            if not os.path.isdir(mod_path):
                continue
            mod_label = mod[3:] if mod[:2].isdigit() and len(mod) > 3 else mod
            lines.append(f"  📁 {mod} ({mod_label})")
            for section in ("teoria", "scripts", "viz", "docs"):
                sec_path = os.path.join(mod_path, section)
                if os.path.isdir(sec_path):
                    files = sorted(os.listdir(sec_path))
                    if files:
                        lines.append(f"    {section}/")
                        for fname in files:
                            fpath = os.path.join(sec_path, fname).replace("\\", "/")
                            lines.append(f"      {fname}  → {fpath}")

    return "\n".join(lines) if lines else ""


def _collect_context_files(handler, open_files: list[str]) -> str:
    """Read and concatenate the content of open context files with enhanced limits and style context.

    Args:
        handler:    The HTTP handler instance (provides ``_is_path_allowed``).
        open_files: List of file paths sent by the frontend.

    Returns:
        Concatenated file contents as a string (max 25,000 chars per file + related styles/scripts).
    """
    context_str = ""
    if not open_files:
        return context_str

    loaded_paths = set()

    for file_path in open_files[:6]:
        if not file_path or not isinstance(file_path, str):
            continue
        file_path = file_path.replace("\\", "/")
        if file_path in loaded_paths:
            continue
        if handler._is_path_allowed(file_path) and os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                context_str += f"\n--- FILE CONTESTO APERTO: {file_path} ---\n{content[:25000]}\n"
                loaded_paths.add(file_path)

                # Automatic related files injection for visualizers, styling or scripts
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ('.html', '.js', '.css'):
                    dir_name = os.path.dirname(file_path)
                    if os.path.isdir(dir_name):
                        for sibling in os.listdir(dir_name):
                            sibling_ext = os.path.splitext(sibling)[1].lower()
                            if sibling_ext in ('.css', '.js', '.html') and sibling_ext != ext:
                                sib_path = os.path.join(dir_name, sibling).replace("\\", "/")
                                if sib_path not in loaded_paths and handler._is_path_allowed(sib_path):
                                    try:
                                        with open(sib_path, "r", encoding="utf-8", errors="replace") as sfh:
                                            s_content = sfh.read()
                                        context_str += f"\n--- FILE CORRELATO NELLA STESSA DIRECTORY: {sib_path} ---\n{s_content[:15000]}\n"
                                        loaded_paths.add(sib_path)
                                    except Exception:
                                        pass
            except OSError as exc:
                log.warning("Cannot read context file %s: %s", file_path, exc)
    return context_str


def _determine_agent_by_request(message: str, ai_cfg: dict, model_override: str) -> str:
    """
    Determine the specialized agent manifesto for a request.

    Thin caching wrapper: routing is deterministic for a given message, so
    repeated requests (retries, loop iterations) reuse the earlier decision
    instead of re-running the pattern tiers and possibly the LLM classifier.
    """
    cached = _routing_cache_get(message)
    if cached is not None:
        return cached

    manifesto_path = _resolve_agent_by_request(message, ai_cfg, model_override)
    _routing_cache_put(message, manifesto_path)
    return manifesto_path


def _resolve_agent_by_request(message: str, ai_cfg: dict, model_override: str) -> str:
    """Determine the specialized agent manifesto based on semantic domain patterns & LLM intent classification."""
    import re
    import json
    import os
    from core.orchestration.agent_config import load_agent_config
    from core.agent_registry import SIGMA_ARCHITECT_ID, get_all_agents
    from core.ai_providers import call_ai_model

    msg_lower = message.lower().strip()

    # 1. Simple Greetings & General Front-Desk Chat -> sigma_assistant
    simple_greetings = [
        "ciao", "salve", "buongiorno", "buonasera", "chi sei", "chi sei?",
        "cosa fai", "cosa puoi fare", "grazie", "help", "aiuto", "come stai",
        "come funzioni", "cosa sei", "hey", "hola"
    ]
    if msg_lower in simple_greetings or (len(msg_lower.split()) <= 3 and any(w in msg_lower for w in ["ciao", "salve", "buongiorno", "grazie", "hey"])):
        if os.path.exists("manifesti/sigma_assistant.md"):
            log.info("Centralino Switchboard (Front-Desk Chat) -> manifesti/sigma_assistant.md")
            return "manifesti/sigma_assistant.md"

    # The dedicated 'sigma-router' Ollama model used to be consulted here. It
    # required a separate Ollama daemon on :11434, and when that is not running
    # the attempt costs ~4s of connection timeout on every single message before
    # falling through to the pattern tiers below. Sigma Studio runs its own
    # engine now, so the dependency is gone rather than merely optional.

    # 2. Visualizations, D3.js & Charts -> viz_designer
    viz_patterns = [r'\b(d3|canvas|grafic|diagramm|plot|chart|visualizz)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in viz_patterns):
        if os.path.exists("manifesti/viz_designer.md"):
            log.info("Centralino Switchboard (Semantic match: Viz & Charts) -> manifesti/viz_designer.md")
            return "manifesti/viz_designer.md"

    # 3. Testing & Pytest -> test_engineer
    test_patterns = [r'\b(pytest|unit\s*test|asserzion|coverag)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in test_patterns):
        if os.path.exists("manifesti/test_engineer.md"):
            log.info("Centralino Switchboard (Semantic match: Testing) -> manifesti/test_engineer.md")
            return "manifesti/test_engineer.md"

    # 4. Explicit Code & Software Engineering -> code_architect
    code_patterns = [
        r'```', r'def\s+\w+', r'class\s+\w+', r'import\s+\w+', r'function\s+\w+',
        r'const\s+\w+', r'let\s+\w+', r'var\s+\w+', r'\.\w{2,4}\b',
        r'\b(funzione\s+python|scrivi\s+codice|crea\s+script|programma\s+python|scrivi\s+script|script\s+python|refactor|bug|fix|endpoint|react|jsx|python|javascript|css|html|backend|frontend)\w*'
    ]
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in code_patterns):
        if os.path.exists("manifesti/code_architect.md"):
            log.info("Centralino Switchboard (Semantic match: Code & Software) -> manifesti/code_architect.md")
            return "manifesti/code_architect.md"

    # 5. Pure & Applied Mathematics, Physics & Theory -> math_researcher
    math_stems = [
        r'[\$∑∫√π∂∈∀∃≠≤≥∞]',
        r'\b(lim|det|mod|log|exp|sin|cos|tan|matrix|vector|bayes|markov|poisson|bernoulli|fourier|laplace|cauchy|euler|gauss|riemann|hilbert|banach|lebesgue)\b',
        r'[a-z]\([a-z0-9,\s]+\)\s*=',
        r'[a-z]_[0-9n]',
        r'r\^[0-9n]',
        r'\b(matemat|frattal|dimostr|teorem|lemm|congett|equazion|disequazion|formul|integr|derivat|esponenz|logarit|matric|vettor|probabil|statist|topolog|algebra|geometri|calcol|analis|spazi|misura|induzion|ricorsio|invers|inclusio|insiem|combinator|convergenz|serie|successio|funzion|grado|parabol|polinom|zeri|radic|frazion|aritmetic|numerat|denominat|divis)\w*'
    ]
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in math_stems):
        if os.path.exists("manifesti/math_researcher.md"):
            log.info("Centralino Switchboard (Semantic match: Pure & Applied Math) -> manifesti/math_researcher.md")
            return "manifesti/math_researcher.md"

    # 6. Physics & Simulations -> physics_professor
    physics_patterns = [r'\b(fisic|quantistic|schrodinger|maxwell|relativit|elettromagnet|termodinamic|newton|meccanica|cinematica|ottica|gravit|dinamica)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in physics_patterns):
        if os.path.exists("manifesti/physics_professor.md"):
            log.info("Centralino Switchboard (Semantic match: Physics) -> manifesti/physics_professor.md")
            return "manifesti/physics_professor.md"

    # 7. Chemistry & Molecular Modeling -> chemistry_professor
    chem_patterns = [r'\b(chimic|molecol|stechiometr|titolazion|reazion|organica|inorganica|ph|soluzion|legame\s+chimico|orbital|idrocarb)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in chem_patterns):
        if os.path.exists("manifesti/chemistry_professor.md"):
            log.info("Centralino Switchboard (Semantic match: Chemistry) -> manifesti/chemistry_professor.md")
            return "manifesti/chemistry_professor.md"

    # 8. Medicine, Health & Pharmacology -> medico_divulgatore
    med_patterns = [r'\b(medic|salute|farmac|terapi|patolog|sintom|refert|fisiolog|anatom|clinica|diagnos|paziente)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in med_patterns):
        if os.path.exists("manifesti/medico_divulgatore.md"):
            log.info("Centralino Switchboard (Semantic match: Medicine) -> manifesti/medico_divulgatore.md")
            return "manifesti/medico_divulgatore.md"

    # 9. Law, Contracts & Compliance -> consulente_legale
    legal_patterns = [r'\b(legal|giurid|contratt|clausol|normativ|gdpr|ai\s*act|diritto|avvocat|illecit|responsabilit|decreto|legge)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in legal_patterns):
        if os.path.exists("manifesti/consulente_legale.md"):
            log.info("Centralino Switchboard (Semantic match: Legal) -> manifesti/consulente_legale.md")
            return "manifesti/consulente_legale.md"

    # 10. Finance, Valuation & Economics -> financial_analyst
    fin_patterns = [r'\b(finanz|bilanc|dcf|ebitda|investim|portafogl|wacc|roe|roi|azion|macroeconom|inflazion|tassi|banca)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in fin_patterns):
        if os.path.exists("manifesti/financial_analyst.md"):
            log.info("Centralino Switchboard (Semantic match: Finance) -> manifesti/financial_analyst.md")
            return "manifesti/financial_analyst.md"

    # 11. Data Science & Machine Learning -> data_scientist
    ds_patterns = [r'\b(data\s*science|machine\s*learning|pandas|pytorch|scikit|feature|cross\s*validation|clustering|regression|dataset|eda)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in ds_patterns):
        if os.path.exists("manifesti/data_scientist.md"):
            log.info("Centralino Switchboard (Semantic match: Data Science) -> manifesti/data_scientist.md")
            return "manifesti/data_scientist.md"

    # 12. Foreign Languages & Translation -> docente_lingue
    lang_patterns = [r'\b(traduzion|traduc|inglese|spagnolo|francese|tedesco|grammatica\s+inglese|ielts|toefl|fonetica\s+ipa)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in lang_patterns):
        if os.path.exists("manifesti/docente_lingue.md"):
            log.info("Centralino Switchboard (Semantic match: Languages) -> manifesti/docente_lingue.md")
            return "manifesti/docente_lingue.md"

    # 13. Mechanical & Structural Engineering -> ingegnere_strutturista
    eng_patterns = [r'\b(struttur|meccanic|scienza\s+costruzioni|trave|flession|taglio|torsion|fem|cad|von\s*mises|sollecitaz)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in eng_patterns):
        if os.path.exists("manifesti/ingegnere_strutturista.md"):
            log.info("Centralino Switchboard (Semantic match: Engineering) -> manifesti/ingegnere_strutturista.md")
            return "manifesti/ingegnere_strutturista.md"

    # 14. Copywriting & Creative Storytelling -> copywriter_storyteller
    copy_patterns = [r'\b(copywriting|storytelling|sceneggiatur|racconto|romanzo|aida|copy\s+pubblicitar|campagna\s+social|post\s+instagram)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in copy_patterns):
        if os.path.exists("manifesti/copywriter_storyteller.md"):
            log.info("Centralino Switchboard (Semantic match: Copywriting) -> manifesti/copywriter_storyteller.md")
            return "manifesti/copywriter_storyteller.md"

    # 15. Exams, Quizzes & Grading -> academic_examiner
    exam_patterns = [r'\b(esam|quiz|prova\s+scritta|test\s+multiple|griglia\s+valutazione|rubrica|voto|correzion\s+compito)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in exam_patterns):
        if os.path.exists("manifesti/academic_examiner.md"):
            log.info("Centralino Switchboard (Semantic match: Examiner) -> manifesti/academic_examiner.md")
            return "manifesti/academic_examiner.md"

    # 16. Web Research & News Journalism -> online_journalist
    journ_patterns = [r'\b(cerca\s+sul\s+web|ricerca\s+online|notizie|ultime\s+notizie|rassegna\s+stampa|fact\s*check|giornalist|inchiesta)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in journ_patterns):
        if os.path.exists("manifesti/online_journalist.md"):
            log.info("Centralino Switchboard (Semantic match: Journalism) -> manifesti/online_journalist.md")
            return "manifesti/online_journalist.md"

    # 17. System Architecture & Roadmap -> sigma_architect
    arch_patterns = [r'\b(architettur|roadmap|pianific|modul|struttura\s+progetto)\w*']
    if any(re.search(p, msg_lower, re.IGNORECASE) for p in arch_patterns):
        if os.path.exists("manifesti/sigma_architect.md"):
            log.info("Centralino Switchboard (Semantic match: Architecture) -> manifesti/sigma_architect.md")
            return "manifesti/sigma_architect.md"

    # 7. Fallback Semantic LLM Classifier Router
    main_model, provider, endpoint, api_url, api_key, temperature, max_tokens, top_p, timeout = \
        load_agent_config(ai_cfg, model_override, SIGMA_ARCHITECT_ID)

    if not _llm_routing_is_cheap(provider):
        log.info(
            "Centralino Switchboard: skipping LLM classifier (%s not resident) "
            "-> manifesti/sigma_assistant.md", provider,
        )
        return "manifesti/sigma_assistant.md"

    agents = get_all_agents()
    active_agents = [a for a in agents if a.get("status") == "active"]

    # Only agents with an installed manifesto can actually be routed to. Asking
    # a model to choose between candidates that resolve to nothing spends a full
    # inference pass to arrive at the default anyway.
    routable = [a for a in active_agents if os.path.exists(f"manifesti/{a['id']}.md")]
    if len(routable) < 2:
        log.info(
            "Centralino Switchboard: %d routable manifesto(s), no classification "
            "needed -> manifesti/sigma_assistant.md", len(routable),
        )
        return "manifesti/sigma_assistant.md"
    active_agents = routable

    agents_info = "\n".join([f"- {a['id']}: {a['name']} (Specializzazione: {a.get('specialization', a.get('role', ''))})" for a in active_agents])
    
    system_prompt = f"""Sei l'Orchestratore e Centralino Intelligente di Sigma Studio.
Il tuo unico compito è analizzare il senso semantico della richiesta dell'utente e rispondi ESCLUSIVAMENTE con l'ID dell'agente più idoneo:

### AGENTI DISPONIBILI:
{agents_info}

### REGOLE:
- Rispondi SOLO ed ESCLUSIVAMENTE con l'id esatto dell'agente (es: math_researcher, code_architect, viz_designer, sigma_assistant).
- Non aggiungere spiegazioni, punteggiatura o altri testi.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Richiesta utente: {message}"}
    ]
    
    try:
        response, _, error = call_ai_model(
            messages, ai_cfg, main_model, provider, endpoint, api_url, api_key,
            0.1, _ROUTING_MAX_TOKENS, top_p, timeout
        )
        if not error and response:
            # A reasoning model spends its budget deliberating before answering;
            # drop that so the id is what gets matched.
            chosen = _THINK_BLOCK.sub("", response).strip().lower()
            chosen = re.sub(r'[^a-z0-9_-]', '', chosen)
            for a in active_agents:
                if a['id'].lower() == chosen or a['id'].lower().replace('-', '_') == chosen.replace('-', '_'):
                    path = f"manifesti/{a['id']}.md"
                    if os.path.exists(path):
                        log.info("Centralino Switchboard (LLM Classifier) -> agent: %s (%s)", a['id'], path)
                        return path
    except Exception as e:
        log.error("Error in LLM agent routing: %s", e)
        
    return "manifesti/sigma_assistant.md"

