import os
from sentence_transformers import CrossEncoder
from config import RERANKER_MODEL


class BGEReranker:
    def __init__(self, model_path: str = None):
        path = model_path or RERANKER_MODEL
        self.model = CrossEncoder(path, max_length=512)

    def rerank(self, query: str, documents: list, top_k: int = 5) -> list:
        # Step 1: CrossEncoder 基础打分
        pairs = [(query, doc.text) for doc in documents]
        base_scores = self.model.predict(pairs)

        # Step 2: Metadata boost（按协议字段匹配叠加权重）
        query_lower = query.lower()
        boosted = []
        for doc, base in zip(documents, base_scores):
            boost = 0.0
            meta = doc.meta

            # 响应码匹配：查询含 "401"，文档标记 response_code="401"
            rc = meta.get('response_code', '')
            if rc and rc in query_lower:
                boost += 2.0

            # 协议匹配：查询含 "SIP"，文档标记 protocol="SIP"
            proto = meta.get('protocol', '')
            if proto and proto.lower() in query_lower:
                boost += 1.5

            # 章节标题词重叠
            st = meta.get('section_title', '')
            if st:
                title_words = set(st.lower().split())
                query_words = set(query_lower.split())
                overlap = len(title_words & query_words)
                if overlap > 0:
                    boost += 0.5 * overlap

            # 关键词匹配
            kw = meta.get('keywords', [])
            if isinstance(kw, list):
                kw_matches = sum(1 for k in kw if k.lower() in query_lower)
                boost += 0.3 * kw_matches

            boosted.append(base + boost)

        # Step 3: 按增强分数重排
        scored = sorted(zip(documents, boosted), key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in scored[:top_k]]
