import os
import re
import yaml
import logging
from typing import List
from dataclasses import dataclass
from chunker import RFCChunker


# ==================== 新增：数据清洗相关常量和函数 ====================

# 切分后需要丢弃的无意义章节名（小写匹配）
MEANINGLESS_SECTIONS = {
    'acknowledgements', 'authors', 'author', 'appendix',
    'table of contents', 'contributors', 'references',
    'revision history', 'intellectual property', 'legal notice',
    'introduction',   # 部分 RFC 的 Introduction 章节内容极短，仅有概述
}

# 各文档类型的 chunk 最小长度阈值（单位：字符）
# case 类型阈值较低，因为 ## 现象/## 原因 等小节本身就短小精炼
_MIN_CHUNK_LENGTHS = {
    'case': 40,
    'rfc': 80,
    '3gpp': 80,
    'product_doc': 60,
    'community': 50,
    'default': 80,
}

# 噪音正则模式（匹配页眉页脚、联系信息等无意义行）
_NOISE_PATTERNS = [
    # RFC 页眉行：RFC 3261 ...
    (r'^\s*RFC\s+\d+.*?\n', ''),
    # 地址行：门牌号 街道 城市 邮编
    (r'^\d+\s+[A-Z][a-zA-Z\s,]+,\s*[A-Z]{2}\s+\d{5}.*\n', ''),
    # 邮箱行
    (r'^\s*EMail:\s*\S+@\S+\s*\n', ''),
    # 电话/传真行
    (r'^\s*(?:Phone|Fax):\s*[\d\-\+\(\)\s]+\s*\n', ''),
    # 版权行
    (r'^\s*Copyright.*?(?:RFC|Internet\s+Society).*\n', ''),
    # RFC 状态说明行
    (r'^\s*Status of this Memo\s*\n', ''),
    # 独立行号行（数字单独一行）
    (r'^\s*\d+\s*$\n', ''),
]


def is_meaningless_chunk(text: str, meta: dict) -> bool:
    """
    判断切分后的 chunk 是否无意义、应予丢弃。

    丢弃条件（满足任一即丢弃）：
    1. 文本过短（<80字符）
    2. 属于已知无意义章节名
    3. 匹配噪音模式（地址/邮箱/页眉等）
    4. 正文字符占比过低（<30%为字母/数字）
    """
    if not text or not text.strip():
        return True

    text_stripped = text.strip()

    # 条件1：过短（按文档类型差异化阈值）
    doc_type = meta.get('type', 'default')
    min_len = _MIN_CHUNK_LENGTHS.get(doc_type, _MIN_CHUNK_LENGTHS['default'])
    if len(text_stripped) < min_len:
        return True

    # 条件2：章节名过滤
    section_title = meta.get('section_title', '').lower()
    if section_title in MEANINGLESS_SECTIONS:
        return True

    # 条件3：噪音模式匹配
    for pattern, _ in _NOISE_PATTERNS:
        if re.search(pattern, text_stripped):
            return True

    # 条件4：正文字符占比（排除符号、空格、数字-only）
    # 但排除纯ASCII图（状态机图等），它们虽然符号多但有语义
    alpha_digit_count = sum(c.isalnum() for c in text_stripped)
    alpha_ratio = alpha_digit_count / max(len(text_stripped), 1)
    # 阈值0.15：低于此判定为纯噪音（如表格分隔线、ASCII艺术家等）
    if alpha_ratio < 0.15:
        return True

    return False


def clean_chunk_text(text: str) -> str:
    """
    清理 chunk 文本中的残余噪音字符，保留正文结构。
    """
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        # 跳过纯空白行（后续统一处理换行）
        stripped = line.strip()
        # 保留有实质内容的行（允许标点符号作为内容）
        if stripped or len(cleaned_lines) == 0:
            cleaned_lines.append(line.rstrip())

    # 合并连续空行（不超过2个换行）
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


@dataclass
class RawDocument:
    meta: dict
    content: str

def parse_markdown_with_yaml(file_path:str)->RawDocument:
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    #提取yaml头部---即markdown文件开头的元数据块，用于配置文档的属性
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if match:
        meta = yaml.safe_load(match.group(1))
        content = text[match.end():]
    else:
        meta = {}
        content = text
    return RawDocument(meta = meta, content = content)

def chunk_text(text:str, chunk_size = 300, overlap = 50)->List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)
    return chunks

def extract_sections(text: str, doc_type: str = "") -> List[dict]:
    """
    从RFC等文档中提取结构化章节信息，用于Parent-Child结构

    Args:
        text: 原始文档文本
        doc_type: 文档类型

    Returns:
        List[dict]: 包含章节信息的列表
    """
    sections = []

    # RFC文档的章节提取
    if doc_type == "rfc":
        # 匹配章节标题：数字或大写字母开头，可能带点，后面至少两个空格或直接跟文字
        lines = text.split('\n')
        current_section = None
        current_content = []

        for line in lines:
            # 匹配章节标题行
            section_match = re.match(r'^(\d+(?:\.\d+)*|[A-Z])\s{2,}(.+)$', line.strip())
            if section_match:
                # 如果之前有章节，保存它
                if current_section:
                    sections.append({
                        'section_id': current_section['id'],
                        'title': current_section['title'],
                        'content': '\n'.join(current_content).strip()
                    })

                # 开始新章节
                section_id = section_match.group(1)
                section_title = section_match.group(2).strip()
                current_section = {
                    'id': section_id,
                    'title': section_title
                }
                current_content = []
            else:
                # 这行属于当前章节内容
                if current_section:
                    current_content.append(line)

        # 保存最后一个章节
        if current_section:
            sections.append({
                'section_id': current_section['id'],
                'title': current_section['title'],
                'content': '\n'.join(current_content).strip()
            })
    else:
        # 默认处理：将整个文档作为一个"章节"
        sections.append({
            'section_id': '0',
            'title': '全文',
            'content': text
        })

    return sections


