# ==============================================================================
# core/mcp/memory_server.py — Memory MCP Server
# Vector DB, Episodic Memory, RAG Context Broker & Knowledge Graph
# ==============================================================================
import json
import os
from core.mcp.base_server import BaseMCPServer
from core.mcp.governance import SAFE, SENSITIVE
from core.logger import get_logger

log = get_logger(__name__)


class MemoryMCPServer(BaseMCPServer):
    def __init__(self):
        super().__init__(
            name="Memory MCP",
            version="1.0.0",
            description="Vector DB, RAG context broker, and episodic memory persistence for Sigma Studio"
        )
        self._init_tools()
        self._init_resources()

    def _init_tools(self):
        self.register_tool(
            name="query_vector_db",
            description="Perform semantic search query on local vector DB or knowledge base.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query text"},
                    "limit": {"type": "integer", "description": "Max results to return", "default": 5}
                },
                "required": ["query"]
            },
            handler=self._handle_query_vector_db,
            safety=SAFE,
            category="memory",
        )

        self.register_tool(
            name="save_episodic_memory",
            description="Persist agent session episodic memory, decisions, and context summaries.",
            input_schema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string", "description": "Active session ID"},
                    "memory_key": {"type": "string", "description": "Key identifier for memory"},
                    "content": {"type": "string", "description": "Memory text content"}
                },
                "required": ["session_id", "memory_key", "content"]
            },
            handler=self._handle_save_episodic_memory,
            safety=SAFE,
            category="memory",
        )

        self.register_tool(
            name="search_knowledge_graph",
            description="Query the conceptual graph and topics network of Sigma Studio.",
            input_schema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Topic or keyword"}
                },
                "required": ["topic"]
            },
            handler=self._handle_search_knowledge_graph,
            safety=SAFE,
            category="memory",
        )

    def _init_resources(self):
        self.register_resource(
            uri="memory://episodic/active",
            name="Active Episodic Memory",
            description="Current active session episodic memory store",
            mime_type="application/json",
            handler=self._read_active_memory
        )
        self.register_resource(
            uri="memory://knowledge/graph",
            name="Sigma Topics Knowledge Graph",
            description="Structure of topics, modules, and sub-topics in Sigma Studio",
            mime_type="application/json",
            handler=self._read_knowledge_graph
        )

    def _handle_query_vector_db(self, query: str = "", limit: int = 5, **kwargs):
        try:
            from core.embedding_router import search_similar_chunks
            results = search_similar_chunks(query or "general", top_k=limit)
            return {"success": True, "query": query, "results": results}
        except Exception as exc:
            log.warning("Vector search fallback triggered: %s", exc)
            return {"success": True, "query": query, "results": [], "note": "Vector DB operating in lightweight mode"}

    def _handle_save_episodic_memory(self, session_id: str = "session_default", memory_key: str = "key_default", content: str = "", **kwargs):
        try:
            from core.agent_memory import save_decision_memory
            # Handle fallback if query key was passed
            actual_content = content or kwargs.get("query") or "sample memory"
            save_decision_memory(session_id, memory_key, actual_content)
            return {"success": True, "message": f"Episodic memory '{memory_key}' saved for session '{session_id}'"}
        except Exception as exc:
            log.error("Failed to save episodic memory: %s", exc)
            return {"success": False, "error": str(exc)}

    def _handle_search_knowledge_graph(self, topic: str = "general", **kwargs):
        try:
            from core.data_handler import load_modules_meta
            meta = load_modules_meta()
            matched = []
            search_term = (topic or kwargs.get("query") or "general").lower()
            for t_name, t_data in meta.get("topics", {}).items():
                if search_term in t_name.lower() or any(search_term in sub.lower() for sub in t_data.get("subtopics", {})):
                    matched.append({"topic": t_name, "details": t_data})
            return {"success": True, "query": search_term, "matches": matched}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _read_active_memory(self, uri: str):
        try:
            from core.agent_memory import load_memory
            mem = load_memory()
            return mem
        except Exception as exc:
            return {"status": "empty", "error": str(exc)}

    def _read_knowledge_graph(self, uri: str):
        try:
            from core.data_handler import load_modules_meta
            return load_modules_meta()
        except Exception as exc:
            return {"topics": {}, "error": str(exc)}
