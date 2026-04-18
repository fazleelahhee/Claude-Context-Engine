"""Graph store — SQLite-backed implementation."""

import asyncio
import json
import sqlite3

from context_engine.models import GraphNode, GraphEdge, NodeType, EdgeType

_DDL = """
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    node_type   TEXT NOT NULL,
    name        TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    properties  TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS edges (
    source_id   TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    edge_type   TEXT NOT NULL,
    properties  TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (source_id, target_id, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON edges (source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges (target_id);
CREATE INDEX IF NOT EXISTS idx_nodes_file   ON nodes  (file_path);
"""


def _row_to_node(row: tuple) -> GraphNode:
    node_id, node_type, name, file_path, properties = row
    return GraphNode(
        id=node_id,
        node_type=NodeType(node_type),
        name=name,
        file_path=file_path,
        properties=json.loads(properties),
    )


class GraphStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path + ".db"
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.executescript(_DDL)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Sync internals (run inside asyncio.to_thread)
    # ------------------------------------------------------------------

    def _sync_ingest(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        cur = self._conn.cursor()
        for node in nodes:
            cur.execute(
                "INSERT OR REPLACE INTO nodes (id, node_type, name, file_path, properties) "
                "VALUES (?, ?, ?, ?, ?)",
                (node.id, node.node_type.value, node.name, node.file_path,
                 json.dumps(node.properties)),
            )
        for edge in edges:
            cur.execute(
                "INSERT OR REPLACE INTO edges (source_id, target_id, edge_type, properties) "
                "VALUES (?, ?, ?, ?)",
                (edge.source_id, edge.target_id, edge.edge_type.value,
                 json.dumps(edge.properties)),
            )
        self._conn.commit()

    def _sync_get_neighbors(self, node_id: str, edge_type: EdgeType | None) -> list[GraphNode]:
        cur = self._conn.cursor()
        if edge_type is None:
            cur.execute(
                "SELECT n.id, n.node_type, n.name, n.file_path, n.properties "
                "FROM edges e JOIN nodes n ON e.target_id = n.id "
                "WHERE e.source_id = ?",
                (node_id,),
            )
        else:
            cur.execute(
                "SELECT n.id, n.node_type, n.name, n.file_path, n.properties "
                "FROM edges e JOIN nodes n ON e.target_id = n.id "
                "WHERE e.source_id = ? AND e.edge_type = ?",
                (node_id, edge_type.value),
            )
        return [_row_to_node(row) for row in cur.fetchall()]

    def _sync_get_nodes_by_file(self, file_path: str) -> list[GraphNode]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, node_type, name, file_path, properties FROM nodes WHERE file_path = ?",
            (file_path,),
        )
        return [_row_to_node(row) for row in cur.fetchall()]

    def _sync_get_nodes_by_type(self, node_type: NodeType) -> list[GraphNode]:
        cur = self._conn.cursor()
        cur.execute(
            "SELECT id, node_type, name, file_path, properties FROM nodes WHERE node_type = ?",
            (node_type.value,),
        )
        return [_row_to_node(row) for row in cur.fetchall()]

    def _sync_delete_by_file(self, file_path: str) -> None:
        cur = self._conn.cursor()
        # Collect node ids belonging to this file
        cur.execute("SELECT id FROM nodes WHERE file_path = ?", (file_path,))
        node_ids = [row[0] for row in cur.fetchall()]
        if node_ids:
            placeholders = ",".join("?" * len(node_ids))
            cur.execute(
                f"DELETE FROM edges WHERE source_id IN ({placeholders}) "
                f"OR target_id IN ({placeholders})",
                node_ids + node_ids,
            )
            cur.execute(
                f"DELETE FROM nodes WHERE id IN ({placeholders})",
                node_ids,
            )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def ingest(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        await asyncio.to_thread(self._sync_ingest, nodes, edges)

    async def get_neighbors(self, node_id: str, edge_type: EdgeType | None = None) -> list[GraphNode]:
        return await asyncio.to_thread(self._sync_get_neighbors, node_id, edge_type)

    async def get_nodes_by_file(self, file_path: str) -> list[GraphNode]:
        return await asyncio.to_thread(self._sync_get_nodes_by_file, file_path)

    async def get_nodes_by_type(self, node_type: NodeType) -> list[GraphNode]:
        return await asyncio.to_thread(self._sync_get_nodes_by_type, node_type)

    async def delete_by_file(self, file_path: str) -> None:
        await asyncio.to_thread(self._sync_delete_by_file, file_path)
