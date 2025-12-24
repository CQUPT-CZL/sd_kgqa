from prompts import *
from neo4j_server import get_neo4j_service
from llm_call import quick_call
from query_logger import get_query_logger

def step1_entity_recognition(query: str, graph_id: str = None):
    """
    Performs entity recognition on the given query.
    """
    neo4j_service = get_neo4j_service(graph_id = graph_id)
    entities = neo4j_service.list_entities()
    
    entity_map = {entity["name"]: {"id": entity["id"], "description": entity["description"]} 
        for entity in entities if "Entity" in entity["labels"]}

    from prompts import get_llm_re_entity_prompt

    prompt = get_llm_re_entity_prompt(query, entity_map.keys())

    llm_res = quick_call(prompt, return_json=True)
    
    entity = None if llm_res['json_content']['entity'] == '' else llm_res['json_content']['entity']
    
    # 记录实体识别日志
    try:
        logger = get_query_logger()
        logger.log_entity_recognition(
            query=query,
            candidates_count=len(entity_map.keys()),
            selected_entity=entity,
            graph_id=graph_id
        )
    except Exception:
        pass  # 避免日志记录影响主流程

    return entity

def step2_get_subgraph(entity: str, graph_id: str = None):
    """
    Retrieves the subgraph for the given entity.
    """
    neo4j_service = get_neo4j_service(graph_id = graph_id)
    entity_path = neo4j_service.get_format_subgraph_paths(entity, depth=2)
    entity_path = [item for item in entity_path if '->' in item]
    return entity_path

def step3_qa_with_llm(query: str, entity_path: str):
    """
    Answers the query based on the provided subgraph.
    Returns: dict with 'answer' and 'referenced_paths'
    """
    prompt = get_llm_qa_prompt(query, entity_path)
    llm_res = quick_call(prompt, return_json=True)
    return llm_res['json_content']
    
    

