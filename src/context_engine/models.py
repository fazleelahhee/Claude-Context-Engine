"""Shared data models for the context engine."""
from dataclasses import dataclass, field
from enum import Enum


class ChunkType(Enum):
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    DOC = "doc"
    COMMENT = "comment"
    COMMIT = "commit"
    SESSION = "session"
    DECISION = "decision"


class NodeType(Enum):
    FUNCTION = "function"
    CLASS = "class"
    FILE = "file"
    MODULE = "module"
    DOC = "doc"
    COMMIT = "commit"
    SESSION = "session"
    DECISION = "decision"


class EdgeType(Enum):
    CALLS = "calls"
    IMPORTS = "imports"
    DEFINES = "defines"
    MODIFIES = "modifies"
    DISCUSSED_IN = "discussed_in"
    DECIDED = "decided"


class ConfidenceLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @staticmethod
    def from_score(score: float) -> "ConfidenceLevel":
        if score > 0.8:
            return ConfidenceLevel.HIGH
        if score >= 0.5:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW


@dataclass
class Chunk:
    id: str
    content: str
    chunk_type: ChunkType
    file_path: str
    start_line: int
    end_line: int
    language: str
    metadata: dict = field(default_factory=dict)
    embedding: list[float] | None = None
    confidence_score: float = 0.0
    compressed_content: str | None = None

    _CHARS_PER_TOKEN_CODE = 3.3

    @property
    def token_count(self) -> int:
        text = self.compressed_content or self.content
        return max(1, int(len(text) / self._CHARS_PER_TOKEN_CODE))


@dataclass
class GraphNode:
    id: str
    node_type: NodeType
    name: str
    file_path: str
    properties: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    properties: dict = field(default_factory=dict)


@dataclass
class RetrievalResult:
    chunks: list[Chunk]
    graph_nodes: list[GraphNode]
    graph_edges: list[GraphEdge]
    query: str
    confidence_scores: dict[str, float] = field(default_factory=dict)
