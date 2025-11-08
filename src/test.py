import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from neo4j_server import get_neo4j_service
from collections import defaultdict

neo4j_service = get_neo4j_service()
query_entity = "带钢头部温降较大"

# 测试只返回Entity标签的节点
res_path = neo4j_service.get_format_subgraph_paths(query_entity, depth=2)
# print(res_entity)
print(res_path)
