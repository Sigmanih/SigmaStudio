"""Context Broker for Sigma Studio — Shared context between agents via SQLite.
Permette agli agenti di condividere decisioni, scoperte e riassunti in modo strutturato.
Ogni agente può: depositare il proprio contesto, leggere il contesto degli altri agenti,
e ricevere un summary unificato di tutto il lavoro fatto finora nella pipeline."""

import os
import json
import sqlite3
import datetime

CONTEXT_DB = "agent_context.db"


def _get_conn() -> sqlite3.Connection:
    """Get or create SQLite connection with context tables."""
    conn = sqlite3.connect(CONTEXT_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _ensure_tables(conn)
    return conn


def _ensure_tables(conn):
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agent_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            memory_type TEXT NOT NULL DEFAULT 'episodic',
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            confidence REAL DEFAULT 0.5
        );
        CREATE INDEX IF NOT EXISTS idx_memory_agent ON agent_memory(agent_id, memory_type);
        
        CREATE TABLE IF NOT EXISTS shared_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            from_agent TEXT,
            summary TEXT NOT NULL,
            files_created TEXT DEFAULT '[]',
            key_decisions TEXT DEFAULT '[]',
            metrics TEXT DEFAULT '{}',
            timestamp TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_context_pipeline ON shared_context(pipeline_id);
        CREATE INDEX IF NOT EXISTS idx_context_agent ON shared_context(agent_id);
        
        CREATE TABLE IF NOT EXISTS pipeline_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            rationale TEXT DEFAULT '',
            outcome TEXT DEFAULT '',
            timestamp TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_decisions_pipeline ON pipeline_decisions(pipeline_id);
        
        CREATE TABLE IF NOT EXISTS agent_chat_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pipeline_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            message TEXT NOT NULL,
            message_type TEXT DEFAULT 'response',
            actions TEXT DEFAULT '[]',
            timestamp TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_chat_pipeline ON agent_chat_log(pipeline_id);
    """)


# ==============================================================================
# AGENT MEMORY (migrated from JSON to SQLite)
# ==============================================================================

def save_agent_memory(agent_id: str, memory_type: str, content: dict, confidence: float = 0.5):
    """Save a memory entry for an agent."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO agent_memory (agent_id, memory_type, content, timestamp, confidence) VALUES (?, ?, ?, ?, ?)",
            (agent_id, memory_type, json.dumps(content), datetime.datetime.now().isoformat(), confidence)
        )
        conn.commit()
    finally:
        conn.close()


