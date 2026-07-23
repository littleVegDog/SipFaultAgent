# SipFaultAgent

基于 RAG（检索增强生成）的 SBC 智能故障诊断助手。支持 SIP/3GPP 协议查询与故障定位。

## 架构

```
用户输入 → Query Router → 协议查询 / 故障诊断
                              │            │
                         RAG 检索      Agent 推理
                              │            │
                         LLM 解释     工具调用 + RAG
                              │            │
                         结果输出      诊断结论
```

## 核心模块

| 模块 | 文件 | 说明 |
|------|------|------|
| 入口 | `main.py` | 菜单式交互，支持全量构建/增量添加/查询 |
| RAG 系统 | `rag.py` | ChromaDB 向量存储，分批构建 + 断点续建 |
| 混合检索 | `hybrid_retriever.py` | Dense (ChromaDB) + Sparse (BM25) 加权融合 |
| Agent | `agent.py` | ReAct 推理循环，工具调用 |
| 路由 | `router.py` | 协议查询 vs 故障诊断分类 |
| 文档切分 | `chunker.py` | RFCChunker + GPPChunker 协议感知切分 |
| 文档加载 | `document_loader.py` | Markdown 解析 + 语义切分 + 数据清洗 |
| RFC 下载 | `rfc_loader.py` | RFC 批量下载 → 结构化 .md 转换 |
| 3GPP 处理 | `threegpp_pdf_loader.py` | Docling + EasyOCR PDF 解析 |
| 查询增强 | `query_expander.py` | 规则 + LLM 双模式 Query Expansion |
| 重排序 | `reranker.py` | CrossEncoder + Metadata 加权 |
| 输入增强 | `input_enhancer.py` | 查询改写与关键词提取 |
| 评估 | `eval_rag.py` | Recall@K / MRR@K 多配置对比 |
| 配置 | `config.py` | API Key、模型路径（环境变量管理） |
| 提示词 | `prompts.py` | System Prompt + 协议查询模板 |
| 日志 | `logger_config.py` | 前台输出 + 文件日志双通道 |
| 工具 | `tools.py` | SIP 诊断模拟工具 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# Windows PowerShell
$env:LLM_API_KEY = "your-deepseek-key"

# Linux / Mac
export LLM_API_KEY="your-deepseek-key"
```

可选环境变量：`TAVILY_API_KEY`、`SERPAPI_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL_ID`。

### 3. 准备知识库

```bash
# 下载 SIP 相关 RFC
python rfc_loader.py download 3261 6665

# 转换为 Markdown
python rfc_loader.py convert raw_rfcs knowledge_base/rfc
```

### 4. 运行

```bash
python main.py
```

启动后选择：
- `1` — 加载已有知识库直接查询
- `2` — 全量重建知识库
- `3` — 增量添加新文档

## 检索流程

```
Query → QueryExpander → [多路查询]
  → HybridRetriever (Dense + BM25 加权融合)
    → Reranker (CrossEncoder + Metadata boost)
      → Parent-Child 展开 (子块 → 完整父块)
        → LLM 生成回答
```

## 文档类型支持

| 类型 | Chunk 策略 | 说明 |
|------|-----------|------|
| `rfc` | RFCChunker | 按章节编号切分，保留协议结构 |
| `3gpp` | GPPChunker | 3GPP 规范专用切分，支持 OCR |
| `product_doc` | 二级标题切分 | 设备配置、错误码手册 |
| `case` | 二级标题切分 | 故障案例 |
| `community` | 二级标题切分 | 社区文档 |

## Parent-Child 结构

- **Parent**：完整章节内容（1000~3000 tokens）
- **Child**：段落级子块（~500 tokens）

检索时用 Child 召回（精确匹配），返回时替换为 Parent（完整上下文），显著提升 LLM 回答质量。

## eval_rag 评估命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行评估（4 种配置对比）
python eval_rag.py
```

评估配置：基线 / +Rerank / +Query Expansion / +Rerank+Expansion

## 目录结构

```
SipFaultAgent/
├── main.py                  # 入口
├── rag.py                   # RAG 核心
├── hybrid_retriever.py      # 混合检索
├── chunker.py               # 文档切分
├── document_loader.py       # 文档加载
├── rfc_loader.py            # RFC 下载/转换
├── threegpp_pdf_loader.py   # 3GPP PDF 处理
├── query_expander.py        # 查询扩展
├── reranker.py              # 重排序
├── router.py                # 查询路由
├── agent.py                 # 诊断 Agent
├── input_enhancer.py        # 输入增强
├── eval_rag.py              # 评估
├── config.py                # 配置
├── prompts.py               # 提示词
├── logger_config.py         # 日志
├── tools.py                 # 工具
├── requirements.txt         # 依赖
├── knowledge_base/          # 知识库 .md 文件
├── raw_rfcs/                # RFC 原始文本
├── model_files/             # 本地模型
└── chroma_db/               # ChromaDB 向量存储
```

## 项目修订记录

详见 [PROJECT_REVISION_LOG.md](PROJECT_REVISION_LOG.md)
