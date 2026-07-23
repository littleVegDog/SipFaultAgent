"""BM25Okapi / HybridRetriever 单元测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hybrid_retriever import BM25Okapi, HybridRetriever
from rag import Document


class TestBM25Okapi:
    def test_init_with_empty_corpus(self):
        bm25 = BM25Okapi([])
        assert bm25.N == 0
        assert bm25.avgdl == 0

    def test_init_builds_idf(self):
        corpus = [["hello", "world"], ["hello", "test"]]
        bm25 = BM25Okapi(corpus)
        assert "hello" in bm25.idf
        assert "world" in bm25.idf
        assert "test" in bm25.idf

    def test_scores_length_matches_corpus(self):
        corpus = [["hello", "world"], ["foo", "bar"], ["hello", "foo", "bar"]]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(["hello"])
        assert len(scores) == 3

    def test_scores_normalized_to_one(self):
        corpus = [["hello", "world"], ["hello", "test"]]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(["hello"])
        assert max(scores) <= 1.0
        assert min(scores) >= 0.0

    def test_exact_match_scores_higher(self):
        corpus = [["hello", "world"], ["unrelated", "terms"]]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(["hello"])
        assert scores[0] > scores[1]

    def test_missing_term_scores_zero(self):
        corpus = [["hello", "world"]]
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(["nonexistent"])
        assert scores[0] == 0.0

    def test_k1_b_parameters_change_scores(self):
        corpus = [["hello", "world", "hello", "hello"]]
        bm25_default = BM25Okapi(corpus)
        bm25_k1 = BM25Okapi(corpus, k1=2.0, b=0.5)
        s1 = bm25_default.get_scores(["hello"])
        s2 = bm25_k1.get_scores(["hello"])
        assert s1 != s2


class TestHybridRetriever:
    def make_docs(self, texts):
        return [Document(id=f"doc_{i}", text=t, meta={}) for i, t in enumerate(texts)]

    def test_init_default_alpha(self):
        hr = HybridRetriever()
        assert hr.alpha == 0.5
        assert not hr.is_ready

    def test_is_ready_after_build(self):
        hr = HybridRetriever()
        docs = self.make_docs(["hello world", "foo bar"])
        hr.build_index(docs)
        assert hr.is_ready

    def test_search_returns_top_k(self):
        hr = HybridRetriever(alpha=0.5)
        docs = self.make_docs(["hello world", "foo bar", "hello test", "unrelated"])
        hr.build_index(docs)
        dense = {"doc_0": 0.9, "doc_1": 0.1, "doc_2": 0.5, "doc_3": 0.0}
        results = hr.search("hello", top_k=2, dense_scores=dense)
        assert len(results) <= 2
        assert results[0][0] in ["doc_0", "doc_2"]  # most relevant

    def test_search_without_dense(self):
        hr = HybridRetriever(alpha=0.5)
        docs = self.make_docs(["hello world", "foo bar"])
        hr.build_index(docs)
        results = hr.search("hello", top_k=5)
        assert len(results) > 0

    def test_search_without_index(self):
        hr = HybridRetriever()
        dense = {"doc_0": 0.9}
        results = hr.search("hello", dense_scores=dense)
        assert len(results) <= 1

    def test_tokenize(self):
        result = HybridRetriever.tokenize("Hello, World! SIP/2.0")
        assert "hello" in result
        assert "world" in result
        assert "sip" in result
        assert "2" in result
        assert "0" in result

    def test_update_alpha_bounds(self):
        hr = HybridRetriever()
        hr.update_alpha(2.0)
        assert hr.alpha == 1.0
        hr.update_alpha(-1.0)
        assert hr.alpha == 0.0
        hr.update_alpha(0.7)
        assert hr.alpha == 0.7

    def test_doc_ids_consistent(self):
        hr = HybridRetriever()
        docs = self.make_docs(["text a", "text b", "text c"])
        hr.build_index(docs)
        assert hr.doc_ids == ["doc_0", "doc_1", "doc_2"]
        assert len(hr.documents) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
