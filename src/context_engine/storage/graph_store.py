"""Kuzu-backed graph store for code relationships."""

import kuzu

from context_engine.models import GraphNode, GraphEdge, NodeType, EdgeType


class GraphStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)
        self._init_schema()

    def _init_schema(self) -> None:
        try:
            self._conn.execute(
                "CREATE NODE TABLE IF NOT EXISTS Node("
                "id STRING, node_type STRING, name STRING, file_path STRING, "
                "PRIMARY KEY(id))"
            )
            self._conn.execute(
                "CREATE REL TABLE IF NOT EXISTS Edge("
                "FROM Node TO Node, edge_type STRING)"
            )
        except Exception:
            pass  # tables already exist

    async def ingest(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        for node in nodes:
            self._conn.execute(
                "MERGE (n:Node {id: $id}) SET n.node_type = $node_type, "
                "n.name = $name, n.file_path = $file_path",
                {"id": node.id, "node_type": node.node_type.value, "name": node.name, "file_path": node.file_path},
            )
        for edge in edges:
            self._conn.execute(
                "MATCH (a:Node {id: $src}), (b:Node {id: $dst}) "
                "CREATE (a)-[:Edge {edge_type: $etype}]->(b)",
                {"src": edge.source_id, "dst": edge.target_id, "etype": edge.edge_type.value},
            )

    async def get_nodes_by_file(self, file_path: str) -> list[GraphNode]:
        result = self._conn.execute(
            "MATCH (n:Node) WHERE n.file_path = $fp RETURN n.id, n.node_type, n.name, n.file_path",
            {"fp": file_path},
        )
        nodes = []
        while result.has_next():
            row = result.get_next()
            nodes.append(GraphNode(id=row[0], node_type=NodeType(row[1]), name=row[2], file_path=row[3]))
        return nodes

    async def get_neighbors(self, node_id: str, edge_type: EdgeType | None = None) -> list[GraphNode]:
        if edge_type:
            result = self._conn.execute(
                "MATCH (a:Node {id: $id})-[e:Edge]->(b:Node) WHERE e.edge_type = $etype "
                "RETURN b.id, b.node_type, b.name, b.file_path",
                {"id": node_id, "etype": edge_type.value},
            )
        else:
            result = self._conn.execute(
                "MATCH (a:Node {id: $id})-[e:Edge]->(b:Node) RETURN b.id, b.node_type, b.name, b.file_path",
                {"id": node_id},
            )
        nodes = []
        while result.has_next():
            row = result.get_next()
            nodes.append(GraphNode(id=row[0], node_type=NodeType(row[1]), name=row[2], file_path=row[3]))
        return nodes

    async def get_nodes_by_type(self, node_type: NodeType) -> list[GraphNode]:
        result = self._conn.execute(
            "MATCH (n:Node) WHERE n.node_type = $nt RETURN n.id, n.node_type, n.name, n.file_path",
            {"nt": node_type.value},
        )
        nodes = []
        while result.has_next():
            row = result.get_next()
            nodes.append(GraphNode(id=row[0], node_type=NodeType(row[1]), name=row[2], file_path=row[3]))
        return nodes

    async def delete_by_file(self, file_path: str) -> None:
        self._conn.execute("MATCH (n:Node) WHERE n.file_path = $fp DETACH DELETE n", {"fp": file_path})
