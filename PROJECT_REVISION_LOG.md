# 项目修订记录

## 2026-07-24 — 完整 Chunker 重构 (10项计划)

### 背景
按用户修改计划，系统性重构 chunker 架构：数据清洗前移到 parse 阶段，chunk 只做切分。

### 修改

| # | 文件 | 改动 |
|---|------|------|
| 1 | `chunker.py` | RFCChunker 重写：删除 `_extract_sections()`，直接用 `metadata` 中的 `section_id`/`section_title`；短章节整体返回，长章节按段落分子块；全部带 `parent_section_id` |
| 2 | `chunker.py` | GPPChunker 重写：同上模式 |
| 3 | `chunker.py` | GenericChunker：短文本整体返回，长文本按段落切分，无数据清洗 |
| 4 | `chunker.py` | **新增** ProductChunker（`##` 标题切分）+ CaseChunker（`## 现象/原因/方案` 关键词切分）|
| 5 | `rag.py` | `build_knowledge_base` + `build_knowledge_base_enhanced` + `incremental_add` 统一用 `get_chunker()` 直接分发，废弃 `semantic_chunk()` |
| 6 | `rag.py` | `SbcRAG.load()` 自动调用 `reload_documents()` 填充 `self.documents`（Parent-Child 可用）|
| 7 | `rag.py` | 元数据平铺：`_flatten_meta()` 展开 meta 字段到 Chroma metadata 顶层；`_parse_meta()` 还原；`filter_meta` 查询生效 |
| 8 | `document_loader.py` | 精简为 parse/load 核心：`parse_markdown_with_yaml()` + `load_all_md_documents()` + 数据清洗函数（`is_meaningless_chunk`/`clean_chunk_text` 供 parse 阶段使用）。删除 `chunk_text`/`semantic_chunk`/`_semantic_chunk_old`/`extract_sections`/`_wrap_as_chunks`/`_post_process_chunks` |
| 9 | `tests/` | 更新 `test_document_loader.py` 适配新 API，删除 `TestChunkText`/`TestSemanticChunk` |

### 新架构

```
get_chunker(doc_type)            document_loader.py (parse only)
  ├── 'rfc' → RFCChunker          ├── parse_markdown_with_yaml()
  ├── '3gpp' → GPPChunker         ├── load_all_md_documents()
  ├── 'product_doc' → ProductChunker  ├── is_meaningless_chunk() [parse阶段]
  ├── 'case' → CaseChunker        └── clean_chunk_text()     [parse阶段]
  └── default → GenericChunker
```

### 数据清洗职责

**前移到 parse 阶段**（rfc_loader/3gpp_pdf_loader 转 .md 时调用）：
- `is_meaningless_chunk()` — 过滤噪音
- `clean_chunk_text()` — 清理残余格式

**Chunker 不再做清洗，只做切分。**

---

## 2026-07-24 — Issue #3: 重构 Chunker 架构

### 背景
`semantic_chunk()` 在 `document_loader.py` 中既做通用切分又调用 RFC 专有 chunker，逻辑混乱。`build_knowledge_base` 应像 `build_knowledge_base_enhanced` 一样按文档类型分发到不同 chunker。

### 修改

| 文件 | 改动 |
|------|------|
| `chunker.py` | 新增 `GenericChunker`（处理 case/community/product_doc/default）+ `get_chunker(doc_type)` 分发器 |
| `document_loader.py` | 重写 `semantic_chunk()` → 委托 `get_chunker()`；删除 `_semantic_chunk_old`/`extract_sections`/`_wrap_as_chunks`/`_post_process_chunks` 死代码（~200 行） |

### 新架构

```
get_chunker(doc_type)
  ├── 'rfc'    → RFCChunker      (章节编号切分 + parent_section_id)
  ├── '3gpp'   → GPPChunker      (3GPP 规范专用)
  └── default  → GenericChunker  (## 标题切分 + 滑动窗口 + 数据清洗)
```

