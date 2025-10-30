import os
import logging
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class Neo4jService:
    """
    封装 Neo4j 数据库访问，提供常用图谱接口：
    - 列出图谱中的实体（节点）
    - 按名称获取实体信息
    - 获取实体的多度子图（可选方向，限制返回规模）
    - 通用 Cypher 执行
    """

    def __init__(self,
                 uri: Optional[str] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 graph_id: Optional[str] = None) -> None:
        self.uri = uri or os.getenv("NEO4J_URI")
        self.user = user or os.getenv("NEO4J_USER")
        self.password = password or os.getenv("NEO4J_PASSWORD")
        self.graph_id = graph_id or os.getenv("NEO4J_GRAPH_ID", "643b6cd8-0664-46b2-8a1c-175585c48161")
        
        if not all([self.uri, self.user, self.password]):
            raise ValueError("Neo4j 配置信息不完整，请在 .env 中设置 NEO4J_URI/USER/PASSWORD")

        self.driver: Driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

        # 简单连通性测试
        with self.driver.session() as session:
            session.run("RETURN 1")
        logger.info(f"✅ Neo4jService 已连接到数据库，使用图谱 ID: {self.graph_id}")

    # 辅助：将节点记录标准化
    @staticmethod
    def _normalize_node(labels: List[str], properties: Dict[str, Any], node_id: Optional[int] = None) -> Dict[str, Any]:
        name = properties.get("name") or properties.get("title") or str(properties)
        return {
            "id": node_id,
            "name": name,
            "description": properties.get("description") or "",
            "labels": labels or [],
            "properties": properties or {},
        }

    # 辅助：将关系记录标准化
    @staticmethod
    def _normalize_rel(rel, start_id: int, end_id: int) -> Dict[str, Any]:
        # rel 是 neo4j.Relationship，可能没有直接的 id 获取；用 element_id 作为唯一标识
        try:
            rel_id = getattr(rel, "id", None)
        except Exception:
            rel_id = None
        element_id = getattr(rel, "element_id", None)
        rel_type = getattr(rel, "type", None)
        props = dict(rel)
        return {
            "id": rel_id,
            "element_id": element_id,
            "type": rel_type,
            "start": start_id,
            "end": end_id,
            "properties": props,
        }

    def list_entities(self, label: Optional[str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        列出图谱中的实体（节点）。
        Args:
            label: 仅返回指定标签的节点（可选）
            limit: 最大返回数量
        Returns:
            规范化的节点列表：[{id, name, labels, properties}]
        """
        cypher = (
            f"MATCH (n:{label}) WHERE n.graph_id = $graph_id RETURN elementId(n) as id, labels(n) as labels, properties(n) as properties LIMIT $limit"
            if label else
            "MATCH (n) WHERE n.graph_id = $graph_id RETURN elementId(n) as id, labels(n) as labels, properties(n) as properties LIMIT $limit"
        )

        with self.driver.session() as session:
            result = session.run(cypher, limit=limit, graph_id=self.graph_id)
            nodes: List[Dict[str, Any]] = []
            for record in result:
                nodes.append(self._normalize_node(record["labels"], record["properties"], record["id"]))
            return nodes


    def get_entity(self, name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称（或 title）获取单个实体。
        Returns: {id, name, labels, properties} 或 None
        """
        cypher = (
            "MATCH (n) WHERE n.name = $name AND n.graph_id = $graph_id "
            "RETURN id(n) as id, labels(n) as labels, properties(n) as properties LIMIT 1"
        )
        with self.driver.session() as session:
            record = session.run(cypher, name=name, graph_id=self.graph_id).single()
            if not record:
                return None
            return self._normalize_node(record["labels"], record["properties"], record["id"])

    
    def get_entity_connections(self, entity_id: str, direction: str = "both", limit: int = 1000) -> List[Dict[str, Any]]:
        """
        根据实体ID获取该实体连接的所有边以及对应的尾节点。
        Args:
            entity_id: 实体的ID（可以是内部ID、elementId或应用程序生成的ID）
            direction: 关系方向，取值："out" | "in" | "both"
            limit: 返回关系数量上限
        Returns:
            [{"edge": {...}, "target_node": {...}}, ...]
        """
        if direction not in ("out", "in", "both"):
            direction = "both"

        # 构建查询语句，支持多种ID格式
        if direction == "out":
            cypher = """
            MATCH (start) WHERE (elementId(start) = $entity_id OR start.id = $entity_id OR toString(elementId(start)) = $entity_id) AND start.graph_id = $graph_id
            MATCH (start)-[r]->(target) WHERE target.graph_id = $graph_id
            RETURN r, target
            LIMIT $limit
            """
        elif direction == "in":
            cypher = """
            MATCH (start) WHERE (elementId(start) = $entity_id OR start.id = $entity_id OR toString(elementId(start)) = $entity_id) AND start.graph_id = $graph_id
            MATCH (source)-[r]->(start) WHERE source.graph_id = $graph_id
            RETURN r, source as target
            LIMIT $limit
            """
        else:  # both
            cypher = """
            MATCH (start) WHERE (elementId(start) = $entity_id OR start.id = $entity_id OR toString(elementId(start)) = $entity_id) AND start.graph_id = $graph_id
            MATCH (start)-[r]-(target) WHERE target.graph_id = $graph_id
            RETURN r, target
            LIMIT $limit
            """

        connections = []

        with self.driver.session() as session:
            result = session.run(cypher, entity_id=entity_id, limit=limit, graph_id=self.graph_id)
            for record in result:
                rel = record["r"]
                target_node = record["target"]
                
                # 创建边和目标节点的配对
                edge_info = self._normalize_rel(rel, rel.start_node.id, rel.end_node.id)
                node_info = self._normalize_node(list(target_node.labels), dict(target_node), target_node.id)
                
                connections.append({
                    "edge": edge_info,
                    "target_node": node_info
                })

        return connections


    def get_subgraph(self,
                     name: str,
                     depth: int = 1,
                     direction: str = "both",
                     limit: int = 1000) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取实体的多度子图。
        Args:
            name: 起始实体名称（或 title）
            depth: 路径最大跳数（>=1）
            direction: 关系方向，取值："out" | "in" | "both"
            limit: 返回路径数量上限（用于保护查询规模）
        Returns:
            { nodes: [...], edges: [...] }
        注意：Cypher 的可变长度路径不支持参数化范围，这里会安全地构造查询字符串。
        """
        depth = max(1, int(depth))
        if direction not in ("out", "in", "both"):
            direction = "both"

        if direction == "out":
            pattern = f"-[*1..{depth}]->"
        elif direction == "in":
            pattern = f"<-[*1..{depth}]-"
        else:
            pattern = f"-[*1..{depth}]-"

        cypher = (
            "MATCH (start) WHERE start.name = $name AND start.graph_id = $graph_id "
            f"MATCH p=(start){pattern}(m) WHERE m.graph_id = $graph_id RETURN p LIMIT $limit"
        )

        nodes_map: Dict[int, Dict[str, Any]] = {}
        edges_map: Dict[Tuple[int, int, str], Dict[str, Any]] = {}

        with self.driver.session() as session:
            result = session.run(cypher, name=name, limit=limit, graph_id=self.graph_id)
            for record in result:
                path = record["p"]
                # 遍历路径上的节点
                for node in path.nodes:
                    nid = node.id
                    if nid not in nodes_map:
                        nodes_map[nid] = self._normalize_node(list(node.labels), dict(node), nid)
                # 遍历路径上的关系
                for rel in path.relationships:
                    start_id = rel.start_node.id
                    end_id = rel.end_node.id
                    key = (start_id, end_id, rel.type)
                    if key not in edges_map:
                        edges_map[key] = self._normalize_rel(rel, start_id, end_id)

        return {
            "nodes": list(nodes_map.values()),
            "edges": list(edges_map.values()),
        }

    def run_cypher(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        执行通用 Cypher 查询，返回字典列表。
        注意：仅用于受信任输入，或自行进行查询白名单控制。
        自动添加 graph_id 参数到查询参数中。
        """
        # 自动添加 graph_id 到参数中
        if params is None:
            params = {}
        params["graph_id"] = self.graph_id
        
        with self.driver.session() as session:
            result = session.run(query, **params)
            rows: List[Dict[str, Any]] = []
            for record in result:
                rows.append(dict(record))
            return rows

    def close(self) -> None:
        if self.driver:
            self.driver.close()


# 提供一个全局单例，方便在应用中直接获取服务
_neo4j_service: Optional[Neo4jService] = None


def get_neo4j_service() -> Neo4jService:
    global _neo4j_service
    if _neo4j_service is None:
        _neo4j_service = Neo4jService()
    return _neo4j_service