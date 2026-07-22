import json
from openai import OpenAI
from typing import List, Dict, Optional
from query_expander import QueryExpander

class InputEnhancer:
    def __init__(self, llm_client: OpenAI, llm_model_id: str) -> None:
        self.llm_client = llm_client
        self.model_id = llm_model_id
        self.query_expander = QueryExpander(llm_client, llm_model_id)

    def enhance(self, raw_query: str) -> Dict[str, any]:
        """
        一次性完成查询增强：生成扩展表述 + 提取关键词。
        返回 {"expanded_queries": [...], "keywords": [...]}
        """
        # 使用智能扩展器
        result = self.query_expander.expand_query(raw_query)

        return {
            "expanded_queries": result.get("expanded_queries", [raw_query]),
            "keywords": result.get("keywords", [])
        }
