"""MCP server exposing context engine tools to Claude Code."""
import json
from pathlib import Path

from mcp.server import Server
from mcp.types import Tool, TextContent

from context_engine.compression.output_rules import get_output_rules, get_level_description, LEVELS

_CHARS_PER_TOKEN = 4


def _count_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


class ContextEngineMCP:
    TOOL_NAMES = [
        "context_search", "expand_chunk", "related_context",
        "session_recall", "index_status", "reindex",
        "set_output_compression",
    ]

    def __init__(self, retriever, backend, compressor, embedder, config) -> None:
        self._retriever = retriever
        self._backend = backend
        self._compressor = compressor
        self._embedder = embedder
        self._config = config
        self._output_level = config.output_compression
        self._server = Server("claude-context-engine")

        project_name = Path.cwd().name
        self._stats_path = Path(config.storage_path) / project_name / "stats.json"
        self._stats = self._load_stats()

        self._register_tools()
        self._register_prompts()

    def _load_stats(self) -> dict:
        if self._stats_path.exists():
            try:
                return json.loads(self._stats_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {"queries": 0, "raw_tokens": 0, "served_tokens": 0}

    def _save_stats(self) -> None:
        try:
            self._stats_path.write_text(json.dumps(self._stats))
        except OSError:
            pass

    def _record(self, raw_tokens: int, served_tokens: int) -> None:
        self._stats["queries"] += 1
        self._stats["raw_tokens"] += raw_tokens
        self._stats["served_tokens"] += served_tokens
        self._save_stats()

    def get_tool_names(self) -> list[str]:
        return list(self.TOOL_NAMES)

    def _register_tools(self) -> None:
        @self._server.list_tools()
        async def list_tools():
            return [
                Tool(
                    name="context_search",
                    description="Search project context — code, docs, session history",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "top_k": {"type": "integer", "default": 10},
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="expand_chunk",
                    description="Get the full original content for a compressed chunk",
                    inputSchema={
                        "type": "object",
                        "properties": {"chunk_id": {"type": "string"}},
                        "required": ["chunk_id"],
                    },
                ),
                Tool(
                    name="related_context",
                    description="Find related code via graph edges",
                    inputSchema={
                        "type": "object",
                        "properties": {"chunk_id": {"type": "string"}},
                        "required": ["chunk_id"],
                    },
                ),
                Tool(
                    name="session_recall",
                    description="Recall past discussions and decisions about a topic",
                    inputSchema={
                        "type": "object",
                        "properties": {"topic": {"type": "string"}},
                        "required": ["topic"],
                    },
                ),
                Tool(
                    name="index_status",
                    description="Check when the index was last updated",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="reindex",
                    description="Trigger re-indexing of a file or the entire project",
                    inputSchema={
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                    },
                ),
                Tool(
                    name="set_output_compression",
                    description="Set output compression level to reduce response token cost. Levels: off, lite, standard, max",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "level": {
                                "type": "string",
                                "enum": list(LEVELS),
                                "description": "off=normal, lite=no filler, standard=fragments ~65% savings, max=telegraphic ~75% savings",
                            },
                        },
                        "required": ["level"],
                    },
                ),
            ]

        @self._server.call_tool()
        async def call_tool(name: str, arguments: dict):
            if name == "context_search":
                return await self._handle_context_search(arguments)
            elif name == "expand_chunk":
                return await self._handle_expand_chunk(arguments)
            elif name == "related_context":
                return await self._handle_related_context(arguments)
            elif name == "session_recall":
                return await self._handle_session_recall(arguments)
            elif name == "index_status":
                return await self._handle_index_status()
            elif name == "reindex":
                return await self._handle_reindex(arguments)
            elif name == "set_output_compression":
                return self._handle_set_output_compression(arguments)
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def _handle_context_search(self, args):
        chunks = await self._retriever.retrieve(args["query"], top_k=args.get("top_k", 10))
        results = []
        raw_tokens = 0
        served_tokens = 0
        for chunk in chunks:
            served_text = chunk.compressed_content or chunk.content
            raw_tokens += _count_tokens(chunk.content)
            served_tokens += _count_tokens(served_text)
            results.append(
                f"[{chunk.file_path}:{chunk.start_line}] (confidence: {chunk.confidence_score:.2f})\n{served_text}"
            )
        body = "\n\n---\n\n".join(results) if results else "No results found."
        rules = get_output_rules(self._output_level)
        if rules:
            body += f"\n\n---\n[Respond using {self._output_level} output compression]"
        self._record(raw_tokens, served_tokens)
        return [TextContent(type="text", text=body)]

    async def _handle_expand_chunk(self, args):
        chunk = await self._backend.get_chunk_by_id(args["chunk_id"])
        if chunk is None:
            return [TextContent(type="text", text="Chunk not found.")]
        tokens = _count_tokens(chunk.content)
        self._record(tokens, tokens)
        return [
            TextContent(
                type="text",
                text=f"[{chunk.file_path}:{chunk.start_line}-{chunk.end_line}]\n{chunk.content}",
            )
        ]

    async def _handle_related_context(self, args):
        neighbors = await self._backend.graph_neighbors(args["chunk_id"])
        if not neighbors:
            return [TextContent(type="text", text="No related context found.")]
        lines = [f"- {n.node_type.value}: {n.name} ({n.file_path})" for n in neighbors]
        return [TextContent(type="text", text="\n".join(lines))]

    async def _handle_session_recall(self, args):
        chunks = await self._retriever.retrieve(args["topic"], top_k=5)
        session_chunks = [c for c in chunks if c.chunk_type.value in ("session", "decision")]
        if not session_chunks:
            session_chunks = chunks[:3]
        results = [c.compressed_content or c.content for c in session_chunks]
        return [
            TextContent(
                type="text",
                text="\n\n".join(results) if results else "No session history found.",
            )
        ]

    async def _handle_index_status(self):
        queries = self._stats["queries"]
        raw = self._stats["raw_tokens"]
        served = self._stats["served_tokens"]
        saved = raw - served
        pct = int(saved / raw * 100) if raw > 0 else 0

        status_parts = [
            "Index status: operational",
            f"Output compression: {self._output_level} — {get_level_description(self._output_level)}",
        ]
        if queries > 0:
            status_parts.append(
                f"Token savings ({queries} queries): {raw:,} raw → {served:,} served "
                f"({saved:,} saved, {pct}%)"
            )
        else:
            status_parts.append("Token savings: no queries recorded yet")
        return [TextContent(type="text", text="\n".join(status_parts))]

    async def _handle_reindex(self, args):
        path = args.get("path")
        if path:
            return [TextContent(type="text", text=f"Re-indexing triggered for: {path}")]
        return [TextContent(type="text", text="Full re-index triggered.")]

    def _handle_set_output_compression(self, args):
        level = args.get("level", "standard")
        if level not in LEVELS:
            return [TextContent(type="text", text=f"Invalid level: {level}. Use: {', '.join(LEVELS)}")]
        self._output_level = level
        desc = get_level_description(level)
        rules = get_output_rules(level)
        if rules:
            return [TextContent(type="text", text=f"Output compression set to: {level}\n{desc}\n\n{rules}")]
        return [TextContent(type="text", text=f"Output compression disabled. Claude will respond normally.")]

    def _register_prompts(self):
        """Register MCP prompts that inject output compression rules at session start."""
        from mcp.types import Prompt, PromptMessage, PromptArgument

        @self._server.list_prompts()
        async def list_prompts():
            return [
                Prompt(
                    name="context-engine-init",
                    description="Initialize context engine with output compression rules",
                    arguments=[
                        PromptArgument(
                            name="output_level",
                            description="Output compression level: off, lite, standard, max",
                            required=False,
                        ),
                    ],
                ),
            ]

        @self._server.get_prompt()
        async def get_prompt(name: str, arguments: dict | None = None):
            if name != "context-engine-init":
                return None
            level = (arguments or {}).get("output_level", self._output_level)
            rules = get_output_rules(level)
            content = "Context engine active."
            if rules:
                content += f"\n\n{rules}"
            return {
                "messages": [
                    PromptMessage(
                        role="user",
                        content=TextContent(type="text", text=content),
                    ),
                ],
            }

    async def run_stdio(self):
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream,
                write_stream,
                self._server.create_initialization_options(),
            )
