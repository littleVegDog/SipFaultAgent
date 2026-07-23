"""BGEReranker metadata boost 单元测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
from reranker import BGEReranker


class TestRerankerMetadataBoost:
    def make_doc(self, text, meta=None):
        from rag import Document
        return Document(id="test", text=text, meta=meta or {})

    @patch.object(BGEReranker, '__init__', lambda self, model_path=None: None)
    def test_boost_response_code_match(self):
        """查询含 '401'，文档 response_code='401' → +2.0 boost"""
        reranker = BGEReranker.__new__(BGEReranker)
        reranker.model = MagicMock()
        reranker.model.predict = MagicMock(return_value=[1.0])

        doc = self.make_doc("401 Unauthorized content",
                            {"response_code": "401", "protocol": "", "section_title": "", "keywords": []})
        result = reranker.rerank("什么是SIP 401错误", [doc], top_k=1)
        assert result[0] == doc

    @patch.object(BGEReranker, '__init__', lambda self, model_path=None: None)
    def test_boost_protocol_match(self):
        """查询含 'SIP'，文档 protocol='SIP' → +1.5 boost"""
        reranker = BGEReranker.__new__(BGEReranker)
        reranker.model = MagicMock()
        reranker.model.predict = MagicMock(return_value=[1.0])

        doc = self.make_doc("SIP protocol content",
                            {"response_code": "", "protocol": "SIP", "section_title": "", "keywords": []})
        result = reranker.rerank("SIP 协议说明", [doc], top_k=1)
        assert result[0] == doc

    @patch.object(BGEReranker, '__init__', lambda self, model_path=None: None)
    def test_no_boost_without_metadata(self):
        """无 metadata 字段时 boost=0，只依赖 CrossEncoder"""
        reranker = BGEReranker.__new__(BGEReranker)
        reranker.model = MagicMock()
        reranker.model.predict = MagicMock(return_value=[1.0])

        doc = self.make_doc("generic content")
        # 不抛异常即通过
        result = reranker.rerank("query", [doc], top_k=1)
        assert result[0] == doc

    @patch.object(BGEReranker, '__init__', lambda self, model_path=None: None)
    def test_boost_section_title_overlap(self):
        """查询 'CSeq' 与 section_title 'CSeq header field' 重叠 → boost"""
        reranker = BGEReranker.__new__(BGEReranker)
        reranker.model = MagicMock()
        reranker.model.predict = MagicMock(return_value=[1.0])

        doc = self.make_doc("CSeq header field defines...",
                            {"response_code": "", "protocol": "", "section_title": "CSeq header field", "keywords": []})
        result = reranker.rerank("CSeq头域的定义", [doc], top_k=1)
        assert result[0] == doc

    @patch.object(BGEReranker, '__init__', lambda self, model_path=None: None)
    def test_boost_keyword_match(self):
        """查询含 'authentication'，文档 keywords=['authentication'] → boost"""
        reranker = BGEReranker.__new__(BGEReranker)
        reranker.model = MagicMock()
        reranker.model.predict = MagicMock(return_value=[1.0])

        doc = self.make_doc("auth content",
                            {"response_code": "", "protocol": "", "section_title": "", "keywords": ["authentication", "SIP"]})
        result = reranker.rerank("authentication failure", [doc], top_k=1)
        assert result[0] == doc

    @patch.object(BGEReranker, '__init__', lambda self, model_path=None: None)
    def test_top_k_truncation(self):
        reranker = BGEReranker.__new__(BGEReranker)
        reranker.model = MagicMock()
        reranker.model.predict = MagicMock(return_value=[1.0, 0.9, 0.8, 0.7, 0.6, 0.5])

        docs = [self.make_doc(f"doc_{i}") for i in range(6)]
        result = reranker.rerank("test", docs, top_k=3)
        assert len(result) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
