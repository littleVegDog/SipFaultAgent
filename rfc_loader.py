import re
import os
import requests
import yaml
from typing import List, Dict


# ==================== Metadata 增强 ====================

RFC_PROTOCOL_MAP = {
    '3261': 'SIP', '3262': 'SIP', '3263': 'SIP', '3264': 'SIP',
    '3265': 'SIP', '3311': 'SIP', '3323': 'SIP', '3325': 'SIP',
    '3428': 'SIP', '3515': 'SIP', '3840': 'SIP', '3841': 'SIP',
    '4028': 'SIP', '4320': 'SIP', '4411': 'SIP', '4412': 'SIP',
    '4474': 'SIP', '4488': 'SIP', '4538': 'SIP', '4916': 'SIP',
    '5393': 'SIP', '5621': 'SIP', '5626': 'SIP', '5630': 'SIP',
    '5922': 'SIP', '5939': 'SIP', '6026': 'SIP', '6140': 'SIP',
    '6141': 'SIP', '6665': 'SIP', '3588': 'Diameter',
    '4006': 'Diameter', '4072': 'Diameter', '4740': 'Diameter',
    '5516': 'Diameter', '6733': 'Diameter', '2327': 'SDP',
    '4566': 'SDP', '3550': 'RTP', '3551': 'RTP', '3711': 'SRTP',
    '2617': 'HTTP', '7235': 'HTTP', '2246': 'TLS', '5246': 'TLS',
    '8446': 'TLS', '6347': 'DTLS',
}

SIP_METHODS = {'INVITE', 'ACK', 'BYE', 'CANCEL', 'REGISTER', 'OPTIONS',
               'PRACK', 'SUBSCRIBE', 'NOTIFY', 'PUBLISH', 'MESSAGE',
               'REFER', 'INFO', 'UPDATE'}

SIP_HEADERS = {'Call-ID', 'CSeq', 'From', 'To', 'Via', 'Contact',
               'Route', 'Record-Route', 'Max-Forwards', 'WWW-Authenticate',
               'Authorization', 'Proxy-Authenticate', 'Content-Type',
               'Content-Length', 'Expires', 'Allow', 'Supported', 'Require'}


def extract_protocol_from_rfc(rfc_number: str) -> str:
    """基于 RFC 编号返回协议名称"""
    return RFC_PROTOCOL_MAP.get(rfc_number, '')


def extract_response_code(section_title: str) -> str:
    """从章节标题提取 SIP 响应码，如 '401 Unauthorized' → '401'"""
    if not section_title:
        return ''
    m = re.match(r'^(\d{3})\b', section_title.strip())
    return m.group(1) if m else ''


def extract_keywords(text: str, section_title: str = '') -> List[str]:
    """从章节内容提取协议关键词（SIP 方法、响应码、常见术语）"""
    keywords = set()
    text_upper = text.upper()
    for method in SIP_METHODS:
        if re.search(r'\b' + method + r'\b', text_upper):
            keywords.add(method)
    resp_match = re.search(r'\b(\d{3})\b', section_title)
    if resp_match:
        keywords.add(resp_match.group(1))
    common_terms = ['authentication', 'authorization', 'proxy', 'registrar',
                    'session', 'dialog', 'transaction', 'transport', 'media',
                    'SDP', 'RTP', 'DTLS', 'TLS', 'TCP', 'UDP', 'Diameter']
    for term in common_terms:
        if re.search(r'\b' + term + r'\b', text, re.IGNORECASE):
            keywords.add(term)
    return sorted(list(keywords))[:10]


# ==================== 下载 ====================

def download_rfc(rfc_number: int, output_dir: str = "raw_rfcs") -> str:
    """从 rfc-editor.org 下载单个 RFC 原始文本"""
    url = f"https://www.rfc-editor.org/rfc/rfc{rfc_number}.txt"
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"rfc{rfc_number}.txt")
    if os.path.exists(file_path):
        print(f"[跳过] RFC {rfc_number} 已存在")
        return file_path
    print(f"[下载] RFC {rfc_number} ...", end=" ")
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 404:
            print(f"不存在 (404)")
            return None
        resp.raise_for_status()
        with open(file_path, "wb") as f:
            f.write(resp.content)
        print(f"完成")
        return file_path
    except Exception as e:
        print(f"失败: {e}")
        return None


def download_rfcs_range(start: int, end: int, output_dir: str = "raw_rfcs") -> List[str]:
    """批量下载 start~end 范围内的 RFC，自动跳过不存在的编号"""
    downloaded = []
    for num in range(start, end + 1):
        path = download_rfc(num, output_dir)
        if path:
            downloaded.append(path)
    print(f"批量下载结束，成功 {len(downloaded)} 个")
    return downloaded