---

## 2026-07-23 — Step 3: 创建单元测试 + 整理测试目录

### 修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `tests/test_chunker.py` | **新建** | RFCChunker + GPPChunker 单元测试 (11 tests) |
| `tests/test_hybrid_retriever.py` | **新建** | BM25Okapi + HybridRetriever 单元测试 (13 tests) |
| `tests/test_document_loader.py` | **新建** | document_loader 单元测试 (13 tests) |
| `tests/test_reranker.py` | **新建** | BGEReranker metadata boost 单元测试 (6 tests) |
| `tests/__init__.py` | **新建** | 测试包初始化 |
| `tests/test.py` | 迁移 | 从根目录移入 |
| `tests/test_docling_3gpp.py` | 迁移 | 从根目录移入 |
| `tests/test_rfc_chunker.py` | 迁移 | 从根目录移入 |
| `tests/test_rfc_manual.py` | 迁移 | 从根目录移入 |

### 测试覆盖

```
tests/test_chunker.py ...........  [11 passed]
tests/test_document_loader.py ...  [13 passed]
tests/test_hybrid_retriever.py ..  [需 sentence_transformers]
tests/test_reranker.py .........    [需 sentence_transformers]
```

---

## 2026-07-23 — Step 2: 内存清理

### 修改文件

| 文件 | 改动 |
|------|------|
| `agent.py` | `__init__` 加 `max_memory_turns=20`；`run()` 每轮追加后检查记忆长度，超过上限时保留 system prompt + 最近 N 轮 |
| `rag.py` | 新增 `unload_documents()`（清空内存列表，ChromaDB 保留数据）、`reload_documents()`（从 ChromaDB 恢复）、`document_count` 属性（优先内存，fallback ChromaDB `collection.count()`）；`enable_hybrid_search()` 文档空时自动 reload；`build_knowledge_base` / `build_knowledge_base_enhanced` 构建完成后自动调用 `unload_documents()` |
| `main.py` | `len(kb.documents)` → `kb.document_count`（内存卸载后仍可查询） |

---

## 2026-07-23 — Step 1: 统一异常处理模式

### 背景
根据检视意见，项目中异常处理模式不一致：存在裸 `pass` 静默吞异常、`traceback.print_exc()` 混用、`print()` 与 `logger` 混用等问题。

### 修改文件

| 文件 | 改动 |
|------|------|
| `document_loader.py` | `RFC chunker出错` 异常：`pass` → `logging.exception()` 记录完整 traceback |
| `rag.py` | 父文档 ChromaDB 查询异常：裸 `except: pass` → `logger.warning()`；JSON 反序列化异常：`pass` → `logger.debug()` |
| `chunker.py` | 新增 `logging.getLogger(__name__)`；RFCChunker / GPPChunker 的 `traceback.print_exc()` 全部替换为 `logger.exception()` |

### 规则
- 所有异常处理统一使用 `logging.getLogger(__name__)` 或 `logger_config` 函数
- 禁止裸 `except: pass` — 至少记录 `logger.warning/debug`
- 不再使用 `traceback.print_exc()` — 使用 `logger.exception()` 自动附带 traceback
- 测试文件 (`test_*.py`) 和 CLI 工具 (`rfc_loader.py`) 允许 `print()` 风格

---

## 2026-07-22 — Phase 1 RFC RECALL 提升

### 背景
根据 suggestion.pdf 改进建议，实施第一阶段：RFC 文档召回率优化。目标：Recall@5 从 ~70% 提升到 ~90%。

