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
from core import paths
from core.logger import get_logger

log = get_logger(__name__)

# --- Agent routing budget ----------------------------------------------------
# Routing picks one manifesto path. It is a classification, not a generation,
# and every millisecond it costs is latency before the user sees any answer.

# The same request always maps to the same agent, and retries and loops re-route
# identical messages, so the routing result is worth keeping.
_ROUTING_CACHE: "OrderedDict[str, str]" = OrderedDict()
_ROUTING_CACHE_MAX = 256


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


_GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
_MESI = [
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]

# Questions where the minute actually matters. Anything else is answered just as
# well by the date, which has the decisive advantage of not changing.
_ASKS_THE_TIME = re.compile(
    r"\b(che\s+or[ae]|orario|adesso|in\s+questo\s+momento|ora\s+esatta|"
    r"quanto\s+manca|fra\s+quanto|scadenz|deadline|timer|cronometr|"
    r"what\s+time|right\s+now|current\s+time)\w*", re.IGNORECASE
)


def _get_date_context() -> str:
    """
    Today's date, without the clock.

    Granularity is a caching decision, not a formatting one. A timestamp with
    minutes changes between one message and the next, and anything that changes
    cannot live in the part of the prompt the KV cache reuses -- so a detail
    almost no answer needs was costing a re-prefill on every turn. The date is
    stable for a day and sits in the prefix; the minute is added, in the
    volatile tail, only when the question is about time.
    """
    from datetime import datetime
    now = datetime.now()
    return (
        f"## 📅 Oggi è {_GIORNI[now.weekday()]} {now.day} "
        f"{_MESI[now.month - 1]} {now.year}.\n"
    )


def _get_time_context() -> str:
    """The full date and clock, for the turns that genuinely need the minute."""
    from datetime import datetime
    now = datetime.now()
    return (
        f"## 🕐 Ora corrente: {_GIORNI[now.weekday()]} {now.day} "
        f"{_MESI[now.month - 1]} {now.year}, ore {now.strftime('%H:%M')}.\n"
    )


def needs_precise_time(message: str) -> bool:
    """Whether this question is worth breaking the cacheable prefix for."""
    return bool(_ASKS_THE_TIME.search(message or ""))


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
- Il tuo ragionamento interno viene gestito automaticamente dal sistema prima che tu scriva la risposta. Scrivi SOLO la risposta finale in italiano, rivolta direttamente a {name_str}, senza preamboli, riflessioni interne o monologhi in inglese nel corpo della risposta.
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

    # Nessun ripiego sul catalogo: il catalogo tiene i metadati, non i corpi.
    # Un manifesto che non e' su disco non e' installato, e un agente non
    # installato non ha un prompt di sistema — lo dice l'orchestratore, che
    # invita a scaricarlo, invece di farlo funzionare a meta' con una copia di
    # riserva che nessuno teneva allineata al repository.
    if not raw_text:
        log.debug("Manifesto non installato: %s", manifesto_path)

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


# --- Knowledge-base tree cache ----------------------------------------------
# The tree was rebuilt from disk on every single chat message: a full walk of
# data/ before the model could be given anything. That is I/O per request and
# tokens per request, and both grow with how much the user has stored -- the
# product got slower the more it was used.
#
# The tree only changes when the user creates or deletes something, which is
# rare compared to how often they type. A short time-to-live plus the mtimes of
# the directories themselves catches every change the agents make through
# create_file / delete_file, at the cost of one stat per topic instead of a
# recursive listing.
_FS_CACHE_TTL_SECONDS = 45.0
_FS_MAX_FILES = 400            # beyond this the tree stops informing and starts crowding
_fs_cache: dict[str, object] = {"stamp": None, "text": "", "built_at": 0.0}


def _fs_tree_stamp(data_dir: str) -> tuple:
    """
    A cheap fingerprint of the tree's shape.

    Directory mtimes move when entries are added or removed at that level, so
    stat-ing the root and each topic detects every structural change without
    descending into the files themselves.
    """
    try:
        stamp = [os.stat(data_dir).st_mtime_ns]
        for entry in sorted(os.listdir(data_dir)):
            path = os.path.join(data_dir, entry)
            if os.path.isdir(path):
                stamp.append(os.stat(path).st_mtime_ns)
        return tuple(stamp)
    except OSError:
        return ()


