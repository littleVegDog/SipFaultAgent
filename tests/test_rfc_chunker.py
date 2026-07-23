#!/usr/bin/env python3
"""
测试RFC chunker功能
"""

from chunker import RFCChunker
import os

def test_rfc_chunker_basic():
    """测试基础RFC chunker功能"""
    print("=== 测试RFC Chunker基础功能 ===")

    # 创建测试用的RFC内容
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

    print(f"测试内容长度: {len(test_content)} 字符")
    print("测试文档内容预览:")
    print(test_content[:200] + "..." if len(test_content) > 200 else test_content)
    print("\n" + "="*50)

    # 创建chunker实例
    chunker = RFCChunker()

    try:
        # 调用chunk方法
        chunks = chunker.chunk(test_content, meta)
        print(f"成功切分出 {len(chunks)} 个chunk")

        if chunks:
            for i, chunk in enumerate(chunks[:3]):  # 显示前3个chunk
                print(f"\nChunk {i+1}:")
                print(f"  ID: {chunk.id}")
                print(f"  Type: {chunk.source_type}")
                print(f"  内容预览: {chunk.content[:100]}...")
                print(f"  元数据: {chunk.metadata}")
        else:
            print("警告: 没有生成任何chunk")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

def test_simple_rfc():
    """测试简化版本的RFC"""
    print("\n=== 测试简化版RFC ===")

    simple_content = """1. Introduction
This is the introduction section.

2. Methods
This describes the methods section.
"""

    meta = {'title': 'TestRFC', 'type': 'rfc'}

    chunker = RFCChunker()
    try:
        chunks = chunker.chunk(simple_content, meta)
        print(f"简化版测试 - 成功切分出 {len(chunks)} 个chunk")
        for i, chunk in enumerate(chunks):
            print(f"  Chunk {i+1}: {chunk.id} -> {len(chunk.content)} chars")
    except Exception as e:
        print(f"简化版错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_rfc_chunker_basic()
    test_simple_rfc()
