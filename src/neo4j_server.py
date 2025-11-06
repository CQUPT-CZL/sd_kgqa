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
        self.graph_id = graph_id or os.getenv("NEO4J_GRAPH_ID", "651fa83d-2841-47c3-b4cf-7394a546f28e")
        
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
                     limit: int = 1000,
                     node_labels: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取实体的多度子图，确保返回完整的图结构用于可视化。
        Args:
            name: 起始实体名称
            depth: 路径最大跳数（>=1）
            direction: 关系方向，取值："out" | "in" | "both"
            limit: 返回路径数量上限（用于保护查询规模）
            node_labels: 可选的节点标签过滤列表，如 ['Entity'] 只返回Entity标签的节点
        Returns:
            { nodes: [...], edges: [...] }
            nodes: [{id, name, labels, properties, element_id}]
            edges: [{id, type, start, end, properties, element_id, start_node_id, end_node_id}]
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

        nodes_map: Dict[str, Dict[str, Any]] = {}  # 使用element_id作为key
        edges_map: Dict[str, Dict[str, Any]] = {}  # 使用element_id作为key
        all_nodes_map: Dict[str, Dict[str, Any]] = {}  # 保存所有节点，用于边的完整性检查

        with self.driver.session() as session:
            result = session.run(cypher, name=name, limit=limit, graph_id=self.graph_id)
            for record in result:
                path = record["p"]
                
                # 先收集所有节点（不过滤）
                for node in path.nodes:
                    element_id = node.element_id
                    if element_id not in all_nodes_map:
                        node_labels_list = list(node.labels)
                        node_info = self._normalize_node(node_labels_list, dict(node), node.id)
                        node_info["element_id"] = element_id
                        all_nodes_map[element_id] = node_info
                        
                        # 如果指定了节点标签过滤，检查节点是否符合条件
                        if node_labels is None or any(label in node_labels_list for label in node_labels):
                            nodes_map[element_id] = node_info
                
                # 收集所有边
                for rel in path.relationships:
                    rel_element_id = rel.element_id
                    if rel_element_id not in edges_map:
                        start_node_id = rel.start_node.id
                        end_node_id = rel.end_node.id
                        start_element_id = rel.start_node.element_id
                        end_element_id = rel.end_node.element_id
                        
                        edge_info = self._normalize_rel(rel, start_node_id, end_node_id)
                        edge_info["element_id"] = rel_element_id
                        edge_info["start_node_element_id"] = start_element_id  # 用于可视化连接
                        edge_info["end_node_element_id"] = end_element_id      # 用于可视化连接
                        edges_map[rel_element_id] = edge_info

        # 确保返回的数据结构完整
        nodes_list = list(nodes_map.values())
        edges_list = list(edges_map.values())
        
        # 验证图结构完整性：只保留连接到过滤后节点的边
        filtered_node_element_ids = {node["element_id"] for node in nodes_list}
        valid_edges = []
        
        for edge in edges_list:
            # 如果边的任意一端连接到过滤后的节点，就保留这条边
            start_in_filtered = edge["start_node_element_id"] in filtered_node_element_ids
            end_in_filtered = edge["end_node_element_id"] in filtered_node_element_ids
            
            if start_in_filtered or end_in_filtered:
                valid_edges.append(edge)
                
                # 如果边的另一端节点不在过滤后的节点中，也要添加进来以保持图的完整性
                if start_in_filtered and edge["end_node_element_id"] not in filtered_node_element_ids:
                    if edge["end_node_element_id"] in all_nodes_map:
                        nodes_list.append(all_nodes_map[edge["end_node_element_id"]])
                        filtered_node_element_ids.add(edge["end_node_element_id"])
                        
                if end_in_filtered and edge["start_node_element_id"] not in filtered_node_element_ids:
                    if edge["start_node_element_id"] in all_nodes_map:
                        nodes_list.append(all_nodes_map[edge["start_node_element_id"]])
                        filtered_node_element_ids.add(edge["start_node_element_id"])
        
        return {
            "nodes": nodes_list,
            "edges": valid_edges,
            "stats": {
                "total_nodes": len(nodes_list),
                "total_edges": len(valid_edges),
                "start_node": name,
                "depth": depth,
                "direction": direction
            }
        }
    
    def get_format_subgraph_paths(self, init_entity, depth = 2):
        res_entity = self.get_subgraph(
            name=init_entity, 
            depth=depth, 
            direction="both",
            node_labels=['Entity']
        )
        ne = {}
        du = {}
        nodes = res_entity['nodes']
        edges = res_entity['edges']
        init_id = None 

        # 先构建这个实体element_id对应实体信息的map
        node_map ={}
        for node in nodes:
            if node['labels'][0] != 'Entity':
                continue
            # 使用element_id作为键，这样才能与边的start_node_element_id和end_node_element_id匹配
            node_map[node['element_id']] = (node['name'], node['description'])
            if node['name'] == init_entity:
                init_id = node['element_id']
            ne[node['element_id']] = []
            du[node['element_id']] = 0
        # print(init_id)

        # 遍历edges，构建路径
        edge_map = {}
        for edge in edges:
            start_node_id = edge['start_node_element_id']
            end_node_id = edge['end_node_element_id']
            if start_node_id not in node_map or end_node_id not in node_map:
                continue
            edge_map[(start_node_id, end_node_id)] = (edge['properties']['relation_type'], edge['properties']['description'])
            if start_node_id not in ne:
                ne[start_node_id] = []
            ne[start_node_id].append(end_node_id)
            du[end_node_id] += 1


        res_paths = []
        def dfs(node_id, path: str):
            # print(path, node_id)
            if node_id not in ne or ne[node_id] == []:
                res_paths.append(path)
                return
            for ne_id in ne[node_id]:
                dfs(ne_id, path  + '->' + edge_map[(node_id, ne_id)][0] + '->' + node_map[ne_id][0])

        # dfs(init_id, query_entity)
        # print(du)

        # print(ne)
        for node_id in du.keys():
            if du[node_id] == 0:
                # print(node_id, node_map[node_id][0])
                dfs(node_id, node_map[node_id][0])

        # print(res_paths)
        return res_paths



    def close(self) -> None:
        if self.driver:
            self.driver.close()


# 提供一个全局单例，方便在应用中直接获取服务
_neo4j_service: Optional[Neo4jService] = None


def get_neo4j_service(graph_id: str = None) -> Neo4jService:
    global _neo4j_service
    if _neo4j_service is None:
        _neo4j_service = Neo4jService(graph_id = graph_id)
    return _neo4j_service