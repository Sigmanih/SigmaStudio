# ==============================================================================
# core/chat/history.py — Fitting a conversation into the window it has
#
# The old rule was `history_messages[-10:]`. Ten messages can be two hundred
# tokens or forty thousand, and the difference decides whether the model has
# room left to answer at all. Worse, nothing told the model that anything had
# been cut, so it would confidently contradict a decision made twelve turns ago
# as though it had never happened.
#
# Counting is done with the resident model's own tokenizer where there is one,
# and with a language-aware estimate where there is not -- a cloud provider, or
# a host with no local runtime. The estimate is deliberately pessimistic: an
# overestimate drops one message too many, an underestimate overflows the
# window and loses the whole turn.
# ==============================================================================
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.logger import get_logger

log = get_logger(__name__)

# Italian runs to roughly three characters per token on the multilingual
# vocabularies these models use -- markedly denser than English. Dividing by
# four, the usual English rule of thumb, understates an Italian prompt by about
# a quarter, which is exactly the direction that overflows a context window.
_CHARS_PER_TOKEN_FALLBACK = 3.0

# Per-message overhead for the chat template's role markers and separators.
_MESSAGE_FRAMING_TOKENS = 4

# Never trim below this: an assistant that cannot see the exchange immediately
# before the current question is not saving context, it is losing the thread.
_MIN_KEPT_MESSAGES = 2


def estimate_tokens(text: str, tokenizer: Any = None) -> int:
    """Token count for a piece of text, exact where possible."""
    if not text:
        return 0
    if tokenizer is not None:
        try:
            return len(tokenizer.encode(text, add_special_tokens=False))
        except Exception:
            try:                                   # llama.cpp handles bytes
                return len(tokenizer.tokenize(text.encode("utf-8")))
            except Exception:
                pass
    return int(len(text) / _CHARS_PER_TOKEN_FALLBACK) + 1


def resident_tokenizer() -> Any:
    """
    The tokenizer of whatever model is loaded, or None.

    Tolerant by construction: this runs on hosts with no engine package at all,
    and a missing tokenizer must cost accuracy, not the request.
    """
    try:
        from core.engine import sigma_engine
    except Exception:
        return None

    tokenizer = getattr(sigma_engine, "tokenizer_instance", None)
    if tokenizer is not None:
        return tokenizer

    backend = getattr(sigma_engine, "active_backend_instance", None)
    llm = getattr(backend, "_llm", None) if backend is not None else None
    return llm                                     # exposes .tokenize(bytes)


def trim_history(
    messages: List[Dict[str, str]],
    budget_tokens: int,
    tokenizer: Any = None,
    count: Optional[Callable[[str], int]] = None,
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """
    The newest slice of a conversation that fits in `budget_tokens`.

    Walks backwards from the most recent turn, because recency is what a reply
    depends on, and stops when the next message would not fit. Returns the kept
    messages in their original order, plus a report of what was left out so the
    caller can tell the model rather than let it assume.
    """
    if not messages:
        return [], {"kept": 0, "dropped": 0, "tokens": 0, "budget": budget_tokens}

    measure = count or (lambda text: estimate_tokens(text, tokenizer))

    kept: List[Dict[str, str]] = []
    used = 0
    dropped_roles: List[str] = []

    for message in reversed(messages):
        cost = measure(message.get("content", "")) + _MESSAGE_FRAMING_TOKENS
        # The floor wins over the budget: a window too small for one exchange
        # is a placement problem, and silently sending nothing hides it.
        if used + cost > budget_tokens and len(kept) >= _MIN_KEPT_MESSAGES:
            dropped_roles.append(message.get("role", "?"))
            continue
        kept.append(message)
        used += cost

    kept.reverse()
    dropped = len(messages) - len(kept)

    report = {
        "kept": len(kept),
        "dropped": dropped,
        "tokens": used,
        "budget": budget_tokens,
        "exact": tokenizer is not None,
    }
    if dropped:
        log.info(
            "[History] %d/%d messaggi tenuti (~%d token su %d disponibili)",
            len(kept), len(messages), used, budget_tokens,
        )
    return kept, report


def dropped_notice(report: Dict[str, Any]) -> str:
    """
    One line telling the model what it can no longer see.

    Without it the model treats a truncated history as a complete one, which is
    how it ends up contradicting something the user agreed to earlier and
    sounding careless rather than merely limited.
    """
    dropped = report.get("dropped", 0)
    if not dropped:
        return ""
    return (
        f"_[{dropped} messaggi precedenti non rientrano nella finestra di "
        f"contesto e non ti sono stati mostrati. Se la richiesta dipende da "
        f"qualcosa che non vedi, chiedilo invece di darlo per scontato.]_"
    )


def history_budget(
    context_window: int,
    fixed_tokens: int,
    reserve_for_answer: int,
) -> int:
    """
    How many tokens the history may occupy.

    The window has to hold three things: the parts that are not negotiable (the
    system prompt, the volatile context, the question), the history, and room
    for the answer. The history is the only elastic one, so it gets what is
    left -- never a fixed fraction, which is how a long system prompt and a
    long history combine to leave the model no room to reply.
    """
    if context_window <= 0:
        return 8192                                # unknown window: stay modest
    return max(context_window - fixed_tokens - reserve_for_answer, 0)
