# ==============================================================================
# core/engine/evaluation.py — Bare, deterministic inference
#
# Sigma Studio normally wraps a model in a product: a persona, the tool
# protocol, the project's memory, the response parser that rescues structure
# from prose. That wrapper is the point of the product, and it is exactly what
# two callers must not get:
#
#   * the benchmark, which is measuring the model and not the wrapper. A score
#     obtained with a Sigma persona in the system prompt and the MCP tools in
#     reach is a score for Sigma Studio, not for the checkpoint, and it is not
#     comparable with any number published for that checkpoint elsewhere.
#
#   * the provider server, which is handing the model to somebody else's
#     client. That client sent its own system prompt, its own sampler and its
#     own expectations; a persona injected underneath it is a silent change to
#     an API contract.
#
# So this module is the whole Sigma layer, removed on purpose, in one place --
# rather than each caller remembering to disable four different things.
#
# Three properties are enforced together, because any one of them alone still
# leaves the measurement dirty:
#
#   neutrality    no persona, no tools, no memory; only the caller's messages.
#   determinism   greedy decoding, no repetition penalty, a fixed seed. The
#                 same question gives the same answer, run after run.
#   terseness     reasoning blocks off and stop sequences on, so the token
#                 budget is spent on the answer rather than on a `<think>`
#                 block that gets truncated before the answer arrives.
# ==============================================================================
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from core.engine.sampling import SamplingParams
from core.logger import get_logger

log = get_logger(__name__)


#: Fixed so a run is reproducible. Greedy decoding does not consult it, but any
#: layer below that does (dropout in an exotic head, a backend that samples
#: anyway) must not be free to vary between runs.
DETERMINISTIC_SEED = 42

#: The sampler that measures the model rather than a sampler.
#:
#: A vendor recipe -- top_p 0.8, a repetition penalty of 1.05 -- is the right
#: default for chat, where it buys fluency. Under measurement it is a thumb on
#: the scale, and the repetition penalty in particular actively costs accuracy
#: on arithmetic, where the correct answer legitimately repeats digits the
#: prompt already contains.
NEUTRAL_SAMPLER = {
    "temperature": 0.0,
    "top_p": 1.0,
    "top_k": 0,
    "min_p": 0.0,
    "repeat_penalty": 1.0,
}

#: Where an answer is over, per task shape. Without these the model keeps
#: writing -- a second worked example, a restatement, a new "Answer:" line --
#: and it is the second answer that turns a correct response into an ambiguous
#: verdict. Cheaper and more honest to stop it at the first.
STOP_MULTIPLE_CHOICE: Tuple[str, ...] = ("\nQuestion:", "\nQ:", "\n\nQuestion")
STOP_SHORT_ANSWER: Tuple[str, ...] = ("\nQuestion:", "\nTask:", "\nQ:")
STOP_MATH: Tuple[str, ...] = ("\nQuestion:", "\nProblem:")
STOP_CODE: Tuple[str, ...] = ("\nTask:", "\n# Task")

#: What opens the assistant's turn when the answer is read from the
#: distribution rather than from the text. It is the same device every public
#: multiple-choice harness uses, and it is not a hint: it says where the answer
#: goes, not which one it is. Without it, the position being read is the first
#: token of a free reply -- and a model opens that with "When" or "The", not
#: with a label.
CHOICE_ANSWER_PREFIX = "Answer:"


@dataclass
class Completion:
    """One answer, with what it cost and whether it is usable."""

    text: str = ""
    tokens: int = 0
    prompt_tokens: int = 0
    tokens_per_sec: float = 0.0
    ttft_ms: float = 0.0
    finish_reason: str = "stop"
    error: str = ""
    batch_size: int = 1
    sampling: Dict[str, Any] = field(default_factory=dict)

    #: The model will not answer this prompt or any other -- the weights could
    #: not be loaded. A caller with a queue of thousands should stop, not write
    #: the same failure a thousand times and call it a score.
    fatal: bool = False
    #: The engine's own diagnosis of a fatal failure, stage and remedy included.
    diagnosis: str = ""
    #: Something went wrong but an answer came back anyway -- a generation cut
    #: short by a deadline, most often. The text is usable and the reason is
    #: worth recording next to it.
    warning: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