def load_agent_memory(agent_id: str, memory_type: str = "episodic", limit: int = 10) -> list:
    """Load recent memory entries for an agent."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT content, timestamp, confidence FROM agent_memory WHERE agent_id = ? AND memory_type = ? ORDER BY id DESC LIMIT ?",
            (agent_id, memory_type, limit)
        ).fetchall()
        result = []
        for row in rows:
            entry = json.loads(row["content"])
            entry["timestamp"] = row["timestamp"]
            entry["confidence"] = row["confidence"]
            result.append(entry)
        return result
    finally:
        conn.close()


def get_memory_context(agent_id: str, max_entries: int = 5) -> str:
    """Build a context string from agent memory for prompt injection."""
    parts = []
    
    episodic = load_agent_memory(agent_id, "episodic", max_entries)
    if episodic:
        lines = []
        for entry in episodic:
            ts = entry.get("timestamp", "")[:19]
            goal = entry.get("goal", "")[:80]
            success = entry.get("success_count", 0)
            fail = entry.get("fail_count", 0)
            line = f"  [{ts}] Goal: {goal} | Azioni: {success}✅/{fail}❌"
            if entry.get("learning"):
                line += f" | Imparato: {entry['learning'][:100]}"
            lines.append(line)
        parts.append("📋 **Sessioni recenti:**\n" + "\n".join(lines))
    
    if not parts:
        return ""
    return "\n\n## 🧠 Memoria dell'Agente\n" + "\n\n".join(parts)


# ==============================================================================
# SHARED CONTEXT — Passaggio di consegne tra agenti
# ==============================================================================

def save_shared_context(pipeline_id: str, agent_id: str, summary: dict, 
                        from_agent: str = None, files_created: list = None,
                        key_decisions: list = None, metrics: dict = None):
    """Save shared context from an agent for downstream agents to read."""
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO shared_context 
               (pipeline_id, agent_id, from_agent, summary, files_created, key_decisions, metrics, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pipeline_id, agent_id, from_agent,
                json.dumps(summary),
                json.dumps(files_created or []),
                json.dumps(key_decisions or []),
                json.dumps(metrics or {}),
                datetime.datetime.now().isoformat()
            )
        )
        conn.commit()
    finally:
        conn.close()


def get_shared_context(pipeline_id: str, agent_id: str = None) -> list:
    """Get shared context for a pipeline, optionally filtered by agent."""
    conn = _get_conn()
    try:
        if agent_id:
            rows = conn.execute(
                "SELECT * FROM shared_context WHERE pipeline_id = ? AND (agent_id = ? OR from_agent = ?) ORDER BY id",
                (pipeline_id, agent_id, agent_id)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM shared_context WHERE pipeline_id = ? ORDER BY id",
                (pipeline_id,)
            ).fetchall()
        
        result = []
        for row in rows:
            result.append({
                "id": row["id"],
                "pipeline_id": row["pipeline_id"],
                "agent_id": row["agent_id"],
                "from_agent": row["from_agent"],
                "summary": json.loads(row["summary"]),
                "files_created": json.loads(row["files_created"]),
                "key_decisions": json.loads(row["key_decisions"]),
                "metrics": json.loads(row["metrics"]),
                "timestamp": row["timestamp"],
            })
        return result
    finally:
        conn.close()


def build_shared_context_prompt(pipeline_id: str, current_agent_id: str) -> str:
    """Build a context prompt string summarizing ALL upstream agents' work."""
    contexts = get_shared_context(pipeline_id)
    if not contexts:
        return ""
    
    parts = ["\n\n## 📋 Contesto Condiviso — Lavoro degli Agenti Precedenti"]
    
    for ctx in contexts:
        if ctx["agent_id"] == current_agent_id:
            continue  # Skip own context
        
        agent_name = ctx.get("from_agent") or ctx["agent_id"]
        summary = ctx.get("summary", {})
        files = ctx.get("files_created", [])
        decisions = ctx.get("key_decisions", [])
        
        lines = [f"\n### {agent_name}"]
        
        if isinstance(summary, dict):
            summary_text = summary.get("overview", "") or summary.get("summary", "") or json.dumps(summary)[:200]
        else:
            summary_text = str(summary)[:200]
        if summary_text:
            lines.append(f"  {summary_text}")
        
        if files:
            lines.append(f"  📄 File creati: {', '.join(f[:50] for f in files)}")
        
        if decisions:
            lines.append(f"  📌 Decisioni:")
            for d in decisions[:3]:
                if isinstance(d, dict):
                    lines.append(f"    • {d.get('decision', d.get('description', str(d)))[:100]}")
                else:
                    lines.append(f"    • {str(d)[:100]}")
        
        parts.append("\n".join(lines))
    
    return "\n".join(parts)


# ==============================================================================
# PIPELINE DECISIONS — Tracciamento decisioni critiche
# ==============================================================================

