"""Agent Memory for Sigma Studio — Memoria persistente per agenti AI.
Permette agli agenti di ricordare esperienze passate, decisioni e pattern appresi."""
import os
import json
import datetime

AGENT_MEMORY_DIR = "agent_memory"
MAX_MEMORY_ENTRIES = 50  # Max entries per agent per memory type


def _ensure_memory_dir(agent_id: str) -> str:
    """Ensure memory directory exists for an agent."""
    agent_dir = os.path.join(AGENT_MEMORY_DIR, agent_id)
    os.makedirs(agent_dir, exist_ok=True)
    return agent_dir


def _get_memory_path(agent_id: str, memory_type: str) -> str:
    """Get path for a specific memory type file."""
    agent_dir = _ensure_memory_dir(agent_id)
    return os.path.join(agent_dir, f"{memory_type}.json")


def load_memory(agent_id: str, memory_type: str = "episodic") -> list:
    """Load memory entries for an agent.

    Memory types:
        - long_term: Conoscenza cumulativa (facts learned)
        - episodic: Cronologia sessioni (what happened when)
        - decisions: Decisioni passate con contesto
        - learned_patterns: Pattern appresi dall'esperienza

    Returns:
        List of memory entries, most recent first.
    """
    path = _get_memory_path(agent_id, memory_type)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            entries = json.load(f)
        return sorted(entries, key=lambda x: x.get("timestamp", ""), reverse=True)
    except Exception:
        return []


def save_memory_entry(agent_id: str, memory_type: str, entry: dict) -> bool:
    """Save a new memory entry for an agent.

    Args:
        agent_id: Agent identifier
        memory_type: Type of memory (long_term, episodic, decisions, learned_patterns)
        entry: Dict with at minimum a 'content' key.
              Auto-adds 'timestamp' and 'agent_id' if missing.

    Returns:
        True on success
    """
    # Auto-populate fields
    if "timestamp" not in entry:
        entry["timestamp"] = datetime.datetime.now().isoformat()
    if "agent_id" not in entry:
        entry["agent_id"] = agent_id

    path = _get_memory_path(agent_id, memory_type)
    entries = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                entries = json.load(f)
        except Exception:
            entries = []

    entries.append(entry)

    # Trim to max entries
    if len(entries) > MAX_MEMORY_ENTRIES:
        entries = entries[-MAX_MEMORY_ENTRIES:]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=4)

    return True


def save_session_memory(agent_id: str, session_data: dict) -> bool:
    """Save a complete session snapshot as episodic memory.

    Args:
        agent_id: Agent identifier
        session_data: Dict with goal, actions_performed, results, decisions, learning

    Returns:
        True on success
    """
    entry = {
        "type": "session",
        "goal": session_data.get("goal", ""),
        "actions_count": len(session_data.get("actions_performed", [])),
        "success_count": session_data.get("success_count", 0),
        "fail_count": session_data.get("fail_count", 0),
        "decisions": session_data.get("decisions", []),
        "learning": session_data.get("learning", ""),
        "summary": session_data.get("summary", ""),
        "timestamp": datetime.datetime.now().isoformat(),
    }
    return save_memory_entry(agent_id, "episodic", entry)


def save_decision_memory(agent_id: str, decision: str, context: str, outcome: str = "") -> bool:
    """Save a decision with context and outcome.

    Args:
        agent_id: Agent identifier
        decision: What was decided
        context: Why it was decided
        outcome: What happened as a result (can be updated later)

    Returns:
        True on success
    """
    entry = {
        "decision": decision,
        "context": context,
        "outcome": outcome,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    return save_memory_entry(agent_id, "decisions", entry)


def save_learned_pattern(agent_id: str, pattern: str, description: str, confidence: float = 0.5) -> bool:
    """Save a learned pattern for an agent.

    Args:
        agent_id: Agent identifier
        pattern: The pattern discovered
        description: Explanation of the pattern
        confidence: Confidence level (0.0 to 1.0)

    Returns:
        True on success
    """
    entry = {
        "pattern": pattern,
        "description": description,
        "confidence": confidence,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    return save_memory_entry(agent_id, "learned_patterns", entry)


def get_memory_context(agent_id: str, max_entries: int = 5) -> str:
    """Build a context string from agent memory for injection into the prompt.

    Args:
        agent_id: The agent to get memory for
        max_entries: Max entries per memory type

    Returns:
        Formatted string with recent memory, or empty string if no memory.
    """
    parts = []

    # Episodic memory (recent sessions)
    episodic = load_memory(agent_id, "episodic")[:max_entries]
    if episodic:
        session_lines = []
        for entry in episodic:
            ts = entry.get("timestamp", "")[:19]
            goal = entry.get("goal", "")[:80]
            success = entry.get("success_count", 0)
            fail = entry.get("fail_count", 0)
            learning = entry.get("learning", "")
            line = f"  [{ts}] Goal: {goal} | Azioni: {success}✅/{fail}❌"
            if learning:
                line += f" | Imparato: {learning[:100]}"
            session_lines.append(line)
        parts.append("📋 **Sessioni recenti:**\n" + "\n".join(session_lines))

    # Decisions (key decisions)
    decisions = load_memory(agent_id, "decisions")[:max_entries]
    if decisions:
        decision_lines = []
        for entry in decisions:
            ts = entry.get("timestamp", "")[:19]
            decision = entry.get("decision", "")[:80]
            outcome = entry.get("outcome", "")
            line = f"  [{ts}] Decisione: {decision}"
            if outcome:
                line += f" → {outcome[:80]}"
            decision_lines.append(line)
        parts.append("📌 **Decisioni passate:**\n" + "\n".join(decision_lines))

    # Learned patterns
    patterns = load_memory(agent_id, "learned_patterns")[:max_entries]
    if patterns:
        pattern_lines = []
        for entry in patterns:
            pattern = entry.get("pattern", "")[:80]
            desc = entry.get("description", "")[:120]
            confidence = entry.get("confidence", 0.5)
            bar = "█" * int(confidence * 10) + "░" * (10 - int(confidence * 10))
            line = f"  • {pattern} | {desc} | Confidenza: {bar} {confidence:.0%}"
            pattern_lines.append(line)
        parts.append("🧠 **Pattern appresi:**\n" + "\n".join(pattern_lines))

    if not parts:
        return ""

    return "\n\n## 🧠 Memoria dell'Agente\n" + "\n\n".join(parts)


def clear_memory(agent_id: str, memory_type: str = None) -> bool:
    """Clear memory for an agent.

    Args:
        agent_id: Agent identifier
        memory_type: Type to clear (None = clear all)

    Returns:
        True on success
    """
    if memory_type:
        path = _get_memory_path(agent_id, memory_type)
        if os.path.exists(path):
            os.remove(path)
        return True
    else:
        agent_dir = os.path.join(AGENT_MEMORY_DIR, agent_id)
        if os.path.isdir(agent_dir):
            for f in os.listdir(agent_dir):
                os.remove(os.path.join(agent_dir, f))
        return True