def download_rfcs_list(rfc_list: List[int], output_dir: str = "raw_rfcs") -> List[str]:
    """批量下载指定列表中的 RFC，自动跳过不存在的编号"""
    downloaded = []
    for num in rfc_list:
        path = download_rfc(num, output_dir)
        if path:
            downloaded.append(path)
    print(f"批量下载结束，成功 {len(downloaded)} 个")
    return downloaded


# ==================== 清洗 ====================

def clean_text(text: str) -> str:
    """
    移除 RFC 原始文本中的页眉、页脚、版权声明、换页符等噪声。
    处理单行和多行格式的噪音。
    """
    # 换页符 → 换行
    text = text.replace('\f', '\n')

    # 单行页脚：Rosenberg, et. al.          Standards Track                     [Page 8]
    text = re.sub(r'\n[^\n]*?\[Page \d+\][^\n]*\n', '\n', text)

    # 多行页眉：RFC 3261 紧跟协议名跨多行
    text = re.sub(r'\n(RFC\s+\d+[^\n]*\n)+', '\n', text)

    # 版权声明块（跨多行，常见于 2008 年后的 RFC）
    text = re.sub(
        r'\n[Cc]opyright\s+\(?c\)?\s*\d{4}.*?'
        r'(?:IETF Trust and the persons identified as the document authors\.?'
        r'|All rights reserved\.?)'
        r'[^\n]*\n',
        '\n',
        text,
        flags=re.DOTALL
    )

    # 多次空行合并
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def skip_table_of_contents(text: str) -> str:
    """
    跳过目录部分（Table of Contents），返回正文开始位置之后的文本。

    直接以 "Table of Contents" 为界，返回其后的全部内容。
    TOC 条目行（如 "1   Introduction .................... 5"）会在后续
    split_into_sections 的 title_clean 步骤中被清理掉（去除点线页码），
    不影响最终 chunk 质量。
    """
    toc_start = text.find('Table of Contents')
    if toc_start == -1:
        return text
    return text[toc_start + len('Table of Contents'):]


# ==================== 解析 & 写文件 ====================

def parse_rfc_meta(text: str) -> Dict:
    """从清洗后的文本中提取 RFC 编号、标题和摘要"""
    rfc_num = ""
    m = re.search(r'Request for Comments:\s*(\d+)', text)
    if m:
        rfc_num = m.group(1)
    else:
        m = re.search(r'RFC\s+(\d+)', text)
        if m:
            rfc_num = m.group(1)

    title = ""
    abstract = ""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith('RFC') and rfc_num in line:
            if i + 1 < len(lines) and lines[i + 1].strip():
                title = lines[i + 1].strip()
                break

    # 提取 Abstract（紧跟 title 之后的几行）
    abs_start = text.lower().find('abstract')
    if abs_start != -1:
        abs_line_start = text.find('\n', abs_start)
        if abs_line_start != -1:
            abs_block = text[abs_line_start:].split('\n\n')[0].strip()
            abstract = re.sub(r'\s+', ' ', abs_block)

    return {"rfc_number": rfc_num, "title": title, "abstract": abstract}


def split_into_sections(text: str) -> List[Dict]:
    """
    将 RFC 正文按章节标题切分为若干 section。
    章节标题格式：行首数字或大写字母开头，数字后有1+空格，跟标题文字。
    匹配例如：1. Introduction、7.1 Requests、21.4.4 403 Forbidden、A Table of Timer Values
    """
    # 匹配：编号(可带点) + 至少1个空格 + 标题文字
    # 支持格式：1 Introduction、1. Introduction、7.1 Requests、21.4.4 403 Forbidden、A Table
    pattern = re.compile(r'^([A-Z]|\d+(?:\.\d+)*\.?)\s{1,}(.+)$', re.MULTILINE)
    matches = list(pattern.finditer(text))

    # Fallback：章节标题完全匹配不到时，将整段正文作为一个 section 返回
    if not matches:
        return [{"section": "", "section_title": "", "content": text.strip()}]

    sections = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sec_num = match.group(1)
        title_raw = match.group(2)

        # 清理标题中的省略号点线和页码（TOC 条目格式如 "Introduction . . . . . . . . . . . . . . . . . .  4"）
        title_clean = re.sub(r'\s*\.{2,}\s*\d+\s*$', '', title_raw).strip()
        if not title_clean:
            title_clean = title_raw.strip()

        content = text[start:end].strip()

        # 跳过 TOC 条目：标题中含省略号点线，说明是目录项而非正文章节
        if re.search(r'\.{2,}', title_raw):
            continue

        sections.append({
            "section": sec_num,
            "section_title": title_clean,
            "content": content
        })
    return sections


