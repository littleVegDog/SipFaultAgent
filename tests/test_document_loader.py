"""document_loader 单元测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from chunker import Chunk
from document_loader import (
    chunk_text, parse_markdown_with_yaml, RawDocument,
    is_meaningless_chunk, clean_chunk_text, semantic_chunk
)


class TestChunkText:
    def test_basic_chunk(self):
        result = chunk_text("hello world " * 100, chunk_size=50, overlap=10)
        assert len(result) > 1
        assert all(isinstance(c, str) for c in result)

    def test_short_text(self):
        result = chunk_text("short", chunk_size=50, overlap=10)
        assert len(result) == 1

    def test_empty_text(self):
        result = chunk_text("", chunk_size=50, overlap=10)
        assert len(result) == 0


class TestCleanChunkText:
    def test_removes_triple_newlines(self):
        result = clean_chunk_text("line1\n\n\n\nline2")
        assert "\n\n\n\n" not in result

    def test_preserves_content(self):
        text = "SIP 401 Unauthorized means auth failed"
        result = clean_chunk_text(text)
        assert "SIP" in result
        assert "401" in result

    def test_empty_input(self):
        assert clean_chunk_text("") == ""


class TestIsMeaninglessChunk:
    def test_too_short(self):
        assert is_meaningless_chunk("hi", {"type": "rfc"})

    def test_acknowledgements(self):
        assert is_meaningless_chunk("Some text in acknowledgements section",
                                     {"type": "rfc", "section_title": "Acknowledgements"})

    def test_valid_chunk(self):
        # RFC 类型最小长度 80 字符
        text = "The 401 response indicates that the request requires user authentication and the server MUST include a WWW-Authenticate header."
        assert not is_meaningless_chunk(text, {"type": "rfc", "section_title": "401 Unauthorized"})


class TestSemanticChunk:
    def test_rfc_type_returns_list_of_chunk(self):
        text = "1. Introduction\nThis is SIP.\n\n2. Methods\nREGISTER and INVITE.\n\n21.4.2 401 Unauthorized\nThe 401 response requires auth.\n\n403 Forbidden\nThe 403 response means access denied.\n\n4. Overview\nSIP protocol overview."
        meta = {"type": "rfc", "title": "RFC3261"}
        result = semantic_chunk(text, meta)
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(c, Chunk) for c in result)

    def test_rfc_chunk_has_metadata(self):
        text = "1. Introduction\nThis introduces SIP.\n\n21.4.2 401 Unauthorized\nThe 401 response requires auth."
        meta = {"type": "rfc", "title": "RFC3261"}
        result = semantic_chunk(text, meta)
        for chunk in result:
            assert hasattr(chunk, 'content')
            assert hasattr(chunk, 'metadata')

    def test_case_type_returns_chunks(self):
        text = "## 现象\n注册失败 403\n## 原因\nACL 配置错误\n## 解决方法\n调整 ACL"
        meta = {"type": "case", "title": "case_001"}
        result = semantic_chunk(text, meta)
        assert isinstance(result, list)
        assert all(isinstance(c, Chunk) for c in result)

    def test_default_type_returns_chunks(self):
        text = "This is a generic document with some text.\n" * 20
        meta = {"type": "default"}
        result = semantic_chunk(text, meta)
        assert isinstance(result, list)
        assert all(isinstance(c, Chunk) for c in result)


class TestParseMarkdownWithYaml:
    def test_extracts_yaml_header(self):
        md = "---\ntype: rfc\ntitle: RFC3261\n---\n\n1. Introduction\nContent here."
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix='.md', text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(md)
            result = parse_markdown_with_yaml(path)
            assert result.meta == {"type": "rfc", "title": "RFC3261"}
            assert "1. Introduction" in result.content
        finally:
            os.unlink(path)

    def test_no_yaml_header(self):
        md = "1. Introduction\nContent without YAML header."
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix='.md', text=True)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(md)
            result = parse_markdown_with_yaml(path)
            assert result.meta == {}
            assert "1. Introduction" in result.content
        finally:
            os.unlink(path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
