"""
简化的大模型调用接口，使用 langchain 支持返回 JSON
"""
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel

load_dotenv()

class LLMCallService:
    def __init__(self, model_name: str = None):
        self.model_name = model_name or os.getenv("MODEL", "gpt-4o")
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=0.7,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_API_BASE_URL")
        )
    
    def call_llm(self, prompt: str, system_message: str = None) -> Dict[str, Any]:
        """简单的 LLM 调用"""
        try:
            messages = []
            if system_message:
                messages.append(SystemMessage(content=system_message))
            messages.append(HumanMessage(content=prompt))
            
            response = self.llm.invoke(messages)
            return {"status": "success", "content": response.content}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def call_llm_json(self, prompt: str, system_message: str = None, 
                     json_schema: Optional[BaseModel] = None) -> Dict[str, Any]:
        """调用 LLM 并返回 JSON 格式，使用 LangChain 的 JsonOutputParser"""
        try:
            # 创建 JSON 输出解析器
            parser = JsonOutputParser(pydantic_object=json_schema) if json_schema else JsonOutputParser()
            
            # 构建消息列表
            messages = []
            if system_message:
                messages.append(SystemMessage(content=system_message))
            
            # 添加格式说明到用户消息中
            format_instructions = parser.get_format_instructions()
            full_prompt = f"{prompt}\n\n{format_instructions}"
            messages.append(HumanMessage(content=full_prompt))
            
            # 调用模型并解析结果
            response = self.llm.invoke(messages)
            parsed_result = parser.parse(response.content)
            
            return {"status": "success", "content": response.content, "json_content": parsed_result}
        except Exception as e:
            return {"status": "error", "error": str(e)}

# 便捷函数
def quick_call(prompt: str, return_json: bool = False) -> Dict[str, Any]:
    service = LLMCallService()
    return service.call_llm_json(prompt) if return_json else service.call_llm(prompt)