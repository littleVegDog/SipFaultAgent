import json
import re
from openai import OpenAI
from tools import SIPDiagnosticTools
from rag import SbcRAG
from prompts import SYSTEM_PROMPT
from logger_config import user_print, info_print, debug_print, error_print, warn_print

class SipFaultDiagAgent:
    def __init__(self, llm_client:OpenAI, tools:SIPDiagnosticTools, rag: SbcRAG, LLM_MODEL_ID,
                 input_enhancer=None, max_memory_turns: int = 20):
        self.llm_client = llm_client
        self.tools = tools
        self.rag = rag
        self.memory = []
        self.model_id = LLM_MODEL_ID
        self.input_enhancer = input_enhancer
        self.max_memory_turns = max_memory_turns  # 限制对话轮数，防止 OOM

    def _call_llm(self)->dict:
        response= self.llm_client.chat.completions.create(
            model=self.model_id,
            messages=self.memory,
            temperature=0.2,
            response_format = {"type":"json_object"}  # ✅ 添加 JSON 格式约束
        )
        raw = response.choices[0].message.content
        debug_print(f"LLM原始响应: {raw}")  # 使用调试日志
        try:
            return json.loads(raw)
        except json.decoder.JSONDecodeError as e:
            error_print(f"JSON解析失败，原始内容: {raw}")
            # 如果使用了 response_format 但仍然失败，这是一个严重错误
            return {"action": "final_answer", "conclusion": "LLM 响应格式错误，无法继续推理。", "sources": []}

    def _execute_tool(self, tool_name:str, tool_input)->str:
        if tool_name == "rag_search":
            # tool_input 可以是字符串或字典
            if isinstance(tool_input, str):
                query = tool_input
                filter_meta = None
                top_k = 3
            else:
                query = tool_input.get("query", "")
                filter_meta = tool_input.get("filter")
                top_k = tool_input.get("top_k", 3)

            docs = self.rag.search(
                    query=query,
                    top_k=top_k,
                    filter_meta=filter_meta,
                    input_enhancer=self.input_enhancer
                )

            return "\n".join(f"[{doc.id}] {doc.text}" for doc in docs)

        return f"未知工具 {tool_name}"

    def run(self, enhance_query:str, keywords: list = None):
        self.memory = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": enhance_query}
        ]
        # 如果有关键词，可以在记忆的第一条用户消息中附带提示
        if keywords:
            self.memory.append({
                "role": "user",
                "content": f"注意：以下英文关键词可能有助于检索知识库：{', '.join(keywords)}"
            })

        info_print("开始故障定界推理...")

        step = 0
        while True:
            step += 1
            debug_print(f"第 {step} 步推理")
            response  = self._call_llm()

            if response.get("action") == "final_answer":
                if response.get("响应格式错误"):
                    # 向记忆中添加一条提示，要求 LLM 重新输出
                    self.memory.append({
                        "role": "user",
                        "content": "你上次输出的格式非法，请重新输出，只包含一个 JSON 对象，不要任何解释。"
                    })
                    continue
                else:
                    info_print("思考结果：已定位故障，准备输出结论")
            else:
                info_print(f"思考结果：调用工具 {response['tool']}，输入: {response.get('input')}")

            if response.get("action") == "final_answer":
                conclusion = response["conclusion"]
                sources = response.get("sources", [])
                info_print("最终结论已生成")
                return conclusion, sources

            tool_name = response["tool"]
            tool_input = response["input"]

            if isinstance(tool_input, str) and tool_input.strip().startswith("{"):
                try:
                    tool_input = json.loads(tool_input)
                except json.JSONDecodeError:
                    pass  # 解析失败保持原字符串

            debug_print(f"调用工具: {tool_name}")
            result = self._execute_tool(tool_name, tool_input)
            # 可视化观察
            debug_print(f"工具返回: {result[:200]}{'...' if len(result) > 200 else ''}")


            #当前行动与结果添加到上下文中
            self.memory.append({
                "role": "assistant",
                "content": f"使用工具{tool_name}，输入{json.dumps(tool_input)}"
            })
            self.memory.append({
                "role": "tool",       # ✅ 修复：工具返回应该使用 "tool" 角色
                "content": f"工具结果：{result}"
            })

            # 内存管理：超过 max_memory_turns 轮后，保留 system prompt + 最近 N 轮
            max_msgs = 2 + self.max_memory_turns * 2  # system + user query + N × (assistant + tool)
            if len(self.memory) > max_msgs:
                # 保留第 0 条 (system) + 第 1 条 (user query) + 最后 max_msgs-2 条
                self.memory = self.memory[:2] + self.memory[-(max_msgs - 2):]
                debug_print(f"记忆裁剪: {len(self.memory)} 条 (上限 {max_msgs})")
