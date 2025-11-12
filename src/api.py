from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from pipeline import step1_entity_recognition, step2_get_subgraph, step3_qa_with_llm

app = FastAPI(
    title="Knowledge Graph API",
    description="API for interacting with the Knowledge Graph",
    version="1.0.0",
)

class QueryRequest(BaseModel):
    query: str
    graph_id: Optional[str] = None

class QueryResponse(BaseModel):
    center_entity: Optional[str]
    paths: Optional[List[str]]
    answer: str
    referenced_paths: Optional[List[str]] = []

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    Receives a query and returns the center entity, paths, and answer.
    """
    # Step 1: Entity Recognition
    center_entity = step1_entity_recognition(request.query, graph_id = request.graph_id)
    
    if not center_entity:
        return QueryResponse(center_entity=None, paths=None, answer="无法识别到您问题中的实体，请换个问题试试。")
    
    # Step 2: Get Subgraph
    paths = step2_get_subgraph(center_entity, graph_id = request.graph_id)
    
    # Step 3: QA with LLM
    qa_result = step3_qa_with_llm(request.query, str(paths))

    return QueryResponse(
        center_entity=center_entity,
        paths=paths,
        answer=qa_result.get('answer', ''),
        referenced_paths=qa_result.get('referenced_paths', [])
    )

@app.get("/")
def read_root():
    return {"Hello": "World"}