# ---------------------------------------------------------------------------
# Sampler
# ---------------------------------------------------------------------------

def deterministic_params(
    max_tokens: int = 512,
    stop: Sequence[str] = (),
    seed: Optional[int] = DETERMINISTIC_SEED,
    num_ctx: int = 0,
) -> SamplingParams:
    """
    The neutral sampler, built directly rather than resolved.

    `SamplingParams.resolve` deliberately layers a family recipe, the provider
    config and the execution profile on top of each other -- which is right for
    a chat and wrong here, because every one of those layers is a decision made
    by this machine's configuration rather than by the model. Measurement needs
    the same numbers on every machine, so it starts from nothing.
    """
    return SamplingParams(
        temperature=float(NEUTRAL_SAMPLER["temperature"]),
        top_p=float(NEUTRAL_SAMPLER["top_p"]),
        top_k=int(NEUTRAL_SAMPLER["top_k"]),
        min_p=float(NEUTRAL_SAMPLER["min_p"]),
        repeat_penalty=float(NEUTRAL_SAMPLER["repeat_penalty"]),
        max_tokens=int(max_tokens),
        num_ctx=int(num_ctx or 0),
        seed=seed,
        stop=tuple(s for s in stop if s),
        source="evaluation:neutral",
    )


# ---------------------------------------------------------------------------
# Reading a stream without reading the furniture
# ---------------------------------------------------------------------------

def is_notice(chunk: Dict[str, Any]) -> bool:
    """
    Whether a chunk is the engine talking, rather than the model.

    The engine narrates: it says it is loading weights, that the placement had
    to spill to RAM, that another request holds the lock. In a chat bubble that
    is exactly right. Concatenated blindly into a completion it becomes the
    model's answer -- which is how a benchmark ends up grading the string
    "Motore occupato da un'altra richiesta" as a wrong answer to a physics
    question, and how an API client receives Italian UI prose it never asked
    for.
    """
    if not isinstance(chunk, dict):
        return True
    return bool(
        chunk.get("notice")
        or chunk.get("loading")
        or chunk.get("type") in ("status", "error")
    )


def collect(stream: Iterable[Dict[str, Any]]) -> Completion:
    """Drains a generate_stream into one answer, keeping notices out of it."""
    result = Completion()
    pieces: List[str] = []

    for chunk in stream:
        if not isinstance(chunk, dict):
            continue
        if is_notice(chunk):
            failure = chunk.get("error")
            if failure:
                # The engine's own explanation is the useful error message;
                # the code beside it is what a caller can branch on.
                result.error = str(chunk.get("token") or failure).strip()
            continue

        token = chunk.get("token") or ""
        if token:
            pieces.append(token)
        if chunk.get("ttft_ms"):
            result.ttft_ms = float(chunk["ttft_ms"])
        if chunk.get("done"):
            result.tokens = int(chunk.get("total_tokens") or 0)
            result.prompt_tokens = int(chunk.get("prompt_tokens") or 0)
            result.tokens_per_sec = float(chunk.get("speed_tok_s") or 0.0)
            if isinstance(chunk.get("sampling"), dict):
                result.sampling = chunk["sampling"]

    text = "".join(pieces)
    result.text = text.strip()
    if not result.tokens:
        result.tokens = len(text.split())
    return result


# ---------------------------------------------------------------------------
# The two entry points
# ---------------------------------------------------------------------------

