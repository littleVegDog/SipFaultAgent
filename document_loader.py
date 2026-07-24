import os
import re
import yaml
import logging
from typing import List
from dataclasses import dataclass
from chunker import RFCChunker


# ==================== 数据清洗相关常量和函数 ====================

MEANINGLESS_SECTIONS = {
    'acknowledgements', 'authors', 'author', 'appendix',
    'table of contents', 'contributors', 'references',
    'revision history', 'intellectual property', 'legal notice',
    'introduction',
}

_MIN_CHUNK_LENGTHS = {
    'case': 40,
    'rfc': 80,
    '3gpp': 80,
    'product_doc': 60,
    'community': 50,
    'default': 80,
}

_NOISE_PATTERNS = [
    (r'^\s*RFC\s+\d+.*?\n', ''),
    (r'^\d+\s+[A-Z][a-zA-Z\s,]+,\s*[A-Z]{2}\s+\d{5}.*\n', ''),
    (r'^\s*EMail:\s*\S+@\S+\s*\n', ''),
    (r'^\s*(?:Phone|Fax):\s*[\d\-\+\(\)\s]+\s*\n', ''),
    (r'^\s*Copyright.*?(?:RFC|Internet\s+Society).*\n', ''),
    (r'^\s*Status of this Memo\s*\n', ''),
    (r'^\s*\d+\s*$\n', ''),
]


def is_meaningless_chunk(text: str, meta: dict) -> bool:
    if not text or not text.strip():
        return True
    text_stripped = text.strip()
    doc_type = meta.get('type', 'default')
    min_len = _MIN_CHUNK_LENGTHS.get(doc_type, _MIN_CHUNK_LENGTHS['default'])
    if len(text_stripped) < min_len:
        return True
    section_title = meta.get('section_title', '').lower()
    if section_title in MEANINGLESS_SECTIONS:
        return True
    for pattern, _ in _NOISE_PATTERNS:
        if re.search(pattern, text_stripped):
            return True
    alpha_digit_count = sum(c.isalnum() for c in text_stripped)
    alpha_ratio = alpha_digit_count / max(len(text_stripped), 1)
    if alpha_ratio < 0.15:
        return True
    return False


def clean_chunk_text(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped or len(cleaned_lines) == 0:
            cleaned_lines.append(line.rstrip())
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


@dataclass
class RawDocument:
    meta: dict
    content: str


def parse_markdown_with_yaml(file_path: str) -> RawDocument:
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if match:
        meta = yaml.safe_load(match.group(1))
        content = text[match.end():]
    else:
        meta = {}
        content = text
    return RawDocument(meta=meta, content=content)


def chunk_text(text: str, chunk_size=300, overlap=50) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)
    return chunks


def semantic_chunk(text: str, meta: dict) -> List:
    """
    根据文档类型选择切分策略。委托给 chunker.py 的 get_chunker() 分发。
    meta['type']: 'rfc' → RFCChunker / '3gpp' → GPPChunker / 其他 → GenericChunker。
    """
    from chunker import get_chunker, GenericChunker
    doc_type = meta.get("type", "default")
    try:
        chunker = get_chunker(doc_type)
        return chunker.chunk(text, meta)
    except Exception:
        logging.exception(f"Chunker ({doc_type}) 失败，回退到 GenericChunker")
        return GenericChunker().chunk(text, meta)


def load_all_md_documents(dir_path: str) -> List[RawDocument]:
    docs = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                try:
                    doc = parse_markdown_with_yaml(file_path)
                    docs.append(doc)
                except Exception as e:
                    logging.error(f"解析失败 {file_path}：{e}")
    return docs