def log_pipeline_decision(pipeline_id: str, node_id: str, agent_id: str,
                          decision: str, rationale: str = "", outcome: str = ""):
    """Log a critical decision made during pipeline execution."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO pipeline_decisions (pipeline_id, node_id, agent_id, decision, rationale, outcome, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pipeline_id, node_id, agent_id, decision, rationale, outcome, datetime.datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_pipeline_decisions(pipeline_id: str) -> list:
    """Get all decisions made in a pipeline."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM pipeline_decisions WHERE pipeline_id = ? ORDER BY id",
            (pipeline_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ==============================================================================
# AGENT CHAT LOG — Messaggi visibili nella chat laterale
# ==============================================================================

def log_agent_message(pipeline_id: str, agent_id: str, message: str,
                      message_type: str = "response", actions: list = None):
    """Log an agent message for display in the side chat."""
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO agent_chat_log (pipeline_id, agent_id, message, message_type, actions, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (pipeline_id, agent_id, message[:500], message_type, json.dumps(actions or []), datetime.datetime.now().isoformat())
        )
        conn.commit()
    finally:
        conn.close()


def get_agent_chat_log(pipeline_id: str, limit: int = 50) -> list:
    """Get agent chat messages for a pipeline."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM agent_chat_log WHERE pipeline_id = ? ORDER BY id DESC LIMIT ?",
            (pipeline_id, limit)
        ).fetchall()
        result = []
        for row in reversed(rows):
            result.append({
                "id": row["id"],
                "agent_id": row["agent_id"],
                "message": row["message"],
                "message_type": row["message_type"],
                "actions": json.loads(row["actions"]),
                "timestamp": row["timestamp"],
            })
        return result
    finally:
        conn.close()


# ==============================================================================
# API HANDLERS
# ==============================================================================

def handle_context_share(self):
    """POST /api/context/share — Share agent context for downstream agents."""
    try:
        req = self.read_json_body()
        pipeline_id = req.get("pipeline_id", "default")
        agent_id = req.get("agent_id", "")
        summary = req.get("summary", {})
        files_created = req.get("files_created", [])
        key_decisions = req.get("key_decisions", [])
        metrics = req.get("metrics", {})
        
        save_shared_context(pipeline_id, agent_id, summary, 
                          files_created=files_created, key_decisions=key_decisions, metrics=metrics)
        return self.send_json_response({"success": True})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_context_get(self):
    """GET /api/context/get?pipeline_id=xxx — Get shared context for a pipeline."""
    from urllib.parse import parse_qs, urlparse
    try:
        query = parse_qs(urlparse(self.path).query)
        pipeline_id = query.get("pipeline_id", [None])[0]
        if not pipeline_id:
            return self.send_json_response({"success": False, "error": "pipeline_id richiesto"}, 400)
        result = get_shared_context(pipeline_id)
        return self.send_json_response({"success": True, "contexts": result})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_context_chat_log(self):
    """GET /api/context/chat_log?pipeline_id=xxx — Get agent chat messages."""
    from urllib.parse import parse_qs, urlparse
    try:
        query = parse_qs(urlparse(self.path).query)
        pipeline_id = query.get("pipeline_id", [None])[0]
        if not pipeline_id:
            return self.send_json_response({"success": False, "error": "pipeline_id richiesto"}, 400)
        limit = int(query.get("limit", [500])[0])
        messages = get_agent_chat_log(pipeline_id, limit)
        return self.send_json_response({"success": True, "messages": messages})
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)


def handle_chat_message_save(self):
    """POST /api/context/chat_message — Save a chat message to persistent log."""
    try:
        req = self.read_json_body()
        pipeline_id = req.get("pipeline_id", "default")
        agent_id = req.get("agent_id", "system")
        message = req.get("message", "")
        message_type = req.get("message_type", "action")
        actions = req.get("actions", [])
        timestamp = req.get("timestamp", datetime.datetime.now().isoformat())
        
        if not message:
            return self.send_json_response({"success": False, "error": "message richiesto"}, 400)
        
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO agent_chat_log (pipeline_id, agent_id, message, message_type, actions, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (pipeline_id, agent_id, message[:2000], message_type, json.dumps(actions or []), timestamp)
            )
            conn.commit()
            # Return the inserted message id
            cursor = conn.execute("SELECT last_insert_rowid()")
            msg_id = cursor.fetchone()[0]
            return self.send_json_response({"success": True, "id": msg_id})
        finally:
            conn.close()
    except Exception as e:
        return self.send_json_response({"success": False, "error": str(e)}, 500)
