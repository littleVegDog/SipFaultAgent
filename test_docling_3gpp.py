#!/usr/bin/env python3
"""
测试Docling 3GPP处理功能
"""

import os
import sys
import traceback

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_docling_processing():
    """测试Docling处理功能"""
    try:
        # 使用 threegpp_pdf_loader（新版Docling OCR支持）
        from threegpp_pdf_loader import extract_text_from_pdf_with_docling, split_3gpp_sections, generate_markdown_chunks

        print("测试Docling 3GPP处理功能...")

        # 测试文件路径
        test_pdf = "knowledge_base/3gpp/ts_129212v190100p.pdf"

        if os.path.exists(test_pdf):
            print(f"测试文件存在: {test_pdf}")

            # 测试文本提取
            print("1. 测试文本提取...")
            text = extract_text_from_pdf_with_docling(test_pdf)
            print(f"提取文本长度: {len(text)} 字符")
            print(f"前200字符预览: {text[:200]}...")

            # 测试章节分割
            print("\n2. 测试章节分割...")
            chunks = split_3gpp_sections(text, "TS 29.212")
            print(f"分割得到 {len(chunks)} 个章节块")

            # 测试生成Markdown
            print("\n3. 测试生成Markdown...")
            output_dir = "temp_test_output"
            generate_markdown_chunks(
                pdf_path=test_pdf,
                output_dir=output_dir,
                spec_id="TS 29.212",
                meta_extra={
                    "interface": "Gx",
                    "domain": "VoLTE",
                    "tags": ["3GPP", "策略控制", "PCC", "Diameter"]
                }
            )
            print(f"测试完成，输出目录: {output_dir}")
        else:
            print(f"测试文件不存在: {test_pdf}")
            print("可能需要先下载3GPP测试文件或将路径改为实际存在的PDF文件")

    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_docling_processing()
