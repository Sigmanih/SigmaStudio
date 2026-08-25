# ==============================================================================
# core/chat/chat_runner.py — Conversational Chat Runner & Streaming Engine
# Sigma Studio v8 — Modular Chat Sub-package
# ==============================================================================
"""AI chat conversation engine with multi-provider model routing, action execution,
file creation tracking, SSE streaming, and deterministic command handlers.
"""

import os
import json
import re
import datetime
import shutil
import time

from core.logger import get_logger
from core.ai_providers import (
    load_ai_config, resolve_provider_config,
    call_ollama, call_ollama_stream,
    call_openai_compatible, call_openai_compatible_stream,
    call_anthropic,
    detect_execution_profile, apply_execution_profile, EXECUTION_PROFILES,
)
from core.task_handler import execute_ai_actions
from core.agent_memory import get_memory_context, save_session_memory, save_decision_memory, load_memory
from core.agent_registry import increment_usage, get_agent
from core.store import tasks_store
from core.data_handler import rebuild_modules_meta
from core.backup_manager import create_backup
from core.task_handler import _compute_diff

from core.chat.response_parser import (
    _TAG_PATTERNS, _clean_all_tags, _extract_json_from_response,
    _extract_english_thinking, _extract_bullet_thinking, _extract_done_thinking,
    _format_response,
)
from core.chat.prompt_builder import (
    _get_time_context, _get_manifesto_content, _build_filesystem_context,
    _collect_context_files, _resolve_manifesto_for_model, _determine_agent_by_request,
    _build_agent_identity_header, invalidate_filesystem_context,
    _get_date_context, needs_precise_time,
)
from core.chat.file_extractor import (
    _normalize_data_path, _ensure_module_subfolders, _determine_default_module_path,
    _generate_files_summary, _format_conversational_summary, _extract_and_create_files_from_text,
)
from core.chat.web_search import _perform_web_search
from core.chat.history import (
    estimate_tokens, resident_tokenizer, trim_history, dropped_notice, history_budget,
)

log = get_logger(__name__)

# What a cloud model is assumed to hold when we cannot ask. Deliberately modest:
# every provider on the list is well past it, so the trim is conservative rather
# than an overflow waiting for the one provider that is not.
_DEFAULT_CLOUD_CONTEXT = 32768


def _engine_context_window() -> int:
    """
    The context of the resident local model, or a safe assumption for the cloud.

    Asked of the engine rather than of the checkpoint: the planner shrinks the
    window to what this machine could actually allocate, and budgeting a
    conversation against the trained figure builds a prompt the runtime refuses.
    """
    try:
        from core.engine import sigma_engine
        window = sigma_engine.context_window()
        if window:
            return window
    except Exception as exc:
        log.debug("Context window unavailable from the engine (%s)", exc)
    return _DEFAULT_CLOUD_CONTEXT