def complete(
    messages: List[Dict[str, str]],
    model_name: Optional[str] = None,
    max_tokens: int = 512,
    stop: Sequence[str] = (),
    seed: Optional[int] = DETERMINISTIC_SEED,
    thinking: Optional[bool] = False,
    engine=None,
) -> Completion:
    """
    One neutral, deterministic answer, in process.

    Deliberately not routed through the provider server: that path is gated on
    a user-facing toggle ("Providers Hub -> abilita"), and a measurement that
    silently reports zeroes because a switch in the UI is off is worse than one
    that refuses to start. The engine is right here; this calls it.
    """
    if engine is None:
        from core.engine.unified_runtime import sigma_engine as engine

    params = deterministic_params(max_tokens=max_tokens, stop=stop, seed=seed)
    conversation = _clean(messages)
    if not conversation:
        return Completion(error="Nessun messaggio da inviare al modello.")

    result = collect(engine.generate_stream(
        prompt=conversation[-1].get("content", ""),
        system_prompt=_system_of(conversation),
        messages=conversation,
        model_name=model_name,
        params=params,
        thinking=thinking,
    ))
    if not result.sampling:
        result.sampling = params.to_dict()
    # A stop string reached mid-stream on a backend that cannot enforce it.
    result.text, _ = _cut(result.text, params.stop)
    return result


def complete_batch(
    conversations: List[List[Dict[str, str]]],
    model_name: Optional[str] = None,
    max_tokens: int = 512,
    stop: Sequence[str] = (),
    seed: Optional[int] = DETERMINISTIC_SEED,
    thinking: Optional[bool] = False,
    batch_size: int = 0,
    cancel: Any = None,
    on_result=None,
    engine=None,
) -> List[Completion]:
    """
    Many neutral answers, in as few forward passes as the device allows.

    This is the shape that makes an evaluation finish. A benchmark is thousands
    of prompts that do not depend on each other, and answering them one at a
    time leaves a GPU decoding a single sequence -- bound by how fast the
    weights can be read, with the arithmetic units idle. The second prompt in a
    batch reads the same weights as the first.
    """
    if engine is None:
        from core.engine.unified_runtime import sigma_engine as engine

    params = deterministic_params(max_tokens=max_tokens, stop=stop, seed=seed)
    cleaned = [_clean(conv) for conv in conversations]

    raw = engine.generate_batch(
        conversations=cleaned,
        params=params,
        model_name=model_name,
        thinking=thinking,
        batch_size=batch_size,
        cancel=cancel,
        on_result=on_result,
    )

    answers: List[Completion] = []
    for entry in raw:
        text, _ = _cut(str(entry.get("text") or ""), params.stop)
        answers.append(Completion(
            text=text.strip(),
            tokens=int(entry.get("tokens") or 0),
            prompt_tokens=int(entry.get("prompt_tokens") or 0),
            tokens_per_sec=float(entry.get("tokens_per_sec") or 0.0),
            finish_reason=str(entry.get("finish_reason") or "stop"),
            error=str(entry.get("error") or ""),
            batch_size=int(entry.get("batch_size") or 1),
            sampling=params.to_dict(),
            fatal=bool(entry.get("fatal")),
            diagnosis=str(entry.get("diagnosis") or ""),
            warning=str(entry.get("warning") or ""),
        ))
    return answers


