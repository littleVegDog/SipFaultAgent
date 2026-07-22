import json
import re
from typing import List, Dict, Optional
from openai import OpenAI
from logger_config import user_print, info_print, debug_print, error_print, warn_print

class QueryExpander:
    """Query Expansion 查询增强器"""

    # 预定义的协议关键词 -> 扩展映射规则（涵盖核心SIP协议相关）
    PROTOCOL_RULES = {
        # 常见错误码扩展
        "403": ["Forbidden", "SIP response code 403", "authentication failure", "access denied"],
        "401": ["Unauthorized", "SIP response code 401", "auth failed", "unauthorized"],
        "404": ["Not Found", "SIP response code 404", "user not found", "not exists"],
        "200": ["OK", "SIP response code 200", "success", "confirmed"],
        "400": ["Bad Request", "SIP response code 400", "malformed request"],
        "486": ["Busy Here", "SIP response code 486", "user busy"],
        "487": ["Request Terminated", "SIP response code 487", "call canceled"],
        "500": ["Server Internal Error", "SIP response code 500", "server error"],
        "503": ["Service Unavailable", "SIP response code 503", "service unavailable"],

        # 核心协议方法
        "invite": ["INVITE request", "SIP INVITE method", "call setup", "session initiation"],
        "register": ["REGISTER request", "SIP REGISTER method", "registration", "user registration"],
        "subscribe": ["SUBSCRIBE request", "SIP SUBSCRIBE method", "subscription", "event subscription"],
        "notify": ["NOTIFY request", "SIP NOTIFY method", "notification", "event notification"],
        "options": ["OPTIONS request", "SIP OPTIONS method", "options", "server capabilities"],
        "bye": ["BYE request", "SIP BYE method", "call end", "session termination"],
        "cancel": ["CANCEL request", "SIP CANCEL method", "call cancel", "request cancelation"],
        "message": ["MESSAGE request", "SIP MESSAGE method", "instant message", "text message"],
        "info": ["INFO request", "SIP INFO method", "information", "session info"],
        "prack": ["PRACK request", "SIP PRACK method", "provisional response ACK"],

        # 协议相关术语
        "sip": ["SIP protocol", "Session Initiation Protocol", "session protocol", "voice protocol"],
        "rfc": ["RFC specification", "Request for Comments", "protocol specification", "RFC standard"],
        "sbc": ["SBC", "Session Border Controller", "session border control", "media gateway"],
        "ims": ["IMS", "IP Multimedia Subsystem", "IP multimedia framework"],
        "pdu": ["PDU", "Protocol Data Unit", "data unit", "message unit"],
        "tftp": ["TFTP", "Trivial File Transfer Protocol", "file transfer"],
        "rtp": ["RTP", "Real-time Transport Protocol", "media streaming", "voice streaming"],
        "rtcp": ["RTCP", "Real-time Transport Control Protocol", "media control"],
        "dtmf": ["DTMF", "Dual-Tone Multi-Frequency", "dial tone", "dialing signal"],
        "codec": ["Codec", "Codec format", "audio codec", "video codec"],
        "session": ["Session", "Call session", "media session", "voice session"],

        # 核心业务词条
        "authentication": ["authentication", "auth", "user authentication", "access control"],
        "authorization": ["authorization", "authz", "access rights", "permission"],
        "call": ["call", "session", "voice call", "telephone call"],
        "media": ["media", "audio", "voice", "video", "streaming"],
        "gateway": ["gateway", "media gateway", "session border controller", "sip gateway"],
        "trunk": ["trunk", "signaling trunk", "media trunk", "voice trunk"],
        "user": ["user", "subscriber", "endpoint", "phone"],
        "device": ["device", "endpoint", "terminal", "phone"],
        "server": ["server", "sip server", "proxy server", "registrar server"],
        "client": ["client", "sip client", "user agent", "endpoint"],

        # 设备问题关键词
        "failure": ["failure", "failed", "error", "issue"],
        "problem": ["problem", "issue", "trouble", "difficulty"],
        "reject": ["reject", "rejection", "denial", "forbidden"],
        "timeout": ["timeout", "time out", "connection timeout", "request timeout"],
        "busy": ["busy", "user busy", "busy here", "unavailable"],
        "offline": ["offline", "unreachable", "not available", "disconnected"],
        "connection": ["connection", "connectivity", "network connection", "call connection"],
    }

    def __init__(self, llm_client: OpenAI, llm_model_id: str):
        self.llm_client = llm_client
        self.model_id = llm_model_id

    def expand_query(self, query: str) -> Dict[str, any]:
        """
        智能查询扩展

        Args:
            query: 原始查询

        Returns:
            Dict: 包含扩展查询和关键词的字典
        """
        # 1. 判断查询复杂度
        if self._is_simple_query(query):
            # 2. 简单查询使用规则扩展
            return self._rule_expand(query)
        else:
            # 3. 复杂查询使用LLM扩展
            return self._llm_expand(query)

    def _is_simple_query(self, query: str) -> bool:
        """判断是否为简单查询（短且关键词明确）"""
        query = query.lower().strip()

        # 简单查询特征判断（综合多个因素）

        # 1. 长度特征
        if len(query) > 30:  # 太长的查询通常复杂
            return False

        # 2. 关键字分析
        query_words = query.split()

        # 3. 检查是否包含协议相关术语
        protocol_words = list(self.PROTOCOL_RULES.keys())
        keyword_matches = []
        for word in query_words:
            # 精确匹配和前缀匹配
            for rule_key in protocol_words:
                if word == rule_key or word.startswith(rule_key) or rule_key.startswith(word):
                    keyword_matches.append(rule_key)
                    break

        # 4. 判断标准：匹配3个以上协议关键词或占字符比例超过30%
        if len(keyword_matches) >= 3:
            return True

        # 5. 进一步判断：如果查询字符串中有常见协议术语
        common_terms = ['sip', '403', '401', '404', '200', 'register', 'invite', 'rfc']
        term_count = sum(1 for term in common_terms if term in query.lower())

        if term_count >= 2:  # 如果包含2个以上关键词则认为简单
            return True

        # 6. 采用比例判断准则：关键术语占比超过30%
        if keyword_matches and len(query) > 0:
            # 计算关键术语的总长度
            key_chars = sum(len(match) for match in keyword_matches)
            ratio = key_chars / len(query)
            if ratio >= 0.3:  # 占比30%以上认为简单
                return True

        return False

    def _rule_expand(self, query: str) -> Dict[str, any]:
        """本地规则扩展"""
        # 提取协议相关关键词
        query_lower = query.lower()
        keywords = []
        expanded_queries = [query]  # 保留原查询

        # 匹配规则 - 全面匹配关键词
        matched_rules = set()
        for keyword, expansions in self.PROTOCOL_RULES.items():
            if keyword in query_lower:
                keywords.append(keyword)
                matched_rules.add(keyword)
                # 添加相关扩展
                for expansion in expansions:
                    if expansion not in expanded_queries:
                        expanded_queries.append(expansion)

        # 词频统计：找出高频匹配词
        word_freq = {}
        query_words = query_lower.split()
        for word in query_words:
            for rule_key in self.PROTOCOL_RULES.keys():
                if rule_key in word or word in rule_key:
                    word_freq[rule_key] = word_freq.get(rule_key, 0) + 1

        # 基于词频添加更丰富的扩展
        top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:2]
        for word_key, freq in top_words:
            if word_key not in matched_rules:
                for expansion in self.PROTOCOL_RULES.get(word_key, []):
                    if expansion not in expanded_queries:
                        expanded_queries.append(expansion)

        # 如果没匹配到关键词，在无匹配情况下的改进策略
        if not matched_rules and len(query) < 30:
            # 简单的语义推断
            if any(word in query_lower for word in ["sip", "sip protocol"]):
                expanded_queries.extend(["SIP protocol", "Session Initiation Protocol"])
            elif any(word in query_lower for word in ["register", "registration"]):
                expanded_queries.extend(["registration", "user registration"])
            elif any(word in query_lower for word in ["invite", "call"]):
                expanded_queries.extend(["INVITE", "call setup"])

        # 确保至少有原查询和一个扩展
        if len(expanded_queries) <= 1:
            # 添加更广泛的协议相关扩展
            expanded_queries.extend([
                f"关于{query}的处理方法",
                f"SIP协议与{query}的关系"
            ])

        return {
            "expanded_queries": expanded_queries,
            "keywords": keywords
        }

    def _llm_expand(self, query: str) -> Dict[str, any]:
        """LLM扩展（复杂查询）"""
        try:
            prompt = f"""你是一个核心网运维专家。请将以下用户口语化的问题转换成一个完整的故障排查请求，
            并生成 3~5 个不同的检索表述（捕捉不同角度：协议方法、错误码、原因描述等）。

            用户原始问题：{query}

            请严格按照以下 JSON 格式输出：
            {{
                "expanded_queries": [
                    "完整专业的故障排查描述，保留原始信息并补充可能的协议层面",
                    "从错误码角度的表述",
                    "从协议方法角度的表述",
                    "从原因描述角度的表述"
                ],
                "keywords": ["关键词1", "关键词2"]
            }}

            要求：
            - expanded_queries 至少包含第一条（增强后的完整描述）
            - 每个扩展 query 要有不同的表述角度
            - 保留所有原始信息（设备标识、IP、错误码等）
            - 用专业术语描述，但不要添加没有依据的猜测
            - 输出纯 JSON，不要其他文字"""

            response = self.llm_client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            # 确保至少包含原始查询
            if result.get("expanded_queries"):
                if query not in result["expanded_queries"]:
                    result["expanded_queries"].insert(0, query)

            return {
                "expanded_queries": result.get("expanded_queries", [query]),
                "keywords": result.get("keywords", [])
            }

        except Exception as e:
            # 出错时返回基本扩展
            error_print(f"LLM扩展失败，使用默认扩展: {e}")
            return {
                "expanded_queries": [query, f"关于{query}的协议规范"],
                "keywords": []
            }
