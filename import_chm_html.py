import os, shutil
from pathlib import Path
from bs4 import BeautifulSoup
from markdownify import markdownify as md_convert
import yaml

# ===== 配置区 =====
CHM_EXTRACTED_DIR = "chm_extracted/SBC_Manual"          # 解压出的 HTML 所在目录
OUTPUT_TEMP_DIR = "temp_kb_import"                      # 临时存放生成的 .md
META = {
    "type": "product_doc",
    "product": "CloudSE2980 产品手册",                    # 修改为实际产品名
    "tags": ["产品文档", "SBC", "配置"],
}
# =================

def clean_html_to_markdown(html_path):
    with open(html_path, 'r', encoding = 'utf-8', errors = 'ignore') as f:
        soup = BeautifulSoup(f, 'html.parser')
    # 移用无用标签
    for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
        tag.decompose()

    # 定位主要内容
    main = soup.find('div', class_ = 'content') or soup.body
    if not main:
        return ""
    return md_convert(str(main), heading_style = "ATX")

def process_chm_html():
    os.makedirs(OUTPUT_TEMP_DIR, exist_ok=True)
    html_files = list(Path(CHM_EXTRACTED_DIR).rglob("*.html")) + list(Path(CHM_EXTRACTED_DIR).rglob("*.htm"))
    count = 0
    for html_file in html_files:
        md_text = clean_html_to_markdown(html_file)
        if not md_text.strip():
            continue
        header = {**META, "title": html_file.stem, "source_file": str(html_file)}
        yaml_header = yaml.dump(header, allow_unicode = True, default_flow_style = False)
        full_content = f"---\n{yaml_header}--\n\n{md_text}"
        out_path = os.path.join(OUTPUT_TEMP_DIR, f"{html_file.stem}.md")
        with open(out_path, 'w', encoding = 'utf-8') as fout:
            fout.write(full_content)
        count += 1

    print(f"成功转换{count}个文档，保存在{OUTPUT_TEMP_DIR}")

if __name__ == "__main__":
    process_chm_html()
