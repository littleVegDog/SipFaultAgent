"""
文档 Chunker：按文档类型分发到不同的切分器。
数据清洗在 parse 阶段（rfc_loader / 3gpp_pdf_loader 转 .md 时）完成，chunker 只做切分。
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """chunk 数据结构"""
    id: str
    content: str
    metadata: Dict[str, Any]
    source_type: str


class BaseChunker(ABC):
    """Chunker 基类"""

    @abstractmethod
    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        pass


# ==================== RFC Chunker ====================

class RFCChunker(BaseChunker):
    """RFC 文档 Chunker：直接使用 metadata 中的 section_id/section_title，按段落切分"""

    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        section_id = str(metadata.get('section', metadata.get('section_id', '')))
        section_title = metadata.get('section_title', '')
        rfc_number = str(metadata.get('rfc_number', ''))

        # 短章节：直接整体返回
        if len(content) <= 1000:
            chunk_content = f"## {section_title} ({section_id})\n\n{content}" if section_title else content
            chunk_id = f"rfc{rfc_number}_{section_id.replace('.', '_')}" if section_id else f"rfc{rfc_number}"
            return [Chunk(
                id=chunk_id,
                content=chunk_content,
                metadata={**metadata, 'section_id': section_id, 'title': section_title,
                          'type': 'rfc_section', 'parent_section_id': section_id},
                source_type='rfc'
            )]

        # 长章节：按段落切分子块
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        chunks = []
        current = ""
        sub_id = 0

        for para in paragraphs:
            if current and len(current) + len(para) + 2 > 700:
                chunk_content = f"## {section_title} ({section_id})\n\n{current.strip()}"
                chunks.append(Chunk(
                    id=f"rfc{rfc_number}_{section_id.replace('.', '_')}_sub_{sub_id}",
                    content=chunk_content,
                    metadata={**metadata, 'section_id': section_id,
                              'sub_section_id': f"{section_id}_sub_{sub_id}",
                              'title': section_title, 'type': 'rfc_subsection',
                              'parent_section_id': section_id},
                    source_type='rfc'
                ))
                sub_id += 1
                current = para
            else:
                current = current + "\n\n" + para if current else para

        if current.strip():
            chunk_content = f"## {section_title} ({section_id})\n\n{current.strip()}"
            chunks.append(Chunk(
                id=f"rfc{rfc_number}_{section_id.replace('.', '_')}_sub_{sub_id}",
                content=chunk_content,
                metadata={**metadata, 'section_id': section_id,
                          'sub_section_id': f"{section_id}_sub_{sub_id}",
                          'title': section_title, 'type': 'rfc_subsection',
                          'parent_section_id': section_id},
                source_type='rfc'
            ))

        return chunks if chunks else [Chunk(
            id=f"rfc{rfc_number}_{section_id.replace('.', '_')}",
            content=content,
            metadata={**metadata, 'section_id': section_id, 'title': section_title,
                      'type': 'rfc_section', 'parent_section_id': section_id},
            source_type='rfc'
        )]


# ==================== 3GPP Chunker ====================

class GPPChunker(BaseChunker):
    """3GPP 文档 Chunker：和 RFCChunker 一致，直接用 metadata + 段落切分"""

    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        section_id = str(metadata.get('section', metadata.get('section_id', '')))
        section_title = metadata.get('section_title', metadata.get('title', ''))
        spec_id = str(metadata.get('spec_id', ''))

        if len(content) <= 1500:
            chunk_content = f"### {section_title} ({section_id})\n\n{content}" if section_title else content
            return [Chunk(
                id=f"{spec_id}_{section_id.replace('.', '_')}",
                content=chunk_content,
                metadata={**metadata, 'section_id': section_id, 'title': section_title,
                          'type': '3gpp_section', 'parent_section_id': section_id},
                source_type='3gpp'
            )]

        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        chunks = []
        current = ""
        sub_id = 0

        for para in paragraphs:
            if para.startswith(('Note:', 'Important:', 'Caution:', 'Example:', 'Warning:')):
                if current.strip():
                    chunks.append(Chunk(
                        id=f"{spec_id}_{section_id.replace('.', '_')}_sub_{sub_id}",
                        content=f"### {section_title} ({section_id})\n\n{current.strip()}",
                        metadata={**metadata, 'section_id': section_id,
                                  'sub_section_id': f"{section_id}_sub_{sub_id}",
                                  'title': section_title, 'type': '3gpp_subsection',
                                  'parent_section_id': section_id},
                        source_type='3gpp'
                    ))
                    sub_id += 1
                    current = ""
                current = para
            elif current and len(current) + len(para) + 2 > 1000:
                chunks.append(Chunk(
                    id=f"{spec_id}_{section_id.replace('.', '_')}_sub_{sub_id}",
                    content=f"### {section_title} ({section_id})\n\n{current.strip()}",
                    metadata={**metadata, 'section_id': section_id,
                              'sub_section_id': f"{section_id}_sub_{sub_id}",
                              'title': section_title, 'type': '3gpp_subsection',
                              'parent_section_id': section_id},
                    source_type='3gpp'
                ))
                sub_id += 1
                current = para
            else:
                current = current + "\n\n" + para if current else para

        if current.strip():
            chunks.append(Chunk(
                id=f"{spec_id}_{section_id.replace('.', '_')}_sub_{sub_id}",
                content=f"### {section_title} ({section_id})\n\n{current.strip()}",
                metadata={**metadata, 'section_id': section_id,
                          'sub_section_id': f"{section_id}_sub_{sub_id}",
                          'title': section_title, 'type': '3gpp_subsection',
                          'parent_section_id': section_id},
                source_type='3gpp'
            ))

        return chunks if chunks else [Chunk(
            id=f"{spec_id}_{section_id}",
            content=content,
            metadata={**metadata, 'section_id': section_id, 'title': section_title,
                      'type': '3gpp_section', 'parent_section_id': section_id},
            source_type='3gpp'
        )]


# ==================== Product Chunker ====================

class ProductChunker(BaseChunker):
    """产品文档 Chunker：按 ## 二级标题切分"""

    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        parts = re.split(r'(?=^## )', content, flags=re.MULTILINE)
        chunks = []
        for i, p in enumerate(parts):
            p = p.strip()
            if len(p) < 30:
                continue
            # 提取标题
            title_match = re.match(r'^##\s+(.+)', p)
            section_title = title_match.group(1).strip() if title_match else f"section_{i}"
            chunks.append(Chunk(
                id=f"product_chunk_{i}",
                content=p,
                metadata={**metadata, 'section_title': section_title, 'type': 'product_doc',
                          'parent_section_id': f"product_chunk_{i}"},
                source_type='product_doc'
            ))
        return chunks if chunks else [Chunk(
            id="product_full", content=content,
            metadata={**metadata, 'type': 'product_doc', 'parent_section_id': 'product_full'},
            source_type='product_doc'
        )]


