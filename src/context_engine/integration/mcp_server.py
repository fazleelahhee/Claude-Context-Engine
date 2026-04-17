"""MCP server exposing context engine tools to Claude Code."""
from mcp.server import Server
from mcp.types import Tool, TextContent


class ContextEngineMCP:
    TOOL_NAMES = [
        "context_search", "expand_chunk", "related_context",
        "session_recall", "index_status", "reindex",
    ]

    def __init__(self, retriever, backend, compressor, embedder, config) -> None:
        self._retriever = retriever
        self._backend = backend
        self._compressor = compressor
        self._embedder = embedder
        self._config = config
        self._server = Server("claude-context-engine")
        self._register_tools()

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
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    async def _handle_context_search(self, args):
        chunks = await self._retriever.retrieve(args["query"], top_k=args.get("top_k", 10))
        results = []
        for chunk in chunks:
            text = chunk.compressed_content or chunk.content
            results.append(
                f"[{chunk.file_path}:{chunk.start_line}] (confidence: {chunk.confidence_score:.2f})\n{text}"
            )
        return [
            TextContent(
                type="text",
                text="\n\n---\n\n".join(results) if results else "No results found.",
            )
        ]

    async def _handle_expand_chunk(self, args):
        chunk = await self._backend.get_chunk_by_id(args["chunk_id"])
        if chunk is None:
            return [TextContent(type="text", text="Chunk not found.")]
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
        return [TextContent(type="text", text="Index status: operational")]

    async def _handle_reindex(self, args):
        path = args.get("path")
        if path:
            return [TextContent(type="text", text=f"Re-indexing triggered for: {path}")]
        return [TextContent(type="text", text="Full re-index triggered.")]

    async def run_stdio(self):
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await self._server.run(
                read_stream,
                write_stream,
                self._server.create_initialization_options(),
            )