def _sanitize_history_message(content: str) -> str:
    """Sanitize history messages to remove old system prompts, role headers, welcome badges, and reasoning monologues."""
    if not content:
        return ""
    if "Chat pronta." in content or "🤖 **Sigma AI Studio**" in content:
        return ""
    clean = re.sub(r'FROM\s+[a-zA-Z0-9_\.\:]+[\s\S]*?SYSTEM\s+"""[\s\S]*?"""', '', content, flags=re.IGNORECASE)
    clean = re.sub(r'SYSTEM\s+"""[\s\S]*?"""', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'Ruolo\s+attivo:[\s\S]*?\n', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'Analyze\s+User\s+Input:[\s\S]*?(?:Final\s+Output\s+Generation:|Proceeds\.?|✅|\n\n)', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<think>[\s\S]*?</think>', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'📁\s*\*\*File salvati con successo su disco:\*\*[\s\S]*$', '', clean, flags=re.IGNORECASE)
    return clean.strip()


_THINK_TAG_RE = re.compile(r"</?(?:think|thinking|reasoning|rationale|scratchpad)>", re.IGNORECASE)


def _new_cancellation_token():
    """
    A token the engine can watch, or None where the engine is not installed.

    Chat must keep working on a host that has no local inference runtime at
    all -- a cloud-only laptop, or a board where the kernels have not been
    built yet. Everything downstream treats None as "never cancelled", so the
    feature degrades instead of breaking the import.
    """
    try:
        from core.engine.cancellation import CancellationToken
        return CancellationToken()
    except Exception as exc:
        log.debug("Cancellation unavailable (%s); streams run to completion.", exc)
        return None


def _resolve_sampling(model, provider_key, provider_cfg, profile, reasoning):
    """
    The sampler for this turn, or None to leave providers on their old defaults.

    Kept tolerant for the same reason as the token above: a missing engine
    package must cost the tuned sampling, not the answer.
    """
    try:
        from core.engine.sampling import SamplingParams
        return SamplingParams.resolve(
            model_name=model,
            provider_key=provider_key,
            provider_cfg=provider_cfg or {},
            profile=profile,
            reasoning=reasoning,
        )
    except Exception as exc:
        log.debug("SamplingParams unavailable (%s); using provider defaults.", exc)
        return None


class _ThinkTagRouter:
    """Split a token stream into answer text and reasoning text on the fly.

    Cleanly routes `<think>...</think>` blocks to the thinking channel,
    holding back only partial tag prefixes like `<th` until resolved.
    """

    def __init__(self):
        self._buffer = ""
        self._in_thinking = False

    def feed(self, text: str) -> list[tuple[str, str]]:
        """Return [(channel, text), …] where channel is 'token' or 'thinking'."""
        self._buffer += text
        out = []

        while True:
            match = _THINK_TAG_RE.search(self._buffer)
            if not match:
                break
            before = self._buffer[:match.start()]
            if before:
                out.append(("thinking" if self._in_thinking else "token", before))
            self._in_thinking = not match.group().startswith("</")
            self._buffer = self._buffer[match.end():]

        # Hold back trailing '<' that might be part of an incoming <think> or </think> tag
        cut = self._buffer.rfind("<")
        if cut != -1 and len(self._buffer) - cut <= 12:
            emit, self._buffer = self._buffer[:cut], self._buffer[cut:]
        else:
            emit, self._buffer = self._buffer, ""

        if emit:
            out.append(("thinking" if self._in_thinking else "token", emit))

        return out

    def flush(self) -> list[tuple[str, str]]:
        """Emit whatever is left once the stream is over."""
        if not self._buffer:
            return []
        channel = "thinking" if self._in_thinking else "token"
        out = [(channel, self._buffer)]
        self._buffer = ""
        return out


def _sse_send(handler, payload: dict) -> bool:
    """Write one SSE event. Works both on the legacy HTTP server (real socket)
    and on the FastAPI adapter, whose wfile pushes into the streaming queue.

    Returns False when the write failed, which on a stream means the reader is
    gone: the user pressed stop, closed the tab, or lost the network. That
    return value is the only signal the engine gets that it can stop; swallowing
    it, as this function used to, is what left generations running to the full
    token budget with nobody on the other end.
    """
    try:
        handler.wfile.write(f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8"))
        handler.wfile.flush()
        return True
    except Exception:
        return False


def _msgs_for_repair(messages, attempted_text):
    """The conversation plus the block that failed, asking for it again, clean."""
    return list(messages) + [
        {"role": "assistant", "content": attempted_text},
        {"role": "user", "content": (
            "Il blocco strumento che hai scritto non è JSON valido e non è stato "
            "eseguito. Riscrivi SOLO l'oggetto JSON della chiamata, senza testo "
            "attorno e senza recinto markdown."
        )},
    ]


def _repair_tool_calls(handler, messages, ai_cfg, model, provider, endpoint,
                       api_url, api_key, timeout, sampling, cancel):
    """
    One grammar-constrained retry of a malformed tool call.

    Returns the parsed calls, or None when nothing better could be produced --
    in which case the caller reports the original parse error, exactly as
    before. This is strictly an upgrade on the retry that already happened: the
    same generation, spent on an output that cannot be malformed.
    """
    try:
        from core.engine.grammars import grammar_for_available_tools
        from core.mcp.agent_loop import extract_tool_calls
        from core.ai_providers import call_ai_model_stream
    except Exception as exc:
        log.debug("Tool repair unavailable (%s)", exc)
        return None

    grammar = grammar_for_available_tools()
    if not grammar:
        return None

    # Short, cold and bounded: this is a transcription, not a decision.
    repair_params = sampling.with_grammar(grammar).with_overrides(
        temperature=0.0, max_tokens=512
    )

    try:
        pieces = []
        for chunk in call_ai_model_stream(
            messages, ai_cfg, model, provider, endpoint, api_url, api_key,
            0.0, 512, 1.0, timeout, params=repair_params, cancel=cancel,
        ):
            if chunk.get("error"):
                return None
            pieces.append(chunk.get("token", ""))
        raw = "".join(pieces).strip()
    except Exception as exc:
        log.debug("Tool repair generation failed: %s", exc)
        return None

    if not raw:
        return None

    # The grammar emits the bare object; extract_tool_calls wants the fence.
    calls = extract_tool_calls(f"```sigma-tool\n{raw}\n```")
    good = [c for c in calls if not c.get("parse_error")]
    if good:
        log.info("Chiamata strumento riparata con grammatica: %s",
                 ", ".join(c["tool"] for c in good))
        _sse_send(handler, {"model_status": "🔧 Chiamata strumento corretta..."})
        return good
    return None


class _TokenCoalescer:
    """
    Batches consecutive tokens on one channel into fewer SSE events.

    A write plus a flush per token is a syscall per token on the server, and on
    the client every event re-renders the whole message through markdown, KaTeX
    and Mermaid. At the ten tokens a second of a 27B nobody notices; the moment
    a small model runs at a hundred and fifty, the interface becomes the slowest
    part of the pipeline and the stream visibly stutters.

    Text is never reordered or dropped -- only grouped. The flush thresholds are
    chosen so the reader cannot perceive the grouping: a frame at 60Hz is 16ms,
    so a 25ms window is at most one frame of extra latency, and the character
    cap keeps a fast model from batching a whole paragraph into one repaint.
    """

    MAX_DELAY_SECONDS = 0.025
    MAX_CHARS = 48

    def __init__(self, emit):
        self._emit = emit
        self._channel = None
        self._buffer = ""
        self._opened_at = 0.0

    def feed(self, channel: str, text: str) -> None:
        if not text:
            return
        now = time.perf_counter()
        # A channel switch must flush: reasoning and answer land in different
        # bubbles, and merging them would put the thinking in the reply.
        if self._channel is not None and channel != self._channel:
            self.flush()
        if self._channel is None:
            self._channel = channel
            self._opened_at = now
        self._buffer += text
        if (len(self._buffer) >= self.MAX_CHARS
                or now - self._opened_at >= self.MAX_DELAY_SECONDS):
            self.flush()

    def flush(self) -> None:
        if self._buffer and self._channel is not None:
            channel, text = self._channel, self._buffer
            self._buffer = ""
            self._channel = None
            self._emit(channel, text)
        else:
            self._buffer = ""
            self._channel = None


def _preparing_status(model: str, bot_name: str) -> str:
    """
    What the engine is doing before the first token arrives.

    Separates the three situations the user experiences as one undifferentiated
    wait: the weights have to be brought into memory, another request is using
    the engine, or the model is resident and simply reading the prompt. Only
    the first is a load, and saying so on every turn taught the user to read
    every pause as one.
    """
    try:
        from core.engine import sigma_engine

        if sigma_engine._generation_waiting > 0:
            return "⏳ Motore occupato da un'altra richiesta, in coda..."
        if sigma_engine.has_resident_model:
            return f"📖 {bot_name} sta leggendo la conversazione..."
        return f"🧠 Caricamento di {model} in memoria..."
    except Exception:
        return f"🧠 Preparazione di {model}..."


def _detect_hardware_note(provider: str, model: str) -> str:
    """Return a concise, informative note about the hardware executing this model."""
    if provider in ["anthropic", "openai", "groq", "mistral", "deepseek", "gemini", "openrouter"]:
        return f"Cloud API ({provider.title()})"

    try:
        import torch
        if torch.cuda.is_available():
            count = torch.cuda.device_count()
            if count == 1:
                name = torch.cuda.get_device_name(0).replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
                total = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
                return f"{name} ({total}GB VRAM)"
            elif count > 1:
                parts = []
                for i in range(count):
                    name = torch.cuda.get_device_name(i).replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
                    total = round(torch.cuda.get_device_properties(i).total_memory / (1024**3), 0)
                    parts.append(f"{name} ({int(total)}GB)")
                return f"Dual GPU: {' + '.join(parts)}"
    except Exception:
        pass

    try:
        import psutil
        cpu_count = psutil.cpu_count(logical=True)
        ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
        return f"CPU ({cpu_count} threads, {ram_gb}GB RAM)"
    except Exception:
        return "Local Host"


def _stream_chat_response(handler, messages, ai_cfg, model, provider,
                          endpoint, api_url, api_key, temperature, max_tokens,
                          top_p, timeout, message, bot_name, manifesto_path,
                          allow_actions, agent_id=None, agent_role=None, agent_image=None,
                          routing_time_ms=None, hardware_note=None,
                          sampling=None, wants_reasoning=True):
    """Stream a chat completion as SSE, then run file extraction on the full text.

    `sampling` is the resolved SamplingParams for this turn; when None each
    provider falls back to the loose temperature/max_tokens/top_p triple.

    `wants_reasoning` decides whether a local model is asked to think before
    answering. It defaults to True so callers that predate the execution
    profiles behave as before.
    """
    import time
    from core.ai_providers import call_ai_model_stream

    cancel = _new_cancellation_token()

    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()

    resolved_agent_id = agent_id or (manifesto_path or "").replace("manifesti/", "").replace(".md", "") \
        or bot_name.lower().replace(" ", "_")

    hw_info = hardware_note or _detect_hardware_note(provider, model)

    # Sent before the first token so the client paints the agent bubble immediately.
    _sse_send(handler, {"meta": {
        "agent_id": resolved_agent_id,
        "agent_name": bot_name,
        "agent_role": agent_role or bot_name,
        "agent_image": agent_image or "/images/default.png",
        "manifesto_used": manifesto_path,
        "routing_time_ms": routing_time_ms,
        "hardware_note": hw_info,
        # Sent before the first token, so it has to describe what is actually
        # happening. It used to say "loading the model" on every request,
        # resident or not, which is why talking to a model already in VRAM felt
        # like waiting for it to load each time. The engine emits its own
        # notice when a load genuinely happens.
        "model_status": _preparing_status(model, bot_name),
    }})

    full_text = ""
    full_thinking = ""
    error_msg = None
    router = _ThinkTagRouter()
    tool_transcript = []           # what ran this turn, for the server log
    has_sent_thinking_status = False
    has_sent_generating_status = False
    t_call_start = time.perf_counter()
    t_first_token = None
    generated_token_count = 0
    calculated_tps = None
    load_duration_ms = None

    # ── Deterministic thinking prefill ──────────────────────────────────────
    # For local providers (Ollama / SigmaEngine) that don't natively separate
    # reasoning from text, we inject a partial assistant message that forces
    # the model to open a <think> block.  The model MUST continue from there,
    # so the _ThinkTagRouter receives clean XML tags with no heuristics needed.
    # Cloud providers (Anthropic, DeepSeek-Reasoner) already return a separate
    # `reasoning_content` field, so prefilling would corrupt their output.
    #
    # It is now conditional. Forcing it on every turn made "ciao" pay for a
    # reasoning block, and the cost is not only latency: a small model pushed
    # into a chain of thought it was never trained to produce answers worse,
    # not better. The execution profile decides -- code, mathematics and
    # analysis think; conversation, greetings and web summaries answer.
    _PREFILL_PROVIDERS = {"ollama", "sigma_engine", "sigma"}
    _prefill_injected = wants_reasoning and provider in _PREFILL_PROVIDERS
    if _prefill_injected:
        # Ollama continues generation from any partial assistant message
        messages = list(messages) + [{"role": "assistant", "content": "<think>\n"}]
        # Prime the router so it starts in thinking state immediately
        router._in_thinking = True

    def _push(payload: dict) -> None:
        """Send one event, and stop the generation if nobody received it."""
        if not _sse_send(handler, payload) and cancel is not None:
            cancel.cancel("client_disconnected")

    def _emit_status_text(text: str) -> None:
        """Forwards an engine status line to the client without metering it."""
        if not text:
            return
        _push({"token": text, "channel": "answer", "status": True})

    def _emit(channel: str, text: str) -> None:
        nonlocal full_text, full_thinking, has_sent_thinking_status, has_sent_generating_status, t_first_token, generated_token_count
        if not text:
            return
        if t_first_token is None:
            t_first_token = time.perf_counter()
        generated_token_count += max(1, len(text.split()))

        if channel == "thinking":
            if not has_sent_thinking_status:
                has_sent_thinking_status = True
                _push({"model_status": f"🧭 {bot_name}: Elaborazione e ragionamento profondo..."})
            full_thinking += text
            _push({"thinking": text})
        else:
            if not has_sent_generating_status:
                has_sent_generating_status = True
                _push({"model_status": f"✨ {bot_name} sta componendo la risposta..."})
            full_text += text
            _push({"token": text})

    # Everything the model produces goes through the coalescer; status lines
    # and metrics bypass it, because they are single events that must land the
    # moment they happen.
    coalescer = _TokenCoalescer(_emit)

    def _run_model_turn(turn_messages=None) -> bool:
        """One pass of the model over `messages`. False if it errored out."""
        nonlocal error_msg, calculated_tps, generated_token_count, t_first_token, load_duration_ms
        _msgs = turn_messages if turn_messages is not None else messages
        try:
            for chunk in call_ai_model_stream(
                _msgs, ai_cfg, model, provider, endpoint, api_url, api_key,
                temperature, max_tokens, top_p, timeout,
                params=sampling, cancel=cancel,
            ):
                if cancel is not None and cancel.cancelled:
                    return False
                if chunk.get("error"):
                    error_msg = chunk.get("message", "Errore sconosciuto")
                    return False
                # Native reasoning channel: already separated by the provider.
                coalescer.feed("thinking", chunk.get("thinking", ""))
                # Status notices (model loading, placement summary) are shown
                # but never timed or counted as generated words.
                if chunk.get("status"):
                    coalescer.flush()
                    if chunk.get("load_duration_ms"):
                        load_duration_ms = chunk.get("load_duration_ms")
                    if chunk.get("model_status"):
                        _sse_send(handler, {
                            "model_status": chunk.get("model_status"),
                            "meta": {"load_duration_ms": load_duration_ms}
                        })
                    if chunk.get("token"):
                        _emit_status_text(chunk.get("token"))
                    continue

                # Answer channel: may still carry inline <think> blocks.
                for channel, text in router.feed(chunk.get("token", "")):
                    coalescer.feed(channel, text)
                if chunk.get("done"):
                    for channel, text in router.flush():
                        coalescer.feed(channel, text)
                    coalescer.flush()

                    # Prefer whatever the runtime measured. SigmaEngine reports
                    # speed_tok_s from real decoded tokens; Ollama reports
                    # tokens_per_second. Recomputing from a word count here
                    # would replace a true number with an estimate that is off
                    # by the tokenizer's words-per-token ratio.
                    tps = chunk.get("speed_tok_s") or chunk.get("tokens_per_second")
                    if tps:
                        calculated_tps = tps
                    elif t_first_token:
                        gen_sec = time.perf_counter() - t_first_token
                        if gen_sec > 0:
                            calculated_tps = round(generated_token_count / gen_sec, 1)

                    raw_load = chunk.get("load_duration")
                    if raw_load:
                        load_duration_ms = round(raw_load / 1e6, 1)
                    elif t_first_token:
                        load_duration_ms = round((t_first_token - t_call_start) * 1000, 1)

                    # The engine reports real token counts; the word-split
                    # tally here is only a fallback for providers that don't.
                    reported_tokens = (
                        chunk.get("eval_count")
                        or chunk.get("total_tokens")
                        or generated_token_count
                    )

                    coalescer.flush()

                    # Forwarded so the client can trigger auto-continuation on truncation.
                    _push({
                        "done_reason": chunk.get("done_reason", "stop"),
                        "truncated": chunk.get("truncated", False),
                        "metrics": {
                            "routing_time_ms": routing_time_ms,
                            "load_duration_ms": load_duration_ms,
                            "tokens_per_second": calculated_tps,
                            "token_count": reported_tokens,
                            "hardware_note": hw_info,
                            "sampling": chunk.get("sampling"),
                        }
                    })
                    return True
            return True
        except Exception as exc:
            log.error("Streaming chat failed: %s", exc, exc_info=True)
            error_msg = str(exc)
            return False

    _run_model_turn(messages)

    # --- Abandoned request ---------------------------------------------------
    # Nobody is reading this stream any more. Running MCP tools or writing
    # files on behalf of an answer the user cancelled is worse than useless:
    # those act on the world, and the user asked for the turn to stop.
    if cancel is not None and cancel.cancelled:
        log.info(
            "Chat stream cancelled (%s) after %d words for '%s'",
            cancel.reason, generated_token_count, model,
        )
        return

    # --- MCP tool loop -------------------------------------------------------
    # The model asks for a tool by writing a fenced block; it is run here and the
    # outcome handed back so the answer can continue with real data. A tool that
    # acts on the world stops the turn and waits for the operator instead.
    if not error_msg:
        try:
            from core.mcp.agent_loop import (MAX_TOOL_ROUNDS, execute_calls,
                                             extract_tool_calls, format_results_for_model)

            for _round in range(MAX_TOOL_ROUNDS):
                calls = extract_tool_calls(full_text)
                if not calls:
                    break

                # A block the model got syntactically wrong is worth one
                # constrained retry before it is reported as a failure. The
                # grammar makes malformed JSON and invented tool names
                # unreachable rather than merely discouraged, so the retry
                # cannot come back wrong in the same way -- unlike the plain
                # re-ask, which costs the same generation and often does.
                malformed = [c for c in calls if c.get("parse_error")]
                if malformed and sampling is not None:
                    repaired = _repair_tool_calls(
                        handler, _msgs_for_repair(messages, full_text),
                        ai_cfg, model, provider, endpoint, api_url, api_key,
                        timeout, sampling, cancel,
                    )
                    if repaired:
                        calls = repaired

                _sse_send(handler, {"model_status": f"⚙️ Eseguo {len(calls)} strumento/i MCP..."})
                outcomes, approvals = execute_calls(calls)

                for outcome in outcomes:
                    tool_transcript.append(outcome)
                    _sse_send(handler, {"tool_result": outcome})

                if approvals:
                    # Nothing more runs this turn: the client shows the request,
                    # and resumes through /api/mcp/approve once the user decides.
                    for approval in approvals:
                        _sse_send(handler, {"tool_approval": approval})
                    break

                if not outcomes:
                    break

                next_messages = list(messages) + [
                    {"role": "assistant", "content": full_text},
                    {"role": "user", "content": format_results_for_model(outcomes)},
                ]
                # Re-apply prefill for local providers on each tool continuation turn
                if _prefill_injected:
                    next_messages = next_messages + [{"role": "assistant", "content": "<think>\n"}]
                # Nothing may straddle the reset: buffered text belongs to the
                # answer that just ended, not to the continuation.
                coalescer.flush()
                full_text = ""
                router = _ThinkTagRouter()
                if _prefill_injected:
                    router._in_thinking = True
                if not _run_model_turn(next_messages):
                    break
        except Exception as exc:
            log.error("MCP tool loop failed: %s", exc, exc_info=True)
            _sse_send(handler, {"tool_result": {
                "tool": "(hub MCP)", "ok": False,
                "output": f"Ciclo strumenti interrotto: {exc}",
            }})

    # A tool continuation can be cancelled too, and the same rule holds: do not
    # write files for an answer the user stopped.
    if cancel is not None and cancel.cancelled:
        log.info("Chat stream cancelled (%s) during the tool loop", cancel.reason)
        return

    if error_msg:
        _sse_send(handler, {"error": error_msg, "token": f"\n\n⚠️ **Errore:** {error_msg}"})
    else:
        for channel, text in router.flush():
            coalescer.feed(channel, text)
        coalescer.flush()

        # The call blocks were the agent's instructions to the hub, not prose:
        # the user sees what the tools did, not the JSON that asked for it.
        try:
            from core.mcp.agent_loop import strip_tool_blocks
            full_text = strip_tool_blocks(full_text)
        except Exception:
            pass

        # Second pass for reasoning shapes no tag can catch (bullet monologues,
        # "done thinking." markers, English self-analysis preambles).
        clean_text, extracted_thinking = _clean_all_tags(full_text)
        thinking_out = "\n\n".join(t for t in (full_thinking, extracted_thinking) if t and t.strip())

        # A reasoning-only answer is still an answer: don't leave the bubble empty.
        if not clean_text.strip() and thinking_out.strip():
            clean_text, thinking_out = thinking_out, ""

        created_files, actions_log = [], []
        if allow_actions and clean_text:
            try:
                created_files, actions_log = _extract_and_create_files_from_text(
                    clean_text, prompt_topic=message
                )
                if created_files:
                    # The cached tree is now a turn behind what is on disk.
                    invalidate_filesystem_context()
            except Exception as exc:
                log.error("Post-stream file extraction failed: %s", exc, exc_info=True)

        final_content = _format_response(clean_text)
        if created_files:
            final_content = _format_conversational_summary(final_content, created_files)

        _sse_send(handler, {
            "final_content": final_content,
            "final_thinking": thinking_out,
            "created_files": created_files,
            "actions_log": actions_log,
            "metrics": {
                "routing_time_ms": routing_time_ms,
                "load_duration_ms": load_duration_ms,
                "tokens_per_second": calculated_tps,
                "token_count": generated_token_count,
                "hardware_note": hw_info
            }
        })

    try:
        handler.wfile.write(b"data: [DONE]\n\n")
        handler.wfile.flush()
    except Exception:
        pass


def _try_fast_web_search(message: str):
    """Riconosce richieste di ricerca web/YouTube e le esegue senza passare dal modello.

    Il modello piccolo (qwen3.5:0.8b) spiega come usare search_web invece di
    chiamarlo. Per le ricerche non c'è ambiguità — l'intento è sempre chiaro
    — quindi saltiamo il LLM e andiamo direttamente su DuckDuckGo/YouTube.
    """
    import re
    from core.chat.web_search import _perform_web_search

    m = message.strip()
    ml = m.lower()

    # Patterns that signal a search intent (not a conversation)
    search_patterns = [
        r"\b(?:cerca|cercami|search|trova|trovami|fammi una ricerca|fai una ricerca)\b",
        r"\b(?:cerca su|cercami su|search on|find on)\b",
        r"\b(?:video(?: di| su)? )youtube\b",
        r"\b(?:apri|visit|go to|vai a|naviga)\s+(?:il sito\s+)?(?:https?://|www\.)",
    ]
    is_search = any(re.search(p, ml) for p in search_patterns)
    # "cerca su youtube" or "video youtube" explicitly
    is_youtube = bool(re.search(r"youtube", ml)) or bool(re.search(r"\bvideo\b", ml))
    # Explicit URL
    url_match = re.search(r"(https?://[^\s]+)", m)

    if not is_search and not is_youtube and not url_match:
        return None

    # Extract the actual query — strip the command words
    query = m
    for prefix in ["cerca su ", "cercami su ", "cerca ", "cercami ", "search on ", "search for ", "search ", 
                    "trova ", "trovami ", "find ", "fammi una ricerca su ", "fammi una ricerca ",
                    "fai una ricerca su ", "fai una ricerca "]:
        if ml.startswith(prefix):
            query = m[len(prefix):]
            break

    if not query.strip():
        return None

    log.info("Fast web search for: %s", query)
    
    try:
        results = _perform_web_search(query)
    except Exception as exc:
        return {"response": f"🔍 Ricerca web fallita: {exc}", "thinking": "", "actions_log": [],
                "created_files": [], "error": str(exc)}

    if not results:
        return {"response": f"🔍 Nessun risultato trovato per '{query}'.", "thinking": "",
                "actions_log": [], "created_files": [], "error": None}

    # Format a nice response
    lines = [f"### 🔍 Risultati per: {query}\n"]
    for i, r in enumerate(results[:5], 1):
        title = r.get("title", "Link")
        href = r.get("href", "")
        body = r.get("body", "")
        if href:
            lines.append(f"**{i}. [{title}]({href})**")
        else:
            lines.append(f"**{i}. {title}**")
        if body:
            lines.append(f"> {body[:300]}")
        lines.append("")
    
    response = "\n".join(lines)
    return {"response": response, "thinking": f"Ricerca web eseguita direttamente per: {query}",
            "actions_log": [], "created_files": [], "error": None}


def _try_fast_command(message: str):
    """Esegue un comando domestico diretto, o None se la frase va all'agente.

    La risposta ha la stessa forma di quella dell'agente, così il client non
    deve sapere quale delle due strade è stata presa.
    """
    try:
        from core.mcp import mcp_hub
        from core.mcp.fast_intents import match_home_command

        intent = match_home_command(message)
        if not intent:
            return None

        started = time.monotonic()
        outcome = mcp_hub.execute_tool(intent["tool"], intent["arguments"])
        elapsed = (time.monotonic() - started) * 1000

        base = {
            "thinking": "", "created_files": [], "actions_log": [], "error": None,
            "manifesto_used": "sigma_home", "agent_name": "Sigma Home",
            "agent_id": "sigma_home",
        }

        if outcome["status"] == "confirmation_required":
            # Il cancello vale anche qui: la corsia veloce accorcia il percorso
            # fino alla chiamata, non salta l'assenso di chi deve darlo.
            return {**base,
                    "response": f"{intent['summary']}.",
                    "tool_approvals": [outcome["approval"]]}

        if outcome["status"] == "error":
            log.info("Corsia veloce fallita su '%s': %s", intent["tool"], outcome["error"])
            return None                       # l'agente ci riprova ragionandoci

        content = outcome["result"].get("content", [])
        text = "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
        log.info("Corsia veloce: %s in %.0f ms", intent["tool"], elapsed)
        return {**base,
                "response": f"✅ {intent['summary']}.",
                "tool_calls": [{"tool": intent["tool"], "ok": True,
                                "server": "HomeAssistant MCP", "output": text}]}
    except Exception as exc:
        log.warning("Corsia veloce non disponibile: %s", exc)
        return None


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
        allow_actions = req.get("allow_actions", False)
        planning_mode = req.get("planning_mode", False)

        msg_lower = message.lower().strip()

        _delete_keywords = ["elimina", "cancella", "rimuovi", "delete", "remove"]
        is_deletion = any(re.search(rf"\b{re.escape(w)}\b", msg_lower) for w in _delete_keywords)
        
        if is_deletion:
            log.info("Deterministic Deletion Request detected for prompt: %s", message)

            raw_target = re.sub(
                r"^(?:elimina|cancella|rimuovi|delete|remove)\s+(?:l[\'\"]|il|lo|la|i|gli|le)?\s*(?:argomento|topic|modulo|file|cartella)?\s*(?:di|su)?\s*",
                "", msg_lower, flags=re.IGNORECASE
            ).strip()
            target_slug = re.sub(r'[^a-zA-Z0-9_]+', '_', raw_target).strip('_')

            deleted_paths = []
            if target_slug:
                possible_topic = os.path.join("data", target_slug)
                if os.path.exists(possible_topic):
                    try:
                        shutil.rmtree(possible_topic)
                        deleted_paths.append(possible_topic.replace('\\', '/'))
                    except Exception as e:
                        log.error("Failed to delete topic folder %s: %s", possible_topic, e)
                
                if not deleted_paths and os.path.exists("data"):
                    for entry in os.listdir("data"):
                        if entry.lower() == target_slug or target_slug in entry.lower():
                            full_p = os.path.join("data", entry)
                            try:
                                if os.path.isdir(full_p):
                                    shutil.rmtree(full_p)
                                else:
                                    os.remove(full_p)
                                deleted_paths.append(full_p.replace('\\', '/'))
                            except Exception as e:
                                log.error("Failed to delete %s: %s", full_p, e)

            if deleted_paths:
                rebuild_modules_meta()
                del_msg = f"🗑️ **Eliminazione completata su disco:**\n" + "\n".join([f"- Eliminata cartella/file `{p}`" for p in deleted_paths])
                actions_log = [{"type": "delete_file", "success": True, "path": p, "message": f"Eliminato {p}"} for p in deleted_paths]
                return self.send_json_response({
                    "response": del_msg,
                    "thinking": f"Richiesta di eliminazione eseguita con successo per: {raw_target}",
                    "actions_log": actions_log,
                    "created_files": [],
                    "error": None,
                    "manifesto_used": "sigma_architect",
                    "agent_name": "Sigma AI Architect",
                    "agent_id": "sigma_architect"
                })
            else:
                return self.send_json_response({
                    "response": f"⚠️ **Nessun elemento trovato:** Non è stato trovato alcun argomento o file corrispondente a `{raw_target or message}` nella cartella `data/`.",
                    "thinking": f"Impossibile trovare il target di eliminazione: {raw_target}",
                    "actions_log": [],
                    "created_files": [],
                    "error": "Elemento non trovato",
                    "manifesto_used": "sigma_architect",
                    "agent_name": "Sigma AI Architect",
                    "agent_id": "sigma_architect"
                })

        # --- corsia veloce per ricerche web ---------------------------------
        # "Cerca su YouTube Bocca di Rosa" non serve il LLM: sappiamo già che
        # è una ricerca. Saltiamo il modello, chiamiamo DuckDuckGo/YouTube
        # direttamente, e restituiamo i risultati formattati.
        if allow_actions and not planning_mode:
            fast_web = _try_fast_web_search(message)
            if fast_web is not None:
                return self.send_json_response(fast_web)

        # --- corsia veloce per i comandi domestici diretti --------------------
        # "Spegni le luci dell'ufficio" non ha bisogno di un giro di modello:
        # il riconoscitore lo traduce in una chiamata e si arrende al primo
        # dubbio, così tutto ciò che richiede davvero di ragionare prosegue
        # verso l'agente completo poche righe più sotto.
        if allow_actions and not planning_mode:
            fast = _try_fast_command(message)
            if fast is not None:
                return self.send_json_response(fast)

        import time
        t_req_start = time.perf_counter()

        ai_cfg = load_ai_config()
        active_provider = ai_cfg.get("active_provider", "ollama")
        model = model_override or ai_cfg.get("active_model") or ai_cfg.get("model") or ""

        if not model:
            prov_cfg = ai_cfg.get("providers", {}).get(active_provider, {})
            model = prov_cfg.get("model") or "llama3.2"

        requested_provider = req.get("model_provider")
        if requested_provider and requested_provider in ai_cfg.get("providers", {}):
            active_provider = requested_provider
            active_prov_cfg = ai_cfg.get("providers", {})[requested_provider]
        else:
            detected_provider, detected_prov = resolve_provider_config(ai_cfg, model)
            if detected_prov:
                active_provider = detected_provider
                active_prov_cfg = detected_prov
            else:
                active_prov_cfg = ai_cfg.get("providers", {}).get(active_provider, {})

        hardware_note = _detect_hardware_note(active_provider, model)

        # Resolve dynamic manifesto if in auto mode or empty
        if not manifesto_path or manifesto_path == "auto" or manifesto_path == "manifesti/auto.md":
            manifesto_path = _determine_agent_by_request(message, ai_cfg, model)

        t_routing_end = time.perf_counter()
        routing_time_ms = round((t_routing_end - t_req_start) * 1000, 1)

        # Resolve real agent details from manifesto_path
        real_agent_name = "Sigma Assistant"
        real_agent_role = "Assistente Front-Desk"
        real_agent_image = "/images/default.png"
        agent_id = "sigma_assistant"

        if manifesto_path:
            agent_id = os.path.basename(manifesto_path).replace(".md", "")
            if os.path.exists(manifesto_path):
                fname = os.path.basename(manifesto_path)
                try:
                    from core.data_handler import _parse_manifesto_file
                    from core.agent_registry import load_agents_meta
                    meta = load_agents_meta()
                    parsed = _parse_manifesto_file(manifesto_path, fname, meta, meta.get("manifesto_images", {}))
                    real_agent_name = parsed.get("name", agent_id.replace("_", " ").title())
                    real_agent_role = parsed.get("role", real_agent_name)
                    real_agent_image = parsed.get("image", "/images/default.png")
                except Exception as e:
                    log.debug("Manifesto metadata extraction error: %s", e)
            else:
                real_agent_name = agent_id.replace("_", " ").title()
                real_agent_role = real_agent_name

        bot_name = real_agent_name

        # ── Execution profile ────────────────────────────────────────────────
        # detect_execution_profile and apply_execution_profile have existed and
        # been imported at the top of this file for a long time without ever
        # being called: sampling came straight off the provider config, so
        # "ciao" was planned exactly like a proof. The profile now decides two
        # things -- the sampler for this turn, and whether the model is asked
        # to think before answering.
        profile_key = detect_execution_profile(message)
        profile = EXECUTION_PROFILES.get(profile_key, {})
        wants_reasoning = bool(profile.get("reasoning", True))
        sampling = _resolve_sampling(
            model, active_provider, active_prov_cfg, profile, wants_reasoning
        )
        log.info(
            "Profilo '%s' (reasoning=%s) | %s",
            profile_key, wants_reasoning,
            sampling.summary() if sampling else "sampler: provider defaults",
        )


        system_prompt = _get_manifesto_content(manifesto_path)

        user_name = req.get('user_name') or req.get('user_profile', {}).get('name')
        user_title = req.get('user_title') or req.get('user_profile', {}).get('title')
        identity_header = _build_agent_identity_header(user_name, user_title)

        # ── Stable prefix / volatile tail ────────────────────────────────────
        # Everything the model reads used to be rebuilt into one system message
        # per turn, clock included. Both local runtimes reuse the KV cache of
        # the longest token prefix shared with the previous call, so a system
        # block whose first lines change every minute invalidates the cache at
        # token zero: the whole prompt is prefilled again on every message, and
        # the cost grows with the conversation.
        #
        # So the message is split by lifetime, not by topic. What is identical
        # from one turn to the next -- who the agent is, its manifesto, the
        # tool catalogue, the file-writing rules -- stays in the system message
        # and is prefilled once. What changes -- the clock, the knowledge-base
        # tree, retrieved memories -- rides with the final user turn, after the
        # history, where it costs its own tokens and nothing else's.
        mcp_tools_catalogue = ""
        retrieved_memory = ""
        try:
            from core.mcp import mcp_hub

            # Memory MCP retrieval depends on the question, so it is volatile.
            mem_server = mcp_hub.get_server("Memory MCP")
            if mem_server and message:
                rag_res = mem_server.call_tool("query_vector_db", {"query": message, "limit": 3})
                if rag_res and not rag_res.get("isError"):
                    retrieved_memory = (
                        "## 🧠 CONTESTO RECUPERATO DA MEMORY MCP:\n"
                        + json.dumps(rag_res.get("results", []), indent=2)
                        + "\n"
                    )

            # The callable tool catalogue only changes when the operator turns a
            # server on or off, so it belongs in the cacheable prefix.
            # Only what is switched on and actually reachable: listing a tool the
            # hub would refuse just sends the agent into a wall.
            from core.mcp.agent_loop import build_tools_prompt
            mcp_tools_catalogue = build_tools_prompt(mcp_hub.get_agent_tools())
        except Exception as mcp_err:
            log.debug("MCP Hub chat pipeline enrichment skipped: %s", mcp_err)

        # The knowledge-base tree belongs in the cacheable prefix. It was moved
        # into the per-turn tail on the theory that it changes; measured, it
        # changes only when the user creates or deletes something, while its
        # ~240 tokens sat at precisely the point where prefix reuse stops. A
        # tree that does change costs one invalidation, which is the right
        # price paid once rather than a fraction of it paid forever.
        fs_context = _build_filesystem_context()
        project_structure = (
            f"\n## STRUTTURA PROGETTO\n{fs_context}\n" if fs_context else ""
        )
        # The date, not the clock: see _get_date_context. Stable for a day, so
        # it belongs here rather than in the tail.
        today = _get_date_context()

        full_prompt = f"""{identity_header}

{system_prompt}{mcp_tools_catalogue}{project_structure}
{today}

## ISTRUZIONI CREAZIONE E SALVATAGGIO FILE SU DISCO
1. Quando l'utente ti chiede di creare, scrivere o generare un file per un Argomento, DEVI SEMPRE specificare il percorso relativo esplicito collegandolo DIRETTAMENTE all'argomento (es. `data/ARGOMENTO/NOME_FILE.md`) e racchiudere il contenuto completo all'interno di un blocco di codice markdown:

Path: `data/ARGOMENTO/NOME_FILE.md`
```markdown
# Titolo del Documento
Contenuto completo...
```

2. REGOLE FONDAMENTALI STRUTTURA A NODI:
   - I file appartengono direttamente al nodo dell'Argomento (es. `data/analisi_1/teoria.md`, `data/analisi_1/grafico.html`).
   - MAI creare un sottoargomento con lo stesso nome dell'argomento padre (es. NON creare mai `data/analisi_1/01_analisi_1`).
   - Sottoargomenti distinti sono permessi SOLO se suddividono un argomento in sotto-concetti specifici e separati (es. `data/analisi_1/insiemi_numerici/spiegazione.md`).
"""

        # Extract and sanitize past chat history context
        raw_history = req.get("history") or req.get("context", {}).get("history", []) or req.get("messages", [])
        history_messages = []
        if isinstance(raw_history, list):
            for h in raw_history:
                if isinstance(h, dict):
                    role = h.get("role", "")
                    content = h.get("content", "")
                    if role in ["user", "assistant"] and content:
                        clean_content = _sanitize_history_message(content)
                        if clean_content:
                            history_messages.append({"role": role, "content": clean_content})

        messages = [{"role": "system", "content": full_prompt}]

        # Drop a user turn the frontend already appended to the history, before
        # measuring: counting a duplicate against the budget evicts a real turn.
        candidate_history = [
            h for h in history_messages
            if not (h.get("role") == "user" and h.get("content") == message)
        ]

        # The volatile block, and then the question. The question stays last:
        # it is what the model must answer, and burying it under a directory
        # listing is how an assistant ends up describing the listing.
        # What genuinely cannot be cached, and nothing else. The clock is
        # fifteen tokens; retrieved memories depend on the question. The
        # knowledge-base tree used to be here too, and measured at ~240 tokens
        # it was the single largest thing being re-prefilled on every message,
        # sitting exactly at the point where the KV cache stops matching. It
        # now lives in the stable prefix above.
        volatile_parts = []
        if needs_precise_time(message):
            volatile_parts.append(_get_time_context())
        if retrieved_memory:
            volatile_parts.append(retrieved_memory)

        # Open workspace context files
        context_files = req.get("context", {}).get("open_files", [])
        if context_files:
            ctx_str = _collect_context_files(self, context_files)
            if ctx_str:
                volatile_parts.append(f"## 📂 FILE APERTI NEL WORKSPACE:\n{ctx_str}")

        # Attached PC files
        uploaded_files = req.get("uploaded_files", [])
        if uploaded_files:
            for uf in uploaded_files:
                if isinstance(uf, dict):
                    fname = uf.get("filename", "allegato")
                    fcontent = uf.get("content", "")
                    if fcontent:
                        volatile_parts.append(f"## 📎 FILE ALLEGATO DALL'UTENTE: {fname}\n```\n{fcontent[:35000]}\n```")

        volatile_context = "\n\n".join(volatile_parts)
        final_user_turn = (
            f"{volatile_context}\n\n---\n\n{message}"
            if volatile_context else message
        )

        # ── History and Prompt Budgeting, measured rather than counted ────────
        # The window has to hold the system prompt, the volatile block, the
        # question and the answer. History gets what is left, and is trimmed
        # from the oldest end with the model's own tokenizer where there is one.
        tokenizer = resident_tokenizer()
        ctx_window = _engine_context_window()
        max_prompt_budget = max(ctx_window - 256, 512)

        # Truncate volatile context or system prompt if it alone exceeds the budget
        fixed_tokens = (
            estimate_tokens(full_prompt, tokenizer)
            + estimate_tokens(final_user_turn, tokenizer)
        )
        if fixed_tokens > max_prompt_budget:
            # Step 1: trim volatile parts (attached files / workspace context)
            if volatile_parts:
                final_user_turn = message
                fixed_tokens = estimate_tokens(full_prompt, tokenizer) + estimate_tokens(final_user_turn, tokenizer)

            # Step 2: trim project structure from full_prompt if still overflowing
            if fixed_tokens > max_prompt_budget and project_structure:
                project_structure = ""
                full_prompt = f"{identity_header}\n\n{system_prompt}{mcp_tools_catalogue}\n{today}\n"
                messages[0]["content"] = full_prompt
                fixed_tokens = estimate_tokens(full_prompt, tokenizer) + estimate_tokens(final_user_turn, tokenizer)

            # Step 3: trim MCP catalogue if still overflowing
            if fixed_tokens > max_prompt_budget and mcp_tools_catalogue:
                mcp_tools_catalogue = ""
                full_prompt = f"{identity_header}\n\n{system_prompt}\n{today}\n"
                messages[0]["content"] = full_prompt
                fixed_tokens = estimate_tokens(full_prompt, tokenizer) + estimate_tokens(final_user_turn, tokenizer)

            # Step 4: hard clamp user message if still overflowing
            if fixed_tokens > max_prompt_budget:
                chars_avail = max(max_prompt_budget * 3, 500)
                final_user_turn = final_user_turn[:chars_avail]
                full_prompt = full_prompt[:chars_avail]
                messages[0]["content"] = full_prompt

        budget = history_budget(
            context_window=ctx_window,
            fixed_tokens=fixed_tokens,
            reserve_for_answer=int(profile.get("max_tokens") or 4096),
        )
        recent_history, history_report = trim_history(
            candidate_history, budget, tokenizer=tokenizer
        )
        messages.extend(recent_history)

        notice = dropped_notice(history_report)
        if notice:
            final_user_turn = f"{notice}\n\n{final_user_turn}"

        if not messages or messages[-1].get("content") != final_user_turn:
            messages.append({"role": "user", "content": final_user_turn})

        log.debug(
            "Contesto: %d fissi + %d storia (%d/%d messaggi) su finestra %d, "
            "riserva risposta %d",
            fixed_tokens, history_report["tokens"], history_report["kept"],
            history_report["kept"] + history_report["dropped"],
            ctx_window, int(profile.get("max_tokens") or 4096),
        )

        prov_endpoint = active_prov_cfg.get("endpoint", "http://localhost:11434/api/chat")
        prov_api_url = active_prov_cfg.get("api_url") or active_prov_cfg.get("endpoint", "")
        prov_api_key = active_prov_cfg.get("api_key", "")
        prov_timeout = req.get("timeout") or active_prov_cfg.get("timeout", 300)

        # The loose triple the non-streaming providers still take. It now comes
        # from the resolved sampler rather than raw config, so the JSON path and
        # the SSE path answer with the same settings.
        if sampling is not None:
            prov_temperature = sampling.temperature
            prov_max_tokens = sampling.max_tokens
            prov_top_p = sampling.top_p
        else:
            tuned_cfg = apply_execution_profile(profile_key, active_prov_cfg)
            prov_temperature = tuned_cfg.get("temperature", 0.7)
            prov_max_tokens = tuned_cfg.get("max_tokens", 4096)
            prov_top_p = tuned_cfg.get("top_p", 0.9)

        # Token-by-token SSE: the user reads the answer as it is produced instead of
        # waiting for the whole generation. Planning mode stays on the JSON path
        # because the frontend needs the complete plan object before rendering it.
        if req.get("stream") and not planning_mode:
            return _stream_chat_response(
                self, messages, ai_cfg, model, active_provider,
                prov_endpoint, prov_api_url, prov_api_key,
                prov_temperature, prov_max_tokens, prov_top_p, prov_timeout,
                message=message, bot_name=bot_name,
                manifesto_path=manifesto_path, allow_actions=allow_actions,
                agent_id=agent_id, agent_role=real_agent_role, agent_image=real_agent_image,
                routing_time_ms=routing_time_ms, hardware_note=hardware_note,
                sampling=sampling, wants_reasoning=wants_reasoning,
            )

        if active_provider in ("sigma_engine", "sigma"):
            # The native engine runs in this process; it has no HTTP endpoint to
            # call. Falling through to the generic branch sent the request to
            # the sigma_engine provider's nominal URL -- this very server's
            # /api/engine, which does not exist -- so every non-streaming turn
            # on a local model answered "API error 404" instead of running it.
            from core.ai_providers import call_ai_model
            ai_response, thinking, err = call_ai_model(
                messages, ai_cfg, model, active_provider,
                prov_endpoint, prov_api_url, prov_api_key,
                prov_temperature, prov_max_tokens, prov_top_p, prov_timeout,
            )
        elif active_provider == "ollama":
            ai_response, thinking, err = call_ollama(
                messages, model,
                endpoint=prov_endpoint,
                temperature=prov_temperature,
                max_tokens=prov_max_tokens,
                top_p=prov_top_p,
                timeout=prov_timeout
            )
        elif active_provider == "anthropic":
            ai_response, thinking, err = call_anthropic(
                messages, model,
                api_key=prov_api_key,
                temperature=prov_temperature,
                max_tokens=prov_max_tokens,
                timeout=prov_timeout
            )
        else:
            ai_response, thinking, err = call_openai_compatible(
                messages, model,
                api_url=prov_api_url,
                api_key=prov_api_key,
                temperature=prov_temperature,
                max_tokens=prov_max_tokens,
                top_p=prov_top_p,
                timeout=prov_timeout
            )

        if err:
            return self.send_json_response({"error": err}, 500)

        created_files = []
        actions_log = []
        if allow_actions and ai_response:
            created_files, actions_log = _extract_and_create_files_from_text(ai_response, prompt_topic=message)
            if created_files:
                invalidate_filesystem_context()

        formatted_res = _format_response(ai_response)
        if created_files:
            formatted_res = _format_conversational_summary(formatted_res, created_files)

        # Resolve real agent details from manifesto_used
        real_agent_name = bot_name
        real_agent_role = ""
        real_agent_image = "/images/default.png"
        if manifesto_path and os.path.exists(manifesto_path):
            fname = os.path.basename(manifesto_path)
            try:
                from core.data_handler import _parse_manifesto_file
                from core.agent_registry import load_agents_meta
                meta = load_agents_meta()
                parsed = _parse_manifesto_file(manifesto_path, fname, meta, meta.get("manifesto_images", {}))
                real_agent_name = parsed.get("name", bot_name)
                real_agent_role = parsed.get("role", "")
                real_agent_image = parsed.get("image", "/images/default.png")
            except Exception as e:
                log.debug("Manifesto metadata extraction error: %s", e)

        return self.send_json_response({
            "response": formatted_res,
            "thinking": thinking or "",
            "actions_log": actions_log,
            "created_files": created_files,
            "error": None,
            "manifesto_used": manifesto_path,
            "agent_name": real_agent_name,
            "agent_role": real_agent_role,
            "agent_image": real_agent_image,
            "agent_id": agent_id,
            "routing_time_ms": routing_time_ms,
            "hardware_note": hardware_note,
            "metrics": {
                "routing_time_ms": routing_time_ms,
                "hardware_note": hardware_note
            }
        })

    except Exception as exc:
        log.error("Unhandled error in handle_chat: %s", exc, exc_info=True)
        return self.send_json_response({"error": str(exc)}, 500)


def handle_chat_extract_files(self):
    """POST /api/chat/extract_files — Extract and save files from completed chat response text."""
    try:
        req = self.read_json_body()
        text = req.get("text", "").strip()
        prompt_topic = req.get("prompt_topic", "").strip()
        if not text:
            return self.send_json_response({"created_files": [], "actions_log": []})

        created_files, actions_log = _extract_and_create_files_from_text(text, prompt_topic=prompt_topic)
        return self.send_json_response({
            "success": True,
            "created_files": created_files,
            "actions_log": actions_log
        })
    except Exception as exc:
        log.error("handle_chat_extract_files error: %s", exc, exc_info=True)
        return self.send_json_response({"error": str(exc)}, 500)
