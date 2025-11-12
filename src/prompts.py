def get_llm_re_entity_prompt(query, entity_list) -> str:
    llm_re_entity_prompt = f"""
你是一个专业的知识图谱实体识别器。
给你提供一个实体列表和一个用户查询，请你识别出这个查询中可能出现的实体！
结果请返回json格式
# 
要是你觉得不存在，那么entity对应为空字符串

文本：{query}

实体列表：
{entity_list}
"""
    return llm_re_entity_prompt


def get_llm_qa_prompt(query, paths) -> str:
    llm_qa_prompt = f"""
你是一个钢铁行业知识回答机器人，你负责专业的回答用户提问的问题。
此外，我们会给你提供一些可能与该问题相关的推理路径，你看看能不能从路径中找到该问题的答案。
如果能找到，那么请你根据路径中的信息，回答用户的问题。
如果不能找到，那么请你回答用户的问题，但是要注意，你不能编造答案。

请注意：
1. 答案请不要提到说，你是通过给你提供的路径回答的，明白吧，就是你就正常回答，不要说"根据提供的路径，所以答案是什么"。
2. 你需要返回JSON格式的结果，包含两个字段：
   - "answer": 你对用户问题的回答
   - "referenced_paths": 你在回答问题时参考了哪些推理路径（如果没有参考任何路径，则返回空列表）

用户问题：{query}

可能有用的推理路径：
{paths}

请返回格式如下的JSON：
{{
  "answer": "你的回答内容",
  "referenced_paths": ["实体1->关系类型->实体2", "实体3->关系类型->实体4"]
}}
"""
    return llm_qa_prompt