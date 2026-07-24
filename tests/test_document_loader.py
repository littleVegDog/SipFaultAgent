"""document_loader 单元测试（parse + 数据清洗）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from document_loader import (
    parse_markdown_with_yaml, RawDocument,
    is_meaningless_chunk, clean_chunk_text
)


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
        text = "The 401 response indicates that the request requires user authentication and the server MUST include a WWW-Authenticate header."
        assert not is_meaningless_chunk(text, {"type": "rfc", "section_title": "401 Unauthorized"})


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
