"""
Hybrid Retriever: Dense (ChromaDB) + Sparse (BM25) 加权融合检索。

用法:
    retriever = HybridRetriever(alpha=0.5)
    retriever.build_index(documents)  # 构建 BM25 索引
    results = retriever.search(query, top_k=5, dense_scores=chroma_scores)
"""

import re
import math
from typing import List, Dict, Tuple, Optional
from rag import Document


class BM25Okapi:
    """轻量 BM25 实现，避免外部依赖"""

    def __init__(self, corpus: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.N = len(corpus)
        self.avgdl = sum(len(doc) for doc in corpus) / max(self.N, 1)
        self.df = {}  # document frequency
        self.idf = {}
        self._initialize()

    def _initialize(self):
        for doc in self.corpus:
            seen = set()
            for word in doc:
                if word not in seen:
                    self.df[word] = self.df.get(word, 0) + 1
                    seen.add(word)
        for word, freq in self.df.items():
            self.idf[word] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1.0)

    def get_scores(self, query: List[str]) -> List[float]:
        scores = []
        for doc in self.corpus:
            score = 0.0
            doc_len = len(doc)
            for term in query:
                if term in self.idf:
                    tf = doc.count(term)
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                    score += self.idf[term] * numerator / denominator
            scores.append(score)
        # Normalize to [0, 1]
        max_score = max(scores) if scores and max(scores) > 0 else 1.0
        return [s / max_score for s in scores]


class HybridRetriever:
    """Dense + Sparse 混合检索器"""

    def __init__(self, alpha: float = 0.5):
        """
        Args:
            alpha: dense 向量权重 (0~1)，剩余 (1-alpha) 为 BM25 权重。
                   协议/精确查询建议 alpha=0.4，通用查询 alpha=0.5。
        """
        self.alpha = alpha
        self.bm25_index: Optional[BM25Okapi] = None
        self.documents: List[Document] = []
        self.doc_ids: List[str] = []

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """简单分词：小写 + 非字母数字分割"""
        return re.findall(r'\w+', text.lower())

    def build_index(self, documents: List[Document]):
        """构建 BM25 索引"""
        self.documents = documents
        self.doc_ids = [doc.id for doc in documents]
        corpus = [self.tokenize(doc.text) for doc in documents]
        self.bm25_index = BM25Okapi(corpus)

    @property
    def is_ready(self) -> bool:
        return self.bm25_index is not None

    def search(self, query: str, top_k: int = 5,
               dense_scores: Optional[Dict[str, float]] = None) -> List[Tuple[str, float]]:
        """
        混合检索：融合 dense (ChromaDB) + sparse (BM25) 分数。

        Args:
            query: 查询字符串
            top_k: 返回结果数量
            dense_scores: doc_id → dense_score 的映射（来自 ChromaDB 检索结果）

        Returns:
            [(doc_id, combined_score), ...] 按分数降序排列
        """
        if not self.bm25_index:
            # BM25 未初始化，退化为纯 dense
            if dense_scores:
                sorted_ids = sorted(dense_scores.items(), key=lambda x: x[1], reverse=True)
                return sorted_ids[:top_k]
            return []

        # BM25 分数
        tokenized = self.tokenize(query)
        bm25_raw = self.bm25_index.get_scores(tokenized)
        bm25_scores = {
            self.doc_ids[i]: bm25_raw[i]
            for i in range(min(len(bm25_raw), len(self.doc_ids)))
        }

        # 合并所有候选 ID
        all_ids = set(bm25_scores.keys())
        if dense_scores:
            all_ids.update(dense_scores.keys())

        # 加权融合
        combined = {}
        for doc_id in all_ids:
            sparse = bm25_scores.get(doc_id, 0.0)
            dense = dense_scores.get(doc_id, 0.0) if dense_scores else 0.0
            combined[doc_id] = (1 - self.alpha) * sparse + self.alpha * dense

        sorted_results = sorted(combined.items(), key=lambda x: x[1], reverse=True)
        return sorted_results[:top_k]

    def update_alpha(self, alpha: float):
        """动态调整 dense/sparse 权重"""
        self.alpha = max(0.0, min(1.0, alpha))