def choose(
    conversations: List[List[Dict[str, str]]],
    letters: List[List[str]],
    model_name: Optional[str] = None,
    batch_size: int = 0,
    engine=None,
) -> List[Dict[str, Any]]:
    """
    Which option the model ranks first, read off the distribution.

    The generative protocol asks for a letter and gets an essay, then mines the
    essay with regular expressions. That is where the ambiguous verdicts come
    from: an answer that says "A is correct because H confuses the two" has
    chosen once and mentions twice, and no parser can tell those apart reliably
    in every phrasing a model can produce.

    Reading the logits at the first answer position asks the same question with
    no prose in between. It returns one ranking, always, plus the margin over
    the runner-up so a near-tie is visible as a near-tie instead of being
    silently resolved. It also costs one forward pass instead of a thousand
    decode steps, which is most of why a full-suite run took hours.

    Returns an empty list when the resident backend cannot expose logits (a
    GGUF served by llama.cpp), so the caller can fall back to the constrained
    generative path rather than treat it as a failure.
    """
    if engine is None:
        from core.engine.unified_runtime import sigma_engine as engine

    if not hasattr(engine, "choice_logits"):
        return []

    outcomes = engine.choice_logits(
        conversations=[_clean(conv) for conv in conversations],
        letters=letters,
        model_name=model_name,
        thinking=False,
        batch_size=batch_size,
        answer_prefix=CHOICE_ANSWER_PREFIX,
    )
    if outcomes and all(o.get("error") == "unsupported_backend" for o in outcomes):
        return choose_constrained(
            conversations, letters, model_name=model_name,
            batch_size=batch_size, engine=engine,
        )
    return outcomes


def rank_continuations(
    questions: List[Tuple[str, List[str]]],
    model_name: Optional[str] = None,
    normalize: str = "char",
    batch_size: int = 0,
    engine=None,
) -> List[Dict[str, Any]]:
    """
    Which of several candidate answers the model finds most likely, as text.

    The measurement HellaSwag, ARC and TruthfulQA are published on. It asks the
    model nothing: no label to pick, no format to follow, no instruction to
    obey. Each candidate ending is scored as a continuation of the context, and
    the most probable one is the answer. A small model that cannot reliably
    produce "Answer: C" still answers this correctly, which is the point --
    those benchmarks are about commonsense and knowledge, not about compliance
    with an answer format.

    `normalize` divides the log-probability before comparing, because otherwise
    the shortest candidate wins almost always: every additional token can only
    subtract probability. "char" divides by the length in characters, which is
    what `acc_norm` means on the public leaderboards; "token" divides by the
    token count; "" compares raw sums.

    Returns, per question: the winning index, the normalised score of each
    candidate, and the margin over the runner-up. An empty list means the
    resident backend cannot expose log-probabilities.
    """
    if engine is None:
        from core.engine.unified_runtime import sigma_engine as engine

    if not hasattr(engine, "continuation_logprobs"):
        return []

    pairs: List[Tuple[str, str]] = []
    spans: List[Tuple[int, int]] = []
    for context, options in questions:
        start = len(pairs)
        for option in options:
            pairs.append((context, option))
        spans.append((start, len(pairs)))

    scored = engine.continuation_logprobs(
        pairs, model_name=model_name, batch_size=batch_size,
    )
    if scored and all(s.get("error") == "unsupported_backend" for s in scored):
        return []

    outcomes: List[Dict[str, Any]] = []
    for position, (start, end) in enumerate(spans):
        rows = scored[start:end]
        fatal = next((r for r in rows if r.get("fatal")), None)
        if fatal:
            outcomes.append({"index": position, "choice": None, "scores": [],
                             "margin": 0.0, "error": fatal.get("error", ""),
                             "fatal": True,
                             "diagnosis": fatal.get("diagnosis", "")})
            continue

        values: List[float] = []
        for row in rows:
            if row.get("error") or row["logprob"] == float("-inf"):
                values.append(float("-inf"))
                continue
            divisor = 1.0
            if normalize == "char":
                divisor = max(row.get("characters") or 1, 1)
            elif normalize == "token":
                divisor = max(row.get("tokens") or 1, 1)
            values.append(row["logprob"] / divisor)

        usable = [v for v in values if v != float("-inf")]
        if not usable:
            outcomes.append({"index": position, "choice": None, "scores": values,
                             "margin": 0.0,
                             "error": "nessuna continuazione valutabile"})
            continue

        best = max(range(len(values)), key=lambda i: values[i])
        runner_up = sorted(usable, reverse=True)
        outcomes.append({
            "index": position,
            "choice": best,
            "scores": [round(v, 6) if v != float("-inf") else None for v in values],
            # The gap to the second best, in normalised log-probability. A gap
            # near zero is a coin toss, and the review queue should see it.
            "margin": round(runner_up[0] - runner_up[1], 6) if len(runner_up) > 1 else 0.0,
            "error": "",
        })
    return outcomes