def write_rfc_as_md(
    file_path: str,
    output_dir: str = "knowledge_base/rfc",
    meta_extra: dict = None
) -> int:
    """
    主流程：读取原始 RFC 文本 → 清洗 → 解析元数据 → 写 .md 文件。

    将 RFC 每个章节单独写成一个 .md 文件（YAML 头 + 正文），
    供 document_loader.py 统一读取再做 semantic_chunk。

    参数:
        file_path: 原始 .txt 文件路径（如 raw_rfcs/rfc4924.txt）
        output_dir: 输出的 .md 文件存放目录
        meta_extra: 附加元数据（如 {"tags": ["SIP", "协议规范"]}）

    返回:
        写入的 .md 文件数量
    """
    # 从文件名直接提取 RFC 编号，避免正文引用其他 RFC 时误提取
    rfc_number = os.path.basename(file_path).replace('rfc', '').replace('.txt', '')

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        raw_text = f.read()

    cleaned = clean_text(raw_text)
    rfc_info = parse_rfc_meta(cleaned)
    body = skip_table_of_contents(cleaned)
    sections = split_into_sections(body)

    os.makedirs(output_dir, exist_ok=True)
    default_meta = {
        "type": "rfc",
        "tags": ["RFC", "SIP", "协议规范"]
    }
    if meta_extra:
        default_meta.update(meta_extra)

    count = 0
    suspicious = []  # 调试：记录 fallback 文件
    first_section = True
    for sec in sections:
        meta = {
            **default_meta,
            "rfc_number": rfc_number,
            "title": rfc_info["title"],
            "section": sec["section"],
            "section_title": sec["section_title"],
            "protocol": extract_protocol_from_rfc(rfc_number),
            "response_code": extract_response_code(sec["section_title"]),
            "keywords": extract_keywords(sec["content"], sec["section_title"]),
        }

        # Fallback 的 section 为空，打印来源信息
        if not sec["section"]:
            suspicious.append({
                "file": file_path,
                "rfc": rfc_number,
                "content_preview": sec["content"][:100],
            })

        fname = f"rfc{rfc_number}_{sec['section'].replace('.', '_')}.md"
        fpath = os.path.join(output_dir, fname)

        # 首个 section 的正文前面拼接 abstract（对协议检索很有用）
        content = sec["content"]
        if first_section and rfc_info.get("abstract"):
            content = f"【协议摘要】{rfc_info['abstract']}\n\n{content}"
            first_section = False

        with open(fpath, 'w', encoding='utf-8') as f:
            yaml_str = yaml.dump(meta, allow_unicode=True, default_flow_style=False)
            f.write(f"---\n{yaml_str}---\n\n")
            f.write(content)
        count += 1

    # 只打印有问题的 RFC（fallback section=空 的那些）
    if suspicious:
        for s in suspicious:
            print(f"[可疑] 源文件: {s['file']}  rfc: {s['rfc']}  内容片段: {s['content_preview'][:80]!r}")

    return count


# ==================== 批量入口 ====================

def process_all_raw_rfcs(
    raw_dir: str = "raw_rfcs",
    output_dir: str = "knowledge_base/rfc",
    meta_extra: dict = None
) -> int:
    """扫描 raw_dir 下所有 .txt 文件，统一走 write_rfc_as_md"""
    total = 0
    for fname in sorted(os.listdir(raw_dir)):
        if fname.lower().endswith('.txt'):
            path = os.path.join(raw_dir, fname)
            try:
                n = write_rfc_as_md(path, output_dir, meta_extra)
                total += n
            except Exception as e:
                print(f"[错误] {fname}: {e}")
    print(f"\n总计写入 {total} 个 .md 文件")
    return total


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("用法:")
        print("  下载 RFC 范围:  python rfc_loader.py download 3000 6800")
        print("  下载 RFC 列表:  python rfc_loader.py download_list 3000,3001,3002,4000")
        print("  转换 MD:   python rfc_loader.py convert raw_rfcs knowledge_base/rfc")
        sys.exit(1)

    action = sys.argv[1]

    if action == "download":
        start = int(sys.argv[2])
        end = int(sys.argv[3])
        download_rfcs_range(start, end)

    elif action == "download_list":
        rfc_str_list = sys.argv[2].split(',')
        rfc_list = [int(x.strip()) for x in rfc_str_list]
        download_rfcs_list(rfc_list)

    elif action == "convert":
        raw_dir = sys.argv[2] if len(sys.argv) > 2 else "raw_rfcs"
        output_dir = sys.argv[3] if len(sys.argv) > 3 else "knowledge_base/rfc"
        process_all_raw_rfcs(raw_dir, output_dir)

    else:
        print(f"未知动作: {action}")