### 修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `chunker.py` | 修改 | 所有 RFCChunk/GPPChunk 元数据加入 `parent_section_id` 字段 |
| `document_loader.py` | 修改 | `semantic_chunk()` 返回 `List[Chunk]`（保留元数据），新增 `_wrap_as_chunks()` |
| `rag.py` | 修改 | 适配 Chunk→Document 元数据流；修复 Parent-Child 上下文增强（仅替换 rfc_subsection 子块）；集成 Hybrid Search（`_search_hybrid`/`enable_hybrid_search`）；构建完成后自动启用 hybrid |
| `rfc_loader.py` | 修改 | 新增 `RFC_PROTOCOL_MAP`(40+ RFC)、`extract_protocol_from_rfc()`、`extract_response_code()`、`extract_keywords()`；`write_rfc_as_md()` YAML 头自动附加 `protocol`/`response_code`/`keywords` |
| `hybrid_retriever.py` | **新建** | 自实现 `BM25Okapi` + `HybridRetriever`（Dense+BM25 加权融合，α=0.5） |
| `reranker.py` | 修改 | `rerank()` 叠加 metadata boost（response_code +2.0, protocol +1.5, section_title +0.5×overlap, keywords +0.3×match） |
| `PROJECT_REVISION_LOG.md` | 新建 | 本文件：项目修订日志 |

### 数据更新
- 下载 31 个核心 SIP/Diameter RFC（RFC 3265-7118）
- 重新生成 63 个 RFC 的 .md 文件（579,616 个），含新元数据字段

---

## 2026-07-18 — ChromaDB 重写 + 分批持久化 + 断点续建

### 背景
从 backup-2026-0717.txt 恢复项目，完成 ChromaDB 迁移。

### 修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `rag.py` | 重写 | 完全切换到 ChromaDB 后端；保留分批构建和断点续建；新增 `protocol_query()`、`delete_document()`、`delete_documents_by_metadata()`、`build_knowledge_base_enhanced()` |
| `main.py` | 修改 | 菜单系统 + RouterAgent 集成 + 文档删除功能 |
| `chunker.py` | 新建 | RFCChunker + GPPChunker 类 |
| `logger_config.py` | 新建 | 日志系统 |
| `query_expander.py` | 新建 | Query Expansion（规则+LLM） |
| `router.py` | 新建 | RouterAgent 查询路由器 |
| `docling_3gpp_loader.py` | 新建 | Docling 3GPP 处理器 |
| `threegpp_pdf_loader.py` | 新建 | 增强版 Docling 3GPP 加载器（OCR 支持） |
| `agent.py` | 修改 | 使用 logger_config；`response_format={"type":"json_object"}` |
| `config.py` | 修改 | `os.getenv()` 保护 API key；`KB_CACHE_DIR="chroma_db"` |
| `prompts.py` | 修改 | 新增 `PROTOCOL_QUERY_PROMPT` |
| `input_enhancer.py` | 修改 | 委托给 `QueryExpander` |
| `document_loader.py` | 修改 | RFC 类型委托给 `RFCChunker` |
| `rfc_loader.py` | 修改 | 新增 `download_rfcs_list()` |
| `reranker.py` | 新建 | BGE-Reranker CrossEncoder |

---

## 2026-07-16 — 分批向量化 + 持久化存储

### 背景
用户要求将向量化与持久化从"全部完成后一次性保存"改为"每批处理完立即保存"。

### 修改文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `rag.py` | 修改 | `build_knowledge_base()` 内移 `save()` 到循环中；新增 `_batch_state.json` 断点追踪 + `.kb_complete` 完整性标记；新增 `_write_batch_state()`/`_read_batch_state()`/`_remove_batch_state()`；断点续建自动恢复 |

---

## 2026-07-15 — 项目初始状态

### 项目结构
- `main.py` — 应用入口
- `agent.py` — LLM Agent
- `rag.py` — RAG 系统（JSON+NumPy 后端）
- `document_loader.py` — 文档加载与切分
- `tools.py` — 诊断工具
- `config.py` — 配置
- `prompts.py` — 系统提示词
- `rfc_loader.py` — RFC 下载与转换
- `3gpp_pdf_loader.py` — 3GPP PDF 处理
- `eval_rag.py` — RAG 评估
- `reranker.py` — 重排序
- `input_enhancer.py` — 输入增强
