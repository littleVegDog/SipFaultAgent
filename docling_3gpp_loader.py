"""
使用Docling处理3GPP PDF文档
增强的文档预处理和数据清洗模块
"""

import os
import re
import yaml
from typing import List, Dict, Any
from docling.document_converter import DocumentConverter
from docling.models import BaseDocument

class Docling3GPPProcessor:
    def __init__(self):
        self.converter = DocumentConverter()

    def process_3gpp_pdf(self, pdf_path: str, output_dir: str, spec_id: str,
                         meta_extra: Dict[str, Any] = None) -> List[str]:
        """
        使用Docling处理3GPP PDF文档
        """
        try:
            document = self.converter.convert(pdf_path)
            content = self._extract_structured_content(document)
            cleaned_content = self._clean_content(content)
            markdown_files = self._generate_markdown_chunks(
                cleaned_content, pdf_path, output_dir, spec_id, meta_extra or {}
            )
            print(f"成功处理 {spec_id}，生成 {len(markdown_files)} 个Markdown文件")
            return markdown_files
        except Exception as e:
            print(f"处理 {pdf_path} 时出错: {e}")
            raise

    def _extract_structured_content(self, document: BaseDocument) -> str:
        return document.text

    def _clean_content(self, content: str) -> str:
        lines = content.split('\n')
        cleaned_lines = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'^\d+$', stripped) and len(stripped) <= 5:
                continue
            if any(keyword in stripped for keyword in ['3GPP', 'TS', 'Technical Specification',
                                                      'Copyright', 'Page', 'Table of Contents']):
                continue
            if not stripped and i > 0 and i < len(lines) - 1:
                if lines[i-1].strip() == '' and lines[i+1].strip() == '':
                    continue
            cleaned_lines.append(line)
        cleaned_text = '\n'.join(cleaned_lines)
        cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)
        cleaned_text = self._normalize_formatting(cleaned_text)
        return cleaned_text

    def _normalize_formatting(self, text: str) -> str:
        text = text.replace('\xa0', ' ')
        text = re.sub(r'\r\n', '\n', text)
        text = re.sub(r'\r', '\n', text)
        return text

    def _generate_markdown_chunks(self, content: str, pdf_path: str, output_dir: str,
                                spec_id: str, meta_extra: Dict[str, Any]) -> List[str]:
        os.makedirs(output_dir, exist_ok=True)
        sections = self._split_sections_with_docling(content, spec_id)
        markdown_files = []
        for i, section in enumerate(sections):
            meta = {
                "type": "3gpp",
                "spec_id": spec_id,
                "section": section.get("section", ""),
                "title": section.get("title", f"{spec_id} Section"),
                "source_file": os.path.basename(pdf_path),
                **meta_extra
            }
            yaml_header = yaml.dump(meta, allow_unicode=True, default_flow_style=False, width=1000)
            full_content = f"---\n{yaml_header}---\n\n{section['content']}"
            fname = f"{spec_id}_{section.get('section', 'unknown')}_{i}.md"
            fpath = os.path.join(output_dir, fname)
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(full_content)
            markdown_files.append(fpath)
        return markdown_files

    def _split_sections_with_docling(self, content: str, spec_id: str) -> List[Dict[str, Any]]:
        sections = []
        lines = content.split('\n')
        current_section = None
        current_content = []
        section_id = ""
        section_title = ""
        for line in lines:
            line = line.strip()
            section_match = re.match(r'^(\d+(?:\.\d+)*[A-Z]?(?:\.\d+)*)(?:\s+)(.+)$', line)
            if section_match and len(line) > 10:
                if current_section:
                    sections.append({
                        'section': current_section,
                        'title': section_title,
                        'content': '\n'.join(current_content).strip()
                    })
                section_id = section_match.group(1)
                section_title = section_match.group(2).strip()
                current_section = section_id
                current_content = [line]
            else:
                if current_section:
                    current_content.append(line)
        if current_section:
            sections.append({
                'section': current_section,
                'title': section_title,
                'content': '\n'.join(current_content).strip()
            })
        filtered_sections = []
        for section in sections:
            content = section['content'].strip()
            if len(content) > 50:
                if not re.match(r'^[\d\W\s]+$', content):
                    filtered_sections.append(section)
        return filtered_sections