def choose_constrained(
    conversations: List[List[Dict[str, str]]],
    letters: List[List[str]],
    model_name: Optional[str] = None,
    batch_size: int = 0,
    engine=None,
) -> List[Dict[str, Any]]:
    """
    The same single answer, for a backend whose logits are out of reach.

    A GGUF served by llama.cpp decodes behind a C API that returns tokens, not
    distributions. What it does expose is a grammar, and a grammar over the
    option labels makes every other continuation unreachable: the model cannot
    emit a paragraph, cannot mention a second letter, cannot answer "it depends"
    -- the tokens for all of that are masked out before the sample.

    So the guarantee is the same one the logit path gives (exactly one label,
    every time, in one token) arrived at from the other side: there the prose
    was never generated because it was never read, here because it could not be
    produced. What is missing is the ranking of the options that were not
    chosen, so there is no margin to report.
    """
    if engine is None:
        from core.engine.unified_runtime import sigma_engine as engine

    from core.engine.grammars import choice_grammar

    outcomes: List[Dict[str, Any]] = [
        {"index": i, "choice": None, "probs": {}, "margin": 0.0, "error": ""}
        for i in range(len(conversations))
    ]

    # Grouped by label set: MMLU-Pro runs to J where ARC stops at D, and one
    # grammar cannot admit both without admitting answers the item does not have.
    groups: Dict[Tuple[str, ...], List[int]] = {}
    for index, options in enumerate(letters):
        key = tuple(str(letter) for letter in (options or []))
        if not key:
            outcomes[index]["error"] = "nessuna opzione da vincolare"
            continue
        groups.setdefault(key, []).append(index)

    for key, indexes in groups.items():
        grammar = choice_grammar(key)
        if not grammar:
            for index in indexes:
                outcomes[index]["error"] = "grammatica non costruibile"
            continue

        params = deterministic_params(max_tokens=8).with_grammar(grammar)
        raw = engine.generate_batch(
            conversations=[_clean(conversations[i]) for i in indexes],
            params=params,
            model_name=model_name,
            thinking=False,
            batch_size=batch_size,
        )
        for position, entry in enumerate(raw):
            index = indexes[position]
            answer = str(entry.get("text") or "").strip().upper()
            chosen = next((letter for letter in key if answer.startswith(letter.upper())), None)
            outcomes[index].update({
                "choice": chosen,
                "error": str(entry.get("error") or ("" if chosen else "nessuna lettera emessa")),
                # No distribution to report: the grammar decided what could be
                # said, the model decided which of those it said, and nothing
                # in between is observable from here.
                "probs": {},
                "margin": 0.0,
                "constrained": True,
            })
    return outcomes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """The caller's conversation, and nothing added to it."""
    cleaned = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if content is None or content == "":
            continue
        role = str(message.get("role") or "user").strip().lower()
        if role not in ("system", "user", "assistant", "tool"):
            role = "user"
        cleaned.append({"role": role, "content": str(content)})
    return cleaned


def _system_of(messages: List[Dict[str, str]]) -> str:
    """The caller's system prompt, or genuinely none."""
    for message in messages:
        if message.get("role") == "system":
            return str(message.get("content") or "")
    return ""


def _cut(text: str, stop: Sequence[str]) -> Tuple[str, bool]:
    """Truncates at the first stop string, reporting whether one was found."""
    if not stop or not text:
        return text, False
    earliest, found = len(text), False
    for marker in stop:
        if not marker:
            continue
        at = text.find(marker)
        if at != -1 and at < earliest:
            earliest, found = at, True
    return (text[:earliest], True) if found else (text, False)
