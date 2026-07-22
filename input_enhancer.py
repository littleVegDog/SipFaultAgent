import json
from openai import OpenAI

class InputEnhancer:
    def __init__(self, llm_client: OpenAI, model: str):
        self.client = llm_client
        self.model = model

    def enhance(self, raw_query: str) -> dict:
        prompt = f"""你是一个SIP运维专家。请将用户口语化的问题转化为专业的故障排查请求，并提取关键的英文技术关键词。

用户原始问题：{raw_query}

输出格式（JSON）：
{{
    "enhanced_query": "完整的专业排查描述",
    "keywords": ["关键词1", "关键词2"]
}}
只输出 JSON，不要任何解释。"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        try:
            return json.loads(response.choices[0].message.content)
        except Exception:
            return {"enhanced_query": raw_query, "keywords": []}