def _build_filesystem_context() -> str:
    """Build a text representation of the ``data/`` knowledge-base structure.

    Cached: see the note above. Returns a multi-line string listing
    topics → modules → sections → files, or empty string if ``data/``
    does not exist.
    """
    import time

    data_dir = str(paths.workspace_dir())
    if not os.path.isdir(data_dir):
        return ""

    now = time.monotonic()
    fresh = (now - float(_fs_cache["built_at"])) < _FS_CACHE_TTL_SECONDS
    stamp = _fs_tree_stamp(data_dir)
    if fresh and _fs_cache["stamp"] == stamp:
        return str(_fs_cache["text"])

    lines: list[str] = []
    file_count = 0
    truncated = False

    for topic in sorted(os.listdir(data_dir)):
        if truncated:
            break
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
                            if file_count >= _FS_MAX_FILES:
                                truncated = True
                                break
                            fpath = os.path.join(sec_path, fname).replace("\\", "/")
                            lines.append(f"      {fname}  → {fpath}")
                            file_count += 1
                if truncated:
                    break
            if truncated:
                break

    if truncated:
        # Say so rather than silently showing a partial tree: an agent that
        # believes it has seen everything will report a file as missing.
        lines.append(
            f"\n… elenco troncato a {_FS_MAX_FILES} file. "
            "Usa gli strumenti di lettura del filesystem per il resto."
        )

    text = "\n".join(lines) if lines else ""
    _fs_cache["stamp"] = stamp
    _fs_cache["text"] = text
    _fs_cache["built_at"] = now
    return text


def invalidate_filesystem_context() -> None:
    """Drop the cached tree after an agent has written to ``data/``."""
    _fs_cache["stamp"] = None
    _fs_cache["built_at"] = 0.0


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
    """
    Pick the specialized manifesto for a request, without spending a model pass.

    Seventeen ordered pattern tiers handle what a regex can decide reliably;
    what they miss goes to the vector-similarity router at the bottom. Nothing
    on this path loads weights or waits on a generation, so routing costs
    microseconds to milliseconds rather than a full inference.
    """
    import re
    import os
    from core.agent_registry import get_all_agents

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

    # 18. Fallback: vector-similarity intent router.
    #
    # This used to be a full inference pass: the chat model was asked, in
    # prose, which manifesto to use, and the user waited for the whole
    # generation before their answer even started. On a 27B that is the single
    # largest fixed cost in front of the first token, paid on every message
    # that the pattern tiers above did not already resolve.
    #
    # core/embedding_router.py answers the same question by similarity against
    # curated anchor phrases. With sentence-transformers installed it is a
    # multilingual embedding lookup; without it, the module falls back to an
    # n-gram TF-IDF cosine that is pure standard library. Both land in single
    # -digit milliseconds and both run anywhere Python runs, which the model
    # pass never did.
    routable_ids = {
        a["id"] for a in get_all_agents()
        if a.get("status") == "active" and os.path.exists(f"manifesti/{a['id']}.md")
    }

    try:
        from core.embedding_router import classify_intent_multilingual

        verdict = classify_intent_multilingual(message)
        if verdict:
            agent = verdict.get("agent")
            if agent in routable_ids:
                log.info(
                    "Centralino Switchboard (Embedding Router, conf=%.2f) -> %s",
                    verdict.get("confidence", 0.0), agent,
                )
                return f"manifesti/{agent}.md"
            log.debug(
                "Embedding Router chose '%s', which has no installed manifesto; "
                "falling through to the front desk.", agent,
            )
    except Exception as exc:
        # A router that cannot answer is not an error worth failing a chat
        # over: the front desk handles anything unrouted perfectly well.
        log.debug("Embedding Router unavailable (%s); using the front desk.", exc)

    return "manifesti/sigma_assistant.md"
