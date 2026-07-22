import os, re, yaml
from docling.document_converter import DocumentConverter


def extract_text_from_pdf_with_docling(pdf_path: str) -> str:
    """使用Docling从PDF提取结构化文本"""
    try:
        converter = DocumentConverter()
        document = converter.convert(pdf_path)
        return document.text
    except Exception as e:
        print(f"Docling解析失败，回退到PyMuPDF: {e}")
        import fitz
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()
        return full_text

def split_3gpp_sections(text:str, spec_id:str)->list:
    """按3GPP章节标题分割，返回块列表。改进的3GPP格式支持。"""
    pattern = re.compile(r'^(\d+(?:\.\d+)*[A-Z]?(?:\.\d+)*)(?:\s{2,})(.+?)(?=\n\d+(?:\.\d+)*[A-Z]?(?:\.\d+)*\s{2,}|\Z)', re.MULTILINE | re.DOTALL)
    parts = pattern.split(text)
    chunks = []

    if len(parts) < 4:
        return [{"section": "", "content": text}]

    for i in range(1, len(parts), 3):
        sec_num = parts[i].strip()
        sec_title = parts[i+1].strip()
        content = parts[i+2].strip() if (i+2) < len(parts) else ""
        if len(content) < 30:
            continue

        full_title = f"{sec_num} {sec_title}".strip()

        if len(content) > 800:
            paras = re.split(r"\n\n", content)
            sub_chunks = []
            cur = ""
            for p in paras:
                if len(cur) + len(p) < 700:
                    cur += "\n\n" + p if cur else p
                else:
                    if cur:
                        sub_chunks.append(cur.strip())
                    cur = p
            if cur:
                sub_chunks.append(cur.strip())
            for j, sub in enumerate(sub_chunks):
                chunks.append({"section": f"{sec_num}.{j+1}", "title": full_title, "content": sub})
        else:
            chunks.append({"section": sec_num, "title": full_title, "content": content})

    return chunks

def generate_markdown_chunks(pdf_path:str, output_dir: str, spec_id:str, meta_extra:dict):
    """主流程：提取-》分块-》生成.md"""
    os.makedirs(output_dir, exist_ok=True)
    text = extract_text_from_pdf_with_docling(pdf_path)
    chunks = split_3gpp_sections(text, spec_id)

    for i, chunk in enumerate(chunks):
        meta = {
            "type": "3gpp",
            "spec_id": spec_id,
            "section": chunk.get("section", ""),
            "title": chunk.get("title", f"{spec_id} {chunk.get('section', '')}"),
            **meta_extra
        }
        yaml_header = yaml.dump(meta, allow_unicode=True, default_flow_style=False)
        full_content  = f"---\n{yaml_header}---\n\n{chunk['content']}"
        fname = f"{spec_id}_{chunk.get('section', 'unknown')}_{i}.md"
        fpath = os.path.join(output_dir, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(full_content)

    print(f"已生成{len(chunks)}个知识块，保存在{output_dir}")

if __name__ == "__main__":
    # 支持多个3GPP文件进行处理
    pdf_files = [
        ("raw_3gpps/ts_129212v190100p.pdf", "TS 29.212"),
        ("raw_3gpps/ts_124229v190600p.pdf", "TS 24.229"),
        ("raw_3gpps/ts_129213v190300p.pdf", "TS 29.213"),
        ("raw_3gpps/ts_129061v190100p.pdf", "TS 29.061"),
    ]

    for pdf_path, spec_id in pdf_files:
        if os.path.exists(pdf_path):
            output_dir = f"knowledge_base/3gpp/{spec_id.replace('.', '_')}/processed"
            generate_markdown_chunks(
                pdf_path=pdf_path,
                output_dir=output_dir,
                spec_id=spec_id,
                meta_extra={
                    "interface": "Gx",
                    "domain": "VoLTE",
                    "tags": ["3GPP", "策略控制", "PCC", "Diameter"]
                }
            )
        else:
            print(f"文件不存在: {pdf_path}")
