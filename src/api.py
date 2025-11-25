from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from pipeline import step1_entity_recognition, step2_get_subgraph, step3_qa_with_llm
from path_visualizer import visualize_paths_with_graphviz
from query_logger import get_query_logger
import io
import base64
import time

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
    visualization_base64: Optional[str] = None  # Base64 编码的可视化图片

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    Receives a query and returns the center entity, paths, and answer.
    All query information is logged to files.
    """
    start_time = time.time()
    logger = get_query_logger()
    error_msg = None

    try:
        # Step 1: Entity Recognition
        center_entity = step1_entity_recognition(request.query, graph_id=request.graph_id)

        if not center_entity:
            answer = "无法识别到您问题中的实体，请换个问题试试。"
            # 记录日志
            execution_time = time.time() - start_time
            logger.log_query(
                query=request.query,
                center_entity=None,
                all_paths=None,
                answer=answer,
                referenced_paths=None,
                graph_id=request.graph_id,
                execution_time=execution_time,
                error="No entity recognized"
            )
            return QueryResponse(center_entity=None, paths=None, answer=answer)

        # Step 2: Get Subgraph
        paths = step2_get_subgraph(center_entity, graph_id=request.graph_id)

        # Step 3: QA with LLM
        qa_result = step3_qa_with_llm(request.query, str(paths))

        # Step 4: 生成参考路径的可视化图片
        visualization_base64 = None
        referenced_paths = qa_result.get('referenced_paths', [])
        if referenced_paths:
            try:
                # 生成可视化图片
                img = visualize_paths_with_graphviz(referenced_paths)
                # 转换为 base64
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                buf.seek(0)
                visualization_base64 = base64.b64encode(buf.read()).decode('utf-8')
            except Exception as viz_error:
                # 图片生成失败时不影响主流程，只记录错误
                logger.log_query(
                    query=request.query,
                    center_entity=center_entity,
                    all_paths=None,
                    answer="",
                    referenced_paths=None,
                    graph_id=request.graph_id,
                    execution_time=0,
                    error=f"Visualization failed: {str(viz_error)}"
                )
                visualization_base64 = None  # 确保返回None而不是报错

        answer = qa_result.get('answer', '')

        # 记录成功的查询日志
        execution_time = time.time() - start_time
        logger.log_query(
            query=request.query,
            center_entity=center_entity,
            all_paths=paths,
            answer=answer,
            referenced_paths=referenced_paths,
            graph_id=request.graph_id,
            execution_time=execution_time,
            error=None
        )
        
        return QueryResponse(
            center_entity=center_entity,
            paths=paths,
            answer=answer,
            referenced_paths=referenced_paths,
            visualization_base64=visualization_base64
        )

    except Exception as e:
        # 记录失败的查询日志
        error_msg = str(e)
        execution_time = time.time() - start_time
        logger.log_query(
            query=request.query,
            center_entity=None,
            all_paths=None,
            answer="",
            referenced_paths=None,
            graph_id=request.graph_id,
            execution_time=execution_time,
            error=error_msg
        )
        raise

@app.get("/")
def read_root():
    return {"Hello": "World"}
