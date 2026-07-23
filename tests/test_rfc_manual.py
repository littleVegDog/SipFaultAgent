#!/usr/bin/env python3
"""
手动测试RFC chunker函数的正确性
"""

from chunker import RFCChunker

def test_content():
    # 原始测试内容，包含多个RFC章节，模拟真实分段结构
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

    meta = {'title': 'RFC3261', 'type': 'rfc'}

    print("=== 实际 RFC 内容 ===")
    print(test_content)
    print("\n=== 期望结构 ===")
    print("应分割为以下章节:")
    print("1. Introduction (1. Introduction -> 1. Introduction 开头到 2. Conformance 开头)")
    print("2. Conformance (2. Conformance -> 2. Conformance 开头到 21.4.2 开头)")
    print("3. 401 Unauthorized (21.4.2 401 Unauthorized -> 21.4.2 401 Unauthorized 开头到 403 Forbidden 开头)")
    print("4. 403 Forbidden (403 Forbidden -> 403 Forbidden 开头到 4. Protocol Overview 开头)")
    print("5. Protocol Overview (4. Protocol Overview -> 4. Protocol Overview 开头到结尾)")
    print("\n=== 手动分割结果 ===")

    lines = test_content.split('\n')
    print(f"总共有 {len(lines)} 行")

    expected_parts = [
        ("1. Introduction", 0, 18),
        ("2. Conformance", 18, 21),
        ("21.4.2 401 Unauthorized", 21, 26),
        ("403 Forbidden", 26, 30),
        ("4. Protocol Overview", 30, None)
    ]

    for i, (title, start_line, end_line) in enumerate(expected_parts):
        if end_line is None:
            line_content = lines[start_line:]
        else:
            line_content = lines[start_line:end_line]
        content = '\n'.join(line_content)
        print(f"\nPart {i+1}: {title}")
        print(content[:200] + '...' if len(content) > 200 else content)

if __name__ == "__main__":
    test_content()
