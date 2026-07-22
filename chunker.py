"""
文档Chunker基类和RFC专用Chunker实现
用于实现不同文档类型定制化切分策略
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass
import re
import json
from logger_config import info_print, debug_print, error_print

@dataclass
class Chunk:
    """chunk数据结构"""
    id: str
    content: str
    metadata: Dict[str, Any]
    source_type: str

class BaseChunker(ABC):
    """Chunker基类"""

    def __init__(self, **kwargs):
        self.config = kwargs

    @abstractmethod
    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        """抽象方法：实现具体chunk逻辑"""
        pass

    def validate_chunk(self, chunk: Chunk) -> bool:
        """通用chunk验证"""
        return (chunk.content and
                len(chunk.content.strip()) > 10 and
                chunk.id and
                chunk.metadata is not None)

    def post_process(self, chunks: List[Chunk]) -> List[Chunk]:
        """通用后处理"""
        # 去重，过滤等
        return [chunk for chunk in chunks if self.validate_chunk(chunk)]

class RFCChunker(BaseChunker):
    """RFC文档专用Chunker"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # RFC章节匹配模式 - 更宽松的匹配规则
        self.section_pattern = r'^(\d+(?:\.\d+)*|[A-Z])(?:\s+)(.+)$'  # 允许一个以上的空格

    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        """
        RFC文档专用切分逻辑
        保持协议术语和章节结构的完整性
        """
        chunks = []
        debug_print(f"开始处理RFC内容，长度={len(content)}")

        try:
            # RFC结构拆分
            sections = self._extract_sections(content)
            debug_print(f"提取到 {len(sections)} 个章节")

            for i, section in enumerate(sections):
                section_id = section['id']
                section_title = section['title']
                section_content = section['content']
                line_start = section['line_start']
                line_end = section['line_end']

                # 按照章节大小进行不同处理
                if len(section_content) > 1000:
                    # 大章节：进行细粒度切片，确保功能点完整性和语义完整性
                    debug_print(f"处理大章节 {section_id}，长度: {len(section_content)}")
                    sub_chunks = self._chunk_large_section(section_content, section_id,
                                                         section_title, metadata)
                    chunks.extend(sub_chunks)
                else:
                    # 小章节：直接保留完整内容
                    debug_print(f"处理小章节 {section_id}，长度: {len(section_content)}")
                    chunk_content = f"## {section_title} ({section_id})\n\n{section_content}"
                    chunks.append(Chunk(
                        id=f"{section_id}",
                        content=chunk_content,
                        metadata={**metadata,
                                'section_id': section_id,
                                'title': section_title,
                                'line_start': line_start,
                                'line_end': line_end,
                                'type': 'rfc_section',
                                'parent_section_id': section_id},
                        source_type='rfc'
                    ))

            # 后处理
            result_chunks = self.post_process(chunks)
            debug_print(f"RFC处理完成，返回 {len(result_chunks)} 个chunk")
            return result_chunks

        except Exception as e:
            error_print(f"RFC切分失败: {e}")
            import traceback
            traceback.print_exc()
            # 出错时使用基础切分作为保底
            return self._fallback_chunk(content, metadata)

    def _extract_sections(self, text: str) -> List[Dict]:
        """
        提取RFC结构章节信息
        RFC典型格式：如 "1. Introduction" 或 "21.4.2 401 Unauthorized"
        """
        sections = []
        lines = text.split('\n')

        current_section = None
        current_content = []
        debug_print(f"开始提取章节，总行数: {len(lines)}")

        for line_num, line in enumerate(lines):
            # 匹配章节标题行 - RFC常用格式
            # 如: "1. Introduction"  或 "21.4.2 401 Unauthorized"
            section_match = re.match(self.section_pattern, line.strip())

            if section_match:
                debug_print(f"匹配到章节标题: \"{line.strip()}\" -> {section_match.groups()}")
                # 保存前一个章节
                if current_section:
                    sections.append({
                        'id': current_section['id'],
                        'title': current_section['title'],
                        'content': '\n'.join(current_content).strip(),
                        'line_start': current_section['line_start'],
                        'line_end': line_num - 1
                    })

                # 开始新章节
                section_id = section_match.group(1).strip()
                title = section_match.group(2).strip()
                current_section = {
                    'id': section_id,
                    'title': title,
                    'line_start': line_num
                }
                current_content = [line]  # 包含章节标题行
            else:
                # 非章节行，归属当前章节
                if current_section:
                    current_content.append(line)

        # 处理最后一个章节
        if current_section:
            sections.append({
                'id': current_section['id'],
                'title': current_section['title'],
                'content': '\n'.join(current_content).strip(),
                'line_start': current_section['line_start'],
                'line_end': len(lines) - 1
            })

        debug_print(f"成功提取 {len(sections)} 个章节")
        return sections

    def _chunk_large_section(self, content: str, section_id: str,
                           section_title: str, metadata: Dict[str, Any]) -> List[Chunk]:
        """处理大章节的子切片"""
        chunks = []
        debug_print(f"开始大章节切分: {section_id}")

        # 简单按段落切分，保持内容连贯性
        paragraphs = content.split('\n\n')

        current_chunk = ""
        chunk_id = 0

        # 开始循环段落
        for para in paragraphs:
            if para.strip():
                # 检查是否可以在当前chunk里添加这个段落
                if len(current_chunk) + len(para) + 2 > 700:  # 700字符限制
                    if current_chunk.strip():
                        # 保存当前chunk
                        chunk_content = f"## {section_title} ({section_id})\n\n{current_chunk.strip()}"
                        chunks.append(Chunk(
                            id=f"{section_id}_sub_{chunk_id}",
                            content=chunk_content,
                            metadata={**metadata,
                                    'section_id': section_id,
                                    'sub_section_id': f"{section_id}_sub_{chunk_id}",
                                    'title': section_title,
                                    'type': 'rfc_subsection',
                                    'parent_section_id': section_id},
                            source_type='rfc'
                        ))
                        chunk_id += 1
                        current_chunk = para + "\n\n"  # 开始新chunk
                    else:
                        # 当前块为空，直接用新段落
                        current_chunk = para + "\n\n"
                else:
                    current_chunk += para + "\n\n"

        # 处理剩余内容
        if current_chunk.strip():
            chunk_content = f"## {section_title} ({section_id})\n\n{current_chunk.strip()}"
            chunks.append(Chunk(
                id=f"{section_id}_sub_{chunk_id}",
                content=chunk_content,
                metadata={**metadata,
                        'section_id': section_id,
                        'sub_section_id': f"{section_id}_sub_{chunk_id}",
                        'title': section_title,
                        'type': 'rfc_subsection',
                        'parent_section_id': section_id},
                source_type='rfc'
            ))

        return chunks

    def _fallback_chunk(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        """错误时的回退切分方案"""
        # 基础滑动窗口，先做最小保障
        try:
            from document_loader import chunk_text
            basic_chunks = chunk_text(content, chunk_size=500, overlap=50)
            return [Chunk(
                id=f"fallback_chunk_{i}",
                content=chunk,
                metadata={**metadata, 'type': 'fallback_chunk', 'source': 'rfc'},
                source_type='rfc'
            ) for i, chunk in enumerate(basic_chunks)]
        except Exception as e:
            # 最后保障：返回整体文档
            error_print(f"回退切分失败: {e}")
            return [Chunk(
                id=f"fallback_full",
                content=content,
                metadata={**metadata, 'type': 'fallback_full', 'source': 'rfc'},
                source_type='rfc'
            )]


class GPPChunker(BaseChunker):
    """3GPP文档专用Chunker"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.section_pattern = r'^(\d+(?:\.\d+)*[A-Z]?(?:\.\d+)*)(?:\s{2,})(.+?)(?=\n\d+(?:\.\d+)*[A-Z]?(?:\.\d+)*\s{2,}|\Z)'

    def chunk(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        """3GPP文档专用切分逻辑"""
        chunks = []
        debug_print(f"开始处理3GPP内容，长度={len(content)}")
        try:
            sections = self._extract_3gpp_sections(content)
            for i, section in enumerate(sections):
                section_id = section['id']
                section_title = section['title']
                section_content = section['content']
                if len(section_content) > 1500:
                    sub_chunks = self._chunk_large_3gpp_section(section_content, section_id,
                                                              section_title, metadata)
                    chunks.extend(sub_chunks)
                else:
                    chunk_content = f"### {section_title} ({section_id})\n\n{section_content}"
                    chunks.append(Chunk(
                        id=f"{section_id}",
                        content=chunk_content,
                        metadata={**metadata, 'section_id': section_id, 'title': section_title, 'type': '3gpp_section', 'parent_section_id': section_id},
                        source_type='3gpp'
                    ))
            result_chunks = self.post_process(chunks)
            debug_print(f"3GPP处理完成，返回 {len(result_chunks)} 个chunk")
            return result_chunks
        except Exception as e:
            error_print(f"3GPP切分失败: {e}")
            import traceback
            traceback.print_exc()
            return self._fallback_chunk(content, metadata)

    def _extract_3gpp_sections(self, text: str) -> List[Dict]:
        sections = []
        lines = text.split('\n')
        current_section = None
        current_content = []
        for line_num, line in enumerate(lines):
            section_match = re.match(self.section_pattern, line.strip(), re.MULTILINE | re.DOTALL)
            if section_match and len(line.strip()) > 10:
                if current_section:
                    sections.append({
                        'id': current_section['id'], 'title': current_section['title'],
                        'content': '\n'.join(current_content).strip(),
                    })
                section_id = section_match.group(1).strip()
                title = section_match.group(2).strip()
                current_section = {'id': section_id, 'title': title}
                current_content = [line]
            else:
                if current_section:
                    current_content.append(line)
        if current_section:
            sections.append({
                'id': current_section['id'], 'title': current_section['title'],
                'content': '\n'.join(current_content).strip(),
            })
        return sections

    def _chunk_large_3gpp_section(self, content: str, section_id: str,
                                section_title: str, metadata: Dict[str, Any]) -> List[Chunk]:
        chunks = []
        paragraphs = content.split('\n\n')
        current_chunk = ""
        chunk_id = 0
        structured_paragraphs = []
        for para in paragraphs:
            if para.strip():
                if para.strip().startswith(('Note:', 'Important:', 'Caution:', 'Example:', 'Warning:', 'Note')):
                    if current_chunk:
                        structured_paragraphs.append(current_chunk)
                        current_chunk = ""
                    structured_paragraphs.append(para)
                else:
                    if current_chunk:
                        current_chunk += "\n\n" + para
                    else:
                        current_chunk = para
        if current_chunk:
            structured_paragraphs.append(current_chunk)
        for para in structured_paragraphs:
            if para.strip():
                if len(current_chunk) + len(para) + 2 > 1000:
                    if current_chunk.strip():
                        chunk_content = f"### {section_title} ({section_id})\n\n{current_chunk.strip()}"
                        chunks.append(Chunk(
                            id=f"{section_id}_sub_{chunk_id}",
                            content=chunk_content,
                            metadata={**metadata, 'section_id': section_id,
                                    'sub_section_id': f"{section_id}_sub_{chunk_id}",
                                    'title': section_title, 'type': '3gpp_subsection',
                                    'parent_section_id': section_id},
                            source_type='3gpp'
                        ))
                        chunk_id += 1
                        current_chunk = para + "\n\n"
                    else:
                        current_chunk = para + "\n\n"
                else:
                    current_chunk += para + "\n\n"
        if current_chunk.strip():
            chunk_content = f"### {section_title} ({section_id})\n\n{current_chunk.strip()}"
            chunks.append(Chunk(
                id=f"{section_id}_sub_{chunk_id}",
                content=chunk_content,
                metadata={**metadata, 'section_id': section_id,
                        'sub_section_id': f"{section_id}_sub_{chunk_id}",
                        'title': section_title, 'type': '3gpp_subsection', 'parent_section_id': section_id},
                source_type='3gpp'
            ))
        return chunks

    def _fallback_chunk(self, content: str, metadata: Dict[str, Any]) -> List[Chunk]:
        try:
            from document_loader import chunk_text
            basic_chunks = chunk_text(content, chunk_size=500, overlap=50)
            return [Chunk(
                id=f"fallback_chunk_{i}", content=chunk,
                metadata={**metadata, 'type': 'fallback_chunk', 'source': '3gpp'},
                source_type='3gpp'
            ) for i, chunk in enumerate(basic_chunks)]
        except Exception as e:
            error_print(f"3GPP回退切分失败: {e}")
            return [Chunk(
                id=f"fallback_full", content=content,
                metadata={**metadata, 'type': 'fallback_full', 'source': '3gpp'},
                source_type='3gpp'
            )]


# 测试函数，可直接运行
def test_rfc_chunker():
    """测试RFC chunker"""
    test_content = """1. Introduction

This document defines the Session Initiation Protocol (SIP) for initiating, modifying, and terminating sessions between two or more participants in a multimedia conference, including voice, video, and messaging.

2. Conformance

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

21.4.2 401 Unauthorized

The 401 response indicates that the request requires user authentication. The response MUST include a WWW-Authenticate header field containing a challenge applicable to the requested resource.

403 Forbidden

The 403 response indicates that the server understood the request but refuses to fulfill it. The server SHOULD include a message body that explains why the request was refused.

4. Protocol Overview

The SIP protocol is a text-based protocol for session establishment."""

    meta = {'title': 'RFC3261', 'type': 'rfc', 'version': '1.0'}

    print("测试RFC Charmer:")
    chunker = RFCChunker()
    chunks = chunker.chunk(test_content, meta)

    print(f"生成 {len(chunks)} 个chunks")
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}: {chunk.id}")
        print(f"  内容长度: {len(chunk.content)}")
        print(f"  内容预览: {chunk.content[:100]}...")
        print(f"  元数据: {chunk.metadata}")
        print()

    return chunks

def test_3gpp_chunker():
    """测试3GPP chunker"""
    test_content = """1. Introduction

This is the introduction section of a 3GPP specification document. It describes the overall purpose and scope of the specification.

2. Conformance

The terms "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

3. Architecture

The architecture of the 3GPP system consists of several components including:
- Core Network Elements
- User Equipment (UE)
- Access Network Elements

Note: The architecture may vary depending on the specific 3GPP release and deployment scenario.

3.1. Network Components

The 3GPP network components include the following:
- MME (Mobility Management Entity)
- S-GW (Serving Gateway)
- P-GW (Packet Data Network Gateway)

Important: The exact implementation of these components is defined in the relevant 3GPP technical specifications.

4. Protocol Description

This section describes the protocols used in the 3GPP system."""

    meta = {'title': 'TS 29.212', 'type': '3gpp', 'version': '1.0'}

    print("测试3GPP Chunker:")
    chunker = GPPChunker()
    chunks = chunker.chunk(test_content, meta)

    print(f"生成 {len(chunks)} 个chunks")
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i+1}: {chunk.id}")
        print(f"  内容长度: {len(chunk.content)}")
        print(f"  内容预览: {chunk.content[:150]}...")
        print(f"  元数据: {chunk.metadata}")
        print()

if __name__ == "__main__":
    test_rfc_chunker()
    test_3gpp_chunker()