# ==================== Case Chunker ====================

class CaseChunker(BaseChunker):
    """案例文档 Chunker：按 ## 现象/原因/解决方案/排查过程 关键词切分"""

    CASE_SECTIONS = ['现象', '原因', '解决方案', '解决方法', '排查过程', '排障过程', '根因', '处理步骤']

    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        parts = re.split(r'(?=^## )', content, flags=re.MULTILINE)
        chunks = []
        for i, p in enumerate(parts):
            p = p.strip()
            if len(p) < 30:
                continue
            title_match = re.match(r'^##\s+(.+)', p)
            section_title = title_match.group(1).strip() if title_match else f"section_{i}"
            chunks.append(Chunk(
                id=f"case_chunk_{i}",
                content=p,
                metadata={**metadata, 'section_title': section_title, 'type': 'case',
                          'parent_section_id': f"case_chunk_{i}"},
                source_type='case'
            ))
        return chunks if chunks else [Chunk(
            id="case_full", content=content,
            metadata={**metadata, 'type': 'case', 'parent_section_id': 'case_full'},
            source_type='case'
        )]


# ==================== Generic Chunker ====================

class GenericChunker(BaseChunker):
    """通用 Chunker：短文本整体返回，长文本按段落切分"""

    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        doc_type = metadata.get('type', 'default')
        if len(content) <= 1000:
            return [Chunk(
                id="chunk_0", content=content,
                metadata={**metadata, 'type': doc_type, 'parent_section_id': 'chunk_0'},
                source_type=doc_type
            )]

        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        chunks = []
        current = ""
        sub_id = 0
        for para in paragraphs:
            if current and len(current) + len(para) + 2 > 700:
                chunks.append(Chunk(
                    id=f"chunk_{sub_id}", content=current.strip(),
                    metadata={**metadata, 'type': doc_type, 'parent_section_id': f"chunk_{sub_id}"},
                    source_type=doc_type
                ))
                sub_id += 1
                current = para
            else:
                current = current + "\n\n" + para if current else para
        if current.strip():
            chunks.append(Chunk(
                id=f"chunk_{sub_id}", content=current.strip(),
                metadata={**metadata, 'type': doc_type, 'parent_section_id': f"chunk_{sub_id}"},
                source_type=doc_type
            ))
        return chunks if chunks else [Chunk(
            id="chunk_0", content=content,
            metadata={**metadata, 'type': doc_type, 'parent_section_id': 'chunk_0'},
            source_type=doc_type
        )]


# ==================== 分发器 ====================

def get_chunker(doc_type: str, **kwargs) -> BaseChunker:
    """根据文档类型返回对应的 Chunker 实例"""
    if doc_type == 'rfc':
        return RFCChunker()
    elif doc_type == '3gpp':
        return GPPChunker()
    elif doc_type == 'product_doc':
        return ProductChunker()
    elif doc_type in ('case', 'community'):
        return CaseChunker()
    else:
        return GenericChunker()
