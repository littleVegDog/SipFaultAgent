import re
from typing import List, Dict
from logger_config import info_print, debug_print, error_print, warn_print

class RouterAgent:
    """
    Query Routing系统，用于区分协议查询和故障诊断等不同类型的查询
    实现Router Agent架构，将查询分为protocol_query和fault_diagnosis两个路径
    """

    def __init__(self):
        # 协议查询关键词 - 增加更多高精度关键词
        self.protocol_keywords = [
            "是什么", "含义", "意思", "解释", "说明", "定义", "文档",
            "状态码", "错误码", "码值", "响应", "返回", "描述",
            "协议", "SIP", "RFC", "3GPP", "信令", "媒体", "注册",
            "Invite", "200", "403", "401", "404", "500"
        ]

        # 故障诊断关键词 - 更具诊断性质的关键词
        self.diagnosis_keywords = [
            "失败", "错误", "问题", "故障", "怎么", "如何", "为什么",
            "出现", "报错", "提示", "卡住", "无响应", "异常", "中断",
            "掉线", "连接", "登录", "认证"
        ]

        # 协议相关词 - 这些词本身就是协议相关
        self.protocol_related_words = [
            "sip", "sbc", "rfc", "3gpp", "协议", "连接", "注册", "信令", "媒体",
            "呼叫", "invite", "200", "403", "401", "404", "500"
        ]

        # 诊断性特征词
        self.diagnosis_features = [
            "怎么", "如何", "为什么", "出现", "报错", "提示", "检查", "调试"
        ]

    def route_query(self, query: str) -> str:
        """
        根据查询内容判断处理类型

        Args:
            query: 用户输入的查询语句

        Returns:
            str: 处理类型，"protocol_query" or "fault_diagnosis"
        """
        query_lower = query.lower().strip()

        # 如果为空或长度过短，返回协议查询
        if not query_lower or len(query_lower) < 3:
            debug_print(f"输入过短: '{query}', 返回默认协议查询")
            return "protocol_query"

        # 计算各类关键词出现频率
        protocol_score = 0
        diag_score = 0
        protocol_word_score = 0
        diag_feature_score = 0

        # 统计协议关键词
        for keyword in self.protocol_keywords:
            if keyword in query_lower:
                protocol_score += 1

        # 统计诊断关键词
        for keyword in self.diagnosis_keywords:
            if keyword in query_lower:
                diag_score += 1

        # 统计协议相关词汇
        for word in self.protocol_related_words:
            if word in query_lower:
                protocol_word_score += 1

        # 统计诊断特征词
        for word in self.diagnosis_features:
            if word in query_lower:
                diag_feature_score += 1

        # 计算置信度分数
        protocol_confidence = protocol_score * 2 + protocol_word_score * 3 + diag_feature_score * 0.5
        diag_confidence = diag_score * 2 + diag_feature_score * 3 + protocol_word_score * 0.5

        # 判断逻辑优化：
        # 1. 如果协议相关词较多且清晰，直接协议查询
        # 2. 如果诊断特征明显，区分度高，故障诊断
        # 3. 如果有矛盾判断，使用更保守的策略
        # 4. 如果无法判断，或者为简单问题，返回协议查询，避免代理处理

        # 协议查询优先的判断条件：
        if (protocol_word_score >= 2 or
            (protocol_score >= 1 and protocol_word_score >= 1) or
            (protocol_confidence > diag_confidence and protocol_confidence > 3)):
            debug_print(f"查询分类: '{query}' -> 协议查询 (置信度协议={protocol_confidence:.2f}, 诊断={diag_confidence:.2f})")
            return "protocol_query"

        # 故障诊断判断条件：
        if (diag_score >= 1 or
            diag_feature_score >= 1 or
            (diag_confidence > protocol_confidence and diag_confidence > 3)):
            debug_print(f"查询分类: '{query}' -> 故障诊断 (置信度协议={protocol_confidence:.2f}, 诊断={diag_confidence:.2f})")
            return "fault_diagnosis"

        # 保守措施：如果是简短而抽象的问题，倾向协议查询
        if len(query_lower) < 10:
            debug_print(f"简短查询处理: '{query}' -> 协议查询")
            return "protocol_query"

        # 其他情况默认返回协议查询（更保守）
        debug_print(f"默认处理: '{query}' -> 协议查询")
        return "protocol_query"

    def is_protocol_query(self, query: str) -> bool:
        """
        判断是否为协议查询
        """
        return self.route_query(query) == "protocol_query"

    def is_fault_diagnosis(self, query: str) -> bool:
        """
        判断是否为故障诊断查询
        """
        return self.route_query(query) == "fault_diagnosis"

    def get_routing_confidence(self, query: str) -> Dict[str, float]:
        """
        获取路由判断的置信度信息
        """
        query_lower = query.lower().strip()
        if not query_lower or len(query_lower) < 3:
            return {"protocol": 0.5, "diagnosis": 0.5}

        protocol_score = 0
        diag_score = 0
        protocol_word_score = 0
        diag_feature_score = 0

        for keyword in self.protocol_keywords:
            if keyword in query_lower:
                protocol_score += 1

        for keyword in self.diagnosis_keywords:
            if keyword in query_lower:
                diag_score += 1

        for word in self.protocol_related_words:
            if word in query_lower:
                protocol_word_score += 1

        for word in self.diagnosis_features:
            if word in query_lower:
                diag_feature_score += 1

        protocol_confidence = protocol_score * 2 + protocol_word_score * 3 + diag_feature_score * 0.5
        diag_confidence = diag_score * 2 + diag_feature_score * 3 + protocol_word_score * 0.5

        # 归一化到0-1之间
        max_score = max(protocol_confidence, diag_confidence, 1)
        return {
            "protocol": protocol_confidence / max_score if max_score > 0 else 0.5,
            "diagnosis": diag_confidence / max_score if max_score > 0 else 0.5
        }