def semantic_chunk(text:str, meta:dict)->List:
    """
    根据文档类型选择不同的切分策略。
    meta 中应包含 'type' 字段，如 'rfc', 'product_doc', 'case', 'community'。
    返回 List[Chunk]，保留元数据（section_id, title, parent_section_id, type 等）。
    """
    from chunker import Chunk
    doc_type = meta.get("type", "")

    # RFC文件使用专门的chunker进行协议结构化处理
    if doc_type == "rfc":
        rfc_chunker = RFCChunker()
        try:
            return rfc_chunker.chunk(text, meta)
        except Exception:
            logging.exception("RFC chunker出错，回退到默认切分方案")

    # 其他文档类型使用原有策略
    return _semantic_chunk_old(text, meta)

def _semantic_chunk_old(text:str, meta:dict)->List:
    """
    老版本的语义切分函数（保留原逻辑为回退）
    """
    doc_type = meta.get("type", "")

    # 首先提取语义章节（Parent结构）
    sections = extract_sections(text, doc_type)

    if doc_type in ("case", "community"):
        # 案例按二级标题切分，尽量保持完整
        chunks = []
        for section in sections:
            # 对每个section内部再次细分
            if len(section['content']) < 100:  # 过短章节直接返回
                if section['content'].strip():
                    chunks.append(f"## {section['title']}\n{section['content']}")
            else:
                # 针对较大章节进行细粒度分割
                sub_chunks = chunk_text(section['content'], chunk_size=500, overlap=50)
                for i, sub_chunk in enumerate(sub_chunks):
                    chunks.append(f"## {section['title']}\n{sub_chunk}")

        # 清理和过滤
        filtered_chunks = []
        for chunk in chunks:
            if is_meaningless_chunk(chunk, meta):
                continue
            chunk = clean_chunk_text(chunk)
            if chunk and len(chunk) >= 30:
                filtered_chunks.append(chunk)

        result = filtered_chunks if filtered_chunks else chunk_text(text)
        return _wrap_as_chunks(result, meta, doc_type)

    # rfc文档切割（回退方案）
    if doc_type == "rfc":
        chunks = []
        for section in sections:
            section_header = section['section_id']
            content = section['content']

            if not content.strip() or len(content) < 30:
                continue

            if len(content) > 700:
                # 对大章节进行子分割，形成Parent-Child关系
                sub_chunks = chunk_text(content, chunk_size=500, overlap=50)
                for i, sub in enumerate(sub_chunks):
                    full_content = f"### 章节：{section['title']} ({section_header})\n{sub}"
                    chunks.append(full_content)
            else:
                # 小章节
                full_content = f"### 章节：{section['title']} ({section_header})\n{content}"
                chunks.append(full_content)

        result = _post_process_chunks(chunks if chunks else chunk_text(text), meta)
        return _wrap_as_chunks(result, meta, doc_type)

    # 产品文档（错误码、配置说明）：按章节切分
    if doc_type == "product_doc":
        chunks = []
        for section in sections:
            content = section['content']
            if not content.strip() or len(content) < 30:
                continue

            if len(content) > 600:
                # 对大章节进行子分割
                sub_chunks = chunk_text(content, chunk_size=500, overlap=50)
                for i, sub in enumerate(sub_chunks):
                    full_content = f"## {section['title']}\n{sub}"
                    chunks.append(full_content)
            else:
                # 小章节
                full_content = f"## {section['title']}\n{content}"
                chunks.append(full_content)

        result = _post_process_chunks(chunks if chunks else chunk_text(text), meta)
        return _wrap_as_chunks(result, meta, doc_type)

    # 默认：固定滑动窗口
    default_chunks = chunk_text(text)
    result = _post_process_chunks(default_chunks, meta)
    return _wrap_as_chunks(result, meta, doc_type)


def _wrap_as_chunks(chunk_texts: List[str], meta: dict, doc_type: str = "default") -> List:
    """将字符串列表包装为 Chunk 对象，保留元数据"""
    from chunker import Chunk
    return [Chunk(id=f"chunk_{i}", content=t, metadata={**meta, 'type': doc_type}, source_type=doc_type)
            for i, t in enumerate(chunk_texts)]


def _post_process_chunks(chunks: List[str], meta: dict) -> List[str]:
    """
    对切分结果统一执行：去噪、过滤、保底。
    确保不返回空列表（至少保留一个 chunk）。
    """
    cleaned = []
    for chunk in chunks:
        if is_meaningless_chunk(chunk, meta):
            continue
        chunk = clean_chunk_text(chunk)
        if chunk:  # 清洗后可能变空，再判一次
            cleaned.append(chunk)

    # 保底：所有 chunk 都被过滤时，保留原文（不过滤）
    if not cleaned and chunks:
        fallback = clean_chunk_text(chunks[0])
        return [fallback] if fallback else []

    return cleaned


def load_all_md_documents(dir_path:str)->List[RawDocument]:
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
