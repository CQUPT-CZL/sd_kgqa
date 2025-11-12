"""
基于指定图谱（graph_id），提取类型为“问题”的实体，
生成其二跳子图的推理路径，并调用大模型生成问答对，
将结果以 JSONL（一行一个样本）形式保存。

使用方法（在项目根目录执行）：
    python src/export_qa_samples.py \
        --graph-id "643b6cd8-0664-46b2-8a1c-175585c48161" \
        --out outputs/qa_samples.jsonl

环境依赖：
- 需要在 .env 或环境变量中配置 Neo4j 连接参数：NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD
- 需要配置 OpenAI 相关：OPENAI_API_KEY（以及可选的 OPENAI_API_BASE_URL）
"""

import os
import json
import argparse
from typing import List, Dict, Any

from neo4j_server import get_neo4j_service
from llm_call import LLMCallService
from pydantic import BaseModel


def _find_question_entities(neo4j_service, label: str | None = None, type_values: List[str] = None) -> List[Dict[str, Any]]:
    """筛选出类型为“问题”的实体。
    优先使用节点属性中的 type/类别/category 字段判断；其次兼容标签包含“问题”或“Question”的情况；
    若仍为空，则回退到按名称问句模式进行识别。
    """
    type_values = type_values or ["问题", "Question", "question"]
    type_set = {str(v).lower() for v in type_values}

    entities = neo4j_service.list_entities(label=label)
    results: List[Dict[str, Any]] = []
    for e in entities:
        props = e.get("properties", {})
        # 优先使用 entity_type 作为类型字段
        t = props.get("entity_type") or props.get("type") or props.get("类别") or props.get("category")
        if t and str(t).lower() in type_set:
            results.append(e)
            continue

        # 兼容：实体标签直接包含“问题/Question”
        labels = e.get("labels", [])
        if any(str(lb) in ("问题", "Question") for lb in labels):
            results.append(e)

    if results:
        return results

    # 回退：根据名称判断是否为问句（末尾含问号或典型问句开头）
    question_starts = ("为什么", "如何", "怎样", "怎么", "是否", "什么是", "原因是什么", "影响是什么", "有哪些", "会导致什么")
    for e in entities:
        name = (e.get("name") or "").strip()
        if not name:
            continue
        if name.endswith("？") or name.endswith("?") or name.startswith(question_starts):
            results.append(e)

    return results


def _build_paths(neo4j_service, name: str, depth: int = 2) -> List[str]:
    """生成以实体名称为中心的子图路径字符串列表，仅保留两跳路径。"""
    paths = neo4j_service.get_format_subgraph_paths(name, depth=depth)
    # 两跳路径示例：A->rel->B->rel->C，包含至少 4 个 "->"
    return [p for p in paths if p.count("->") >= 4]


class QASchema(BaseModel):
    question: str
    answer: str


def _gen_qa_two_hop(entity_name: str, paths: List[str]) -> Dict[str, str]:
    """调用大模型生成基于两跳路径的问答对，返回 {question, answer}。"""
    service = LLMCallService()
    # 强调两跳路径与答案长度，答案不少于 40 字、不超过 120 字；不披露路径本身
    prompt = (
        "你将基于一个知识图谱中的实体与两跳推理路径，生成一个中文问答对。\n"
        "要求：\n"
        "1) 问题围绕该实体，体现两跳推理的因果或影响关系，长度不超过 25 个汉字；\n"
        "2) 答案应基于两跳路径的信息进行归纳，1-2 句话，40-120 个汉字；\n"
        "3) 答案不要直接描述‘根据路径’或‘两跳’等字眼，不披露路径来源；\n"
        "4) 不要编造，无法确定时给出客观说明。\n\n"
        f"实体名称：{entity_name}\n"
        f"两跳路径列表：{paths}\n"
        "请仅输出 JSON：{\"question\": <问题>, \"answer\": <答案>}"
    )

    res = service.call_llm_json(prompt=prompt, json_schema=QASchema)
    if res.get("status") == "success" and "json_content" in res:
        return res["json_content"]
    # 回退：若解析失败，采用保守生成
    return {"question": f"{entity_name}的两跳影响是什么？", "answer": f"与{entity_name}相关的两跳影响需结合现场路径信息判断。"}


def generate_samples(graph_id: str, out_path: str, label: str = None, type_value: str = "问题", limit: int = None) -> None:
    """核心流程：抓取实体 -> 构造路径 -> 生成简短问答 -> 写入 JSON（数组）。"""
    neo4j_service = get_neo4j_service(graph_id=graph_id)

    candidates = _find_question_entities(neo4j_service, label=label, type_values=[type_value])
    if limit is not None:
        candidates = candidates[:max(0, int(limit))]

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    samples: List[Dict[str, Any]] = []
    for e in candidates:
        name = e.get("name")
        if not name:
            continue

        paths = _build_paths(neo4j_service, name, depth=2)
        qa = _gen_qa_two_hop(name, paths)
        sample = {
            "graph_id": graph_id,
            "question_entity_id": e.get("id"),
            "question_entity_name": name,
            "paths": paths,
            "question": qa.get("question", ""),
            "answer": qa.get("answer", ""),
        }
        samples.append(sample)

    # 写入 JSON 数组
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)

    print(f"导出完成，共生成 {len(samples)} 条样本 -> {out_path}")


def main():
    parser = argparse.ArgumentParser(description="导出类型为‘问题’实体的二跳子图问答样本（JSON 数组）")
    parser.add_argument("--graph-id", required=True, help="目标图谱 graph_id")
    parser.add_argument("--out", default="outputs/qa_samples.json", help="输出文件路径（JSON）")
    parser.add_argument("--label", default=None, help="实体节点的标签（默认 None，表示不限定标签）")
    parser.add_argument("--type", default="问题", help="用于过滤的实体类型（默认 ‘问题’）")
    parser.add_argument("--limit", type=int, default=None, help="可选：限制导出的实体数量上限")

    args = parser.parse_args()
    generate_samples(
        graph_id=args.graph_id,
        out_path=args.out,
        label=args.label,
        type_value=args.type,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()