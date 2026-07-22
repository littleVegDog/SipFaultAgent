import os
import re
import json
import logging
from sentence_transformers import SentenceTransformer
from typing import List, Optional
from dataclasses import dataclass
from prompts import PROTOCOL_QUERY_PROMPT

# Chroma 相关导入
import chromadb
from chromadb import Client
from chromadb.config import Settings

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from logger_config import user_print, info_print, debug_print, error_print, warn_print


@dataclass
class Document:
    id: str
    text: str
    meta: dict


class SbcRAG:
    """
    RAG 知识库，使用 ChromaDB 作为向量存储后端。

    ChromaDB 自动持久化，每次 add() 后数据即写入磁盘，
    无需手动调用 save()。
    """
    def __init__(self, embed_model: str, reranker=None, enable_rerank: bool = True, chroma_path: str = "chroma_db"):
        self.model = SentenceTransformer(embed_model)
        self.documents: List[Document] = []
        self.query_prompt = "为这个句子生成表示以用于检索相关文章："
        self.reranker = reranker
        self.enable_rerank = enable_rerank
        # Chroma数据库相关
        self.chroma_path = chroma_path
        os.makedirs(chroma_path, exist_ok=True)
        # 使用PersistentClient确保本地持久化
        self.client = Client(Settings(chroma_location=chroma_path, is_persistent=True))
        self.collection = None
        self.hybrid_retriever = None  # Hybrid search (BM25 + Dense)
        self._initialize_collection()

    def add_document(self, document: Document):
        emb = self.model.encode(document.text)
        self.documents.append(document)
        self._add_document_to_chroma(document, emb)

    def add_documents_batch(self, documents: List[Document], batch_size: int = 100):
        """批量添加文档，分批编码避免内存溢出，直接写入 ChromaDB"""
        texts = [doc.text for doc in documents]
        embs = self.model.encode(texts, batch_size=batch_size, show_progress_bar=True)
        for doc, emb in zip(documents, embs):
            self.documents.append(doc)
        self._add_documents_to_chroma(documents, embs)

    def search(self, query: str, top_k: int = 3, filter_meta: Optional[dict] = None,
               input_enhancer=None, use_parent_context=True, use_hybrid: bool = True) -> List[Document]:
        logger.info(f"开始RAG检索: 查询='{query}', top_k={top_k}, hybrid={use_hybrid}")
        queries = [query]
        if input_enhancer:
            result = input_enhancer.enhance(query)
            expanded = result.get("expanded_queries", [])
            if expanded:
                queries = expanded
                logger.info(f"查询扩展: {expanded}")

        # 选择检索策略
        search_fn = self._search_hybrid if (use_hybrid and self.hybrid_retriever and self.hybrid_retriever.is_ready) else self._search_single

        all_candidates = {}
        for i, q in enumerate(queries):
            logger.info(f"执行第{i+1}个查询: '{q}'")
            candidates = search_fn(q, top_k=top_k * 3, filter_meta=filter_meta)
            logger.info(f"查询 '{q}' 检索到 {len(candidates)} 个候选文档")
            for doc in candidates:
                if doc.id not in all_candidates:
                    all_candidates[doc.id] = doc

        candidate_docs = list(all_candidates.values())
        logger.info(f"去重后共有 {len(candidate_docs)} 个候选文档")

        if self.enable_rerank and self.reranker and len(candidate_docs) > top_k:
            logger.info("应用rerank排序")
            candidate_docs = self.reranker.rerank(query, candidate_docs, top_k=top_k)
        else:
            candidate_docs = candidate_docs[:top_k]

        # Parent-Child上下文增强：子块（rfc_subsection）替换为完整父块内容
        if use_parent_context:
            logger.info("启用Parent-Child上下文增强")
            enhanced_docs = []
            parent_ids = set()
            parent_cache = {}

            for doc in candidate_docs:
                pid = doc.meta.get('parent_section_id', '')
                # 仅对子块（有 parent 且不是自引用的小章节）进行替换
                if pid and doc.meta.get('type') == 'rfc_subsection':
                    parent_ids.add(pid)

            for parent_id in parent_ids:
                # 先查内存，再查 ChromaDB
                parent_doc = self.get_document_by_id(parent_id)
                if not parent_doc:
                    try:
                        results = self.collection.get(ids=[parent_id])
                        if results and results['ids']:
                            pmeta_str = results['metadatas'][0].get('meta', '{}') if results['metadatas'] else '{}'
                            parent_doc = Document(
                                id=results['ids'][0],
                                text=results['documents'][0] if results['documents'] else '',
                                meta=json.loads(pmeta_str)
                            )
                    except Exception:
                        pass
                if parent_doc:
                    parent_cache[parent_id] = parent_doc

            for doc in candidate_docs:
                pid = doc.meta.get('parent_section_id', '')
                if pid and doc.meta.get('type') == 'rfc_subsection' and pid in parent_cache:
                    parent_doc = parent_cache[pid]
                    enhanced_doc = Document(
                        id=doc.id,
                        text=parent_doc.text,
                        meta={**doc.meta, **parent_doc.meta}
                    )
                    enhanced_docs.append(enhanced_doc)
                    logger.debug(f"子块 {doc.id} 替换为父块 {parent_doc.id}")
                else:
                    enhanced_docs.append(doc)

            candidate_docs = enhanced_docs

        logger.info(f"最终返回 {len(candidate_docs)} 个文档")
        return candidate_docs

    def _search_single(self, query: str, top_k: int = 3, filter_meta: Optional[dict] = None) -> List[Document]:
        """单 query 检索（使用 ChromaDB 向量检索）"""
        logger.info(f"执行单次检索: 查询='{query}', top_k={top_k}")
        results = self._search_with_chroma(query, top_k, filter_meta)
        logger.info(f"向量检索完成，返回 {len(results)} 个文档")
        return results

    # ---- Hybrid Search ----

    def enable_hybrid_search(self, alpha: float = 0.5):
        """启用混合检索：构建 BM25 索引（需在所有文档加载后调用）"""
        from hybrid_retriever import HybridRetriever
        self.hybrid_retriever = HybridRetriever(alpha=alpha)
        self.hybrid_retriever.build_index(self.documents)
        info_print(f"混合检索已启用 (alpha={alpha}, {len(self.documents)} 文档)")

    def _search_hybrid(self, query: str, top_k: int = 3, filter_meta: dict = None) -> List[Document]:
        """混合检索：Dense (ChromaDB) + Sparse (BM25) 融合"""
        if not self.hybrid_retriever or not self.hybrid_retriever.is_ready:
            return self._search_with_chroma(query, top_k, filter_meta)

        # Dense: ChromaDB 检索 (扩大候选集)
        dense_top_k = top_k * 3
        dense_results = self._search_with_chroma(query, dense_top_k, filter_meta)
        dense_scores = {}
        for i, doc in enumerate(dense_results):
            # 排名分数: 第一位=1.0, 递减
            dense_scores[doc.id] = 1.0 / (i + 1)

        # Sparse: BM25 检索 + 加权融合
        hybrid_results = self.hybrid_retriever.search(query, top_k=top_k, dense_scores=dense_scores)

        # 结果映射回 Document
        doc_map = {doc.id: doc for doc in dense_results}
        for doc in self.documents:
            if doc.id not in doc_map:
                doc_map[doc.id] = doc

        hybrid_docs = []
        for doc_id, _ in hybrid_results:
            if doc_id in doc_map:
                hybrid_docs.append(doc_map[doc_id])

        return hybrid_docs if hybrid_docs else dense_results[:top_k]

    # ---- ChromaDB 操作 ----

    def _initialize_collection(self):
        """初始化Chroma集合"""
        try:
            self.collection = self.client.get_or_create_collection(
                name="rag_documents",
                metadata={"description": "RAG documents with embeddings"}
            )
        except Exception as e:
            error_print(f"初始化Chroma集合失败: {e}")
            self.collection = self.client.create_collection(
                name="rag_documents",
                metadata={"description": "RAG documents with embeddings"}
            )

    def _add_document_to_chroma(self, document: Document, embedding):
        """添加单个文档到Chroma数据库"""
        try:
            meta_str = json.dumps(document.meta, ensure_ascii=False)
            self.collection.add(
                documents=[document.text],
                embeddings=[embedding.tolist()],
                metadatas=[{"doc_id": document.id, "meta": meta_str}],
                ids=[document.id]
            )
        except Exception as e:
            error_print(f"添加文档到Chroma失败: {e}")

    def _add_documents_to_chroma(self, documents: List[Document], embeddings):
        """批量添加文档到Chroma数据库"""
        try:
            documents_text = [doc.text for doc in documents]
            embeddings_list = [emb.tolist() for emb in embeddings]
            metadatas = [{"doc_id": doc.id, "meta": json.dumps(doc.meta, ensure_ascii=False)} for doc in documents]
            ids = [doc.id for doc in documents]
            self.collection.add(
                documents=documents_text,
                embeddings=embeddings_list,
                metadatas=metadatas,
                ids=ids
            )
        except Exception as e:
            error_print(f"批量添加文档到Chroma失败: {e}")

    def _search_with_chroma(self, query: str, top_k: int, filter_meta: Optional[dict] = None) -> List[Document]:
        """使用Chroma数据库进行向量检索"""
        logger.info(f"Chroma向量检索: 查询='{query}', top_k={top_k}")
        try:
            query_embedding = self.model.encode([query], normalize_embeddings=True)[0]
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k,
                where=filter_meta if filter_meta else None
            )
            docs = []
            if 'ids' in results and results['ids']:
                for i in range(len(results['ids'][0])):
                    doc_id = results['ids'][0][i]
                    text = results['documents'][0][i] if 'documents' in results and results['documents'] else ""
                    meta_data = results['metadatas'][0][i] if 'metadatas' in results and results['metadatas'] else {}
                    meta = {}
                    if 'meta' in meta_data:
                        try:
                            meta = json.loads(meta_data['meta'])
                        except Exception:
                            pass
                    docs.append(Document(id=doc_id, text=text, meta=meta))
            logger.info(f"Chroma检索完成，返回 {len(docs)} 个文档")
            return docs
        except Exception as e:
            logger.error(f"Chroma检索失败: {e}")
            return []

    # ---- 持久化 ----
    # ChromaDB 自动持久化，persist()/save() 仅确保目录存在

    def persist(self, dir_path: str = "kb_store"):
        """ChromaDB已自动持久化，此方法确保目录存在"""
        os.makedirs(dir_path, exist_ok=True)
        info_print(f"知识库已保存至{dir_path}（ChromaDB自动持久化）")

    def save(self, dir_path: str = "kb_store"):
        """ChromaDB已自动持久化"""
        self.persist(dir_path)

    @classmethod
    def load(cls, dir_path: str = "kb_store", embed_model: str = None):
        """从ChromaDB加载已存在的知识库"""
        try:
            chroma_path = os.path.join(dir_path, "chroma_db")
            kb = cls(embed_model, chroma_path=chroma_path)
            return kb
        except Exception as e:
            error_print(f"加载知识库失败: {e}")
            return None

    # ---- 文档管理 ----

    def get_document_by_id(self, doc_id: str) -> Document:
        """根据ID获取文档"""
        for doc in self.documents:
            if doc.id == doc_id:
                return doc
        return None

    def get_parent_document(self, doc: Document) -> Document:
        """根据Child文档获取Parent文档"""
        if 'parent_section_id' in doc.meta:
            parent_id = doc.meta['parent_section_id']
            parent_doc = self.get_document_by_id(parent_id)
            if parent_doc:
                return parent_doc
        return doc

    def get_sibling_documents(self, doc: Document) -> List[Document]:
        """获取同父文档的所有兄弟文档"""
        if 'parent_section_id' not in doc.meta:
            return [doc]
        parent_id = doc.meta['parent_section_id']
        siblings = []
        for document in self.documents:
            if document.meta.get('parent_section_id') == parent_id and document.id != doc.id:
                siblings.append(document)
        return siblings

    def get_documents_by_section(self, section_id: str) -> List[Document]:
        """根据章节ID获取所有该章节下的文档"""
        section_docs = []
        for document in self.documents:
            if (document.meta.get('parent_section_id') == section_id or
                    document.meta.get('section') == section_id):
                section_docs.append(document)
        return section_docs

    def delete_document(self, doc_id: str) -> bool:
        """删除指定ID的文档及其在Chroma中的向量"""
        try:
            self.collection.delete(ids=[doc_id])
            self.documents = [doc for doc in self.documents if doc.id != doc_id]
            info_print(f"文档 {doc_id} 已从知识库中删除")
            return True
        except Exception as e:
            error_print(f"删除文档失败: {e}")
            return False

    def delete_documents_by_metadata(self, filter_meta: dict) -> int:
        """根据元数据过滤删除文档"""
        try:
            result = self.collection.get(where=filter_meta)
            ids_to_delete = result['ids']
            if not ids_to_delete:
                info_print("未找到匹配的文档")
                return 0
            self.collection.delete(ids=ids_to_delete)
            self.documents = [doc for doc in self.documents if doc.id not in ids_to_delete]
            info_print(f"已删除 {len(ids_to_delete)} 个文档")
            return len(ids_to_delete)
        except Exception as e:
            error_print(f"批量删除文档失败: {e}")
            return 0

    # ---- 协议查询 ----

    def protocol_query(self, query: str, top_k: int = 5, llm_client=None, model_id: str = None) -> str:
        """
        处理协议查询的完整流程：
        1. RAG检索相关文档
        2. LLM总结和解释
        3. 返回用户友好的解释
        """
        logger.info(f"开始协议查询: '{query}', top_k={top_k}")
        if not llm_client or not model_id:
            docs = self.search(query, top_k=top_k)
            if docs:
                return f"检索到的文档片段：\n\n" + "\n\n".join(
                    [doc.text[:500] + "..." if len(doc.text) > 500 else doc.text for doc in docs[:3]])
            else:
                return "未找到相关协议文档"

        docs = self.search(query, top_k=top_k)
        if not docs:
            return "未找到相关协议文档"

        combined_content = self._build_intelligent_content(query, docs)
        summary_prompt = PROTOCOL_QUERY_PROMPT.format(query=query, combined_content=combined_content)

        try:
            response = llm_client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": "你是一个专业的通信协议解释器，擅长解释SIP、RFC等协议规范。"},
                    {"role": "user", "content": summary_prompt}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM调用失败: {str(e)}")
            return f"查询结果:\n\n" + "\n\n".join([doc.text[:500] + "..." if len(doc.text) > 500 else doc.text for doc in
                                                   docs[:3]]) + f"\n\n(注意: LLM总结失败，仅显示原始文档. 错误: {str(e)})"

    def _build_intelligent_content(self, query: str, docs: List[Document]) -> str:
        """智能构建查询内容：基于查询与文档标题匹配度决定返回完整章节还是单片段"""
        doc_scores = []
        query_words = set(query.lower().split())
        for i, doc in enumerate(docs):
            title = doc.meta.get('section_title', '')
            if not title:
                title = doc.text[:100].lower()
            title_words = set(title.lower().split())
            intersection = query_words & title_words
            union = query_words | title_words
            if not union:
                score = 0
            else:
                score = len(intersection) / len(union)
            doc_scores.append((doc, score))
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        top_docs = doc_scores[:3]
        should_return_complete = any(score > 0.3 for _, score in top_docs)
        if should_return_complete:
            return self._build_complete_section_content(docs)
        else:
            return "\n\n".join([f"文档片段 {i + 1}:\n{doc.text}" for i, doc in enumerate(docs)])

    def _build_complete_section_content(self, docs: List[Document]) -> str:
        """构建完整章节内容"""
        section_groups = {}
        for doc in docs:
            section_id = doc.meta.get('parent_section_id') or doc.meta.get('section', 'unknown')
            if section_id not in section_groups:
                section_groups[section_id] = []
            section_groups[section_id].append(doc)
        content_parts = []
        for section_id, section_docs in section_groups.items():
            if len(section_docs) > 1 or (section_docs and section_docs[0].meta.get('section_title')):
                section_title = section_docs[0].meta.get('section_title', '未知章节')
                section_num = section_docs[0].meta.get('section', section_id)
                all_content = '\n'.join([doc.text for doc in section_docs])
                content_parts.append(f"### 章节：{section_title} ({section_num})\n{all_content}")
            else:
                content_parts.append(section_docs[0].text)
        return "\n\n".join(content_parts)


# ==================== 知识库构建函数 ====================

def incremental_add(new_files_dir: str = "./knowledge_base/new_docs", cache_dir: str = "kb_store",
                    embed_model: str = None):
    """增量添加新文档到已有知识库"""
    if not os.path.exists(os.path.join(cache_dir, "chroma_db")):
        raise Exception("ChromaDB 缓存不存在，请先执行全量构建。")
    kb = SbcRAG.load(cache_dir, embed_model)
    from document_loader import load_all_md_documents, semantic_chunk
    raw_docs = load_all_md_documents(new_files_dir)
    if not raw_docs:
        info_print("无新增文档。")
        return
    all_chunks = []
    for raw_doc in raw_docs:
        chunk_list = semantic_chunk(raw_doc.content, raw_doc.meta)
        for i, chunk in enumerate(chunk_list):
            doc_id = f"{raw_doc.meta.get('title', 'doc')}_incr_{i}"
            all_chunks.append(Document(id=doc_id, text=chunk.content, meta=chunk.metadata))
    kb.add_documents_batch(all_chunks)
    info_print(f"增量添加完成，共添加 {len(raw_docs)} 个文档。")


def _scan_md_files(base_dir: str) -> list:
    """扫描目录下所有 .md 文件，只返回路径列表"""
    paths = []
    for root, _, files in os.walk(base_dir):
        for f in files:
            if f.endswith(".md"):
                paths.append(os.path.join(root, f))
    return paths


def _mem_usage() -> float:
    """返回当前进程 RSS 内存（MB）"""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return -1.0


def _write_batch_state(cache_dir: str, last_batch_idx: int, total_processed_files: int):
    """写入断点状态文件"""
    state_path = os.path.join(cache_dir, "_batch_state.json")
    state = {"last_batch_idx": last_batch_idx, "total_processed_files": total_processed_files}
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f)


def _read_batch_state(cache_dir: str) -> Optional[dict]:
    """读取断点状态文件"""
    state_path = os.path.join(cache_dir, "_batch_state.json")
    if not os.path.exists(state_path):
        return None
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return None


def _remove_batch_state(cache_dir: str):
    """清除断点状态文件"""
    state_path = os.path.join(cache_dir, "_batch_state.json")
    if os.path.exists(state_path):
        os.remove(state_path)


def _write_complete_marker(cache_dir: str):
    """写入知识库构建完成标记"""
    marker_path = os.path.join(cache_dir, ".kb_complete")
    with open(marker_path, "w", encoding="utf-8") as f:
        f.write("1")


def _check_complete_marker(cache_dir: str) -> bool:
    """检查知识库是否完整构建"""
    marker_path = os.path.join(cache_dir, ".kb_complete")
    return os.path.exists(marker_path)


def build_knowledge_base(base_dir: str, emb_model: str,
                         cache_dir: str = "kb_store",
                         force_rebuild: bool = False,
                         reranker=None,
                         file_batch_size: int = 2000) -> SbcRAG:
    """
    分批构建知识库（ChromaDB 后端），支持断点续建。

    流程：
    1. 检查 ChromaDB 缓存：完整 → 加载返回；不完整 → 断点续建；无 → 全新构建
    2. 分批扫描 → 切块 → 向量化 → 直接写入 ChromaDB（自动持久化）
    3. 每批记录断点，崩溃后可继续
    """
    from document_loader import parse_markdown_with_yaml, semantic_chunk

    kb = None
    start_batch_idx = 0
    chroma_db_path = os.path.join(cache_dir, "chroma_db")

    # ---- 第一关：检查已有缓存 ----
    if not force_rebuild and os.path.exists(chroma_db_path):
        if _check_complete_marker(cache_dir):
            info_print("从ChromaDB缓存中加载知识库")
            kb = SbcRAG.load(cache_dir, emb_model)
            if kb is not None:
                if reranker:
                    kb.reranker = reranker
                return kb
        else:
            info_print("检测到不完整的知识库缓存，尝试从断点继续构建...")
            kb = SbcRAG.load(cache_dir, emb_model)
            if kb is not None:
                if reranker:
                    kb.reranker = reranker
                batch_state = _read_batch_state(cache_dir)
                if batch_state is not None:
                    start_batch_idx = batch_state["last_batch_idx"] + 1
                    info_print(f"  已恢复 {batch_state['total_processed_files']} 个文件，"
                              f"从第 {start_batch_idx + 1} 批继续构建...")
                else:
                    info_print("  无断点信息，将重新全量构建。")
                    kb = None

    # ---- 第二关：全新构建 ----
    if kb is None:
        kb = SbcRAG(emb_model, reranker=reranker, chroma_path=chroma_db_path)
        start_batch_idx = 0

    # ---- 第三关：统一批处理 ----
    all_paths = _scan_md_files(base_dir)
    total_files = len(all_paths)

    if start_batch_idx == 0:
        info_print(f"正在构建知识库：初始化 embedding model...")
        info_print(f"共发现 {total_files} 个 .md 文件，每批处理 {file_batch_size} 个")

    start_idx = start_batch_idx * file_batch_size

    for batch_idx in range(start_idx, total_files, file_batch_size):
        batch_paths = all_paths[batch_idx:batch_idx + file_batch_size]
        batch_chunks = []

        for path in batch_paths:
            try:
                raw_doc = parse_markdown_with_yaml(path)
                # semantic_chunk() now returns List[Chunk] with preserved metadata
                chunk_list = semantic_chunk(raw_doc.content, raw_doc.meta)
                for i, chunk in enumerate(chunk_list):
                    doc_id = f"{raw_doc.meta.get('title', 'doc')}_chunk_{i}"
                    batch_chunks.append(Document(id=doc_id, text=chunk.content, meta=chunk.metadata))
            except Exception as e:
                debug_print(f"  [跳过] 解析失败 {path}: {e}")

        if not batch_chunks:
            continue

        # 向量化 + 直接写入 ChromaDB（自动持久化）
        kb.add_documents_batch(batch_chunks)

        # 记录断点状态
        current_batch_idx = batch_idx // file_batch_size
        processed = min(batch_idx + file_batch_size, total_files)
        _write_batch_state(cache_dir, current_batch_idx, processed)

        batch_num = current_batch_idx + 1
        info_print(f"  批次 {batch_num} 完成 "
                  f"({processed}/{total_files} 文件, 累计 {len(kb.documents)} 个块), "
                  f"当前内存约 {_mem_usage():.0f}MB")

        del batch_chunks

    # ---- 第四关：收尾 ----
    _remove_batch_state(cache_dir)
    _write_complete_marker(cache_dir)
    kb.enable_hybrid_search()
    info_print(f"知识库构建完成，共 {len(kb.documents)} 条文档已持久化至 {cache_dir}")
    return kb


def build_knowledge_base_enhanced(base_dir: str, emb_model: str,
                                  cache_dir: str = "kb_store",
                                  force_rebuild: bool = False,
                                  reranker=None) -> SbcRAG:
    """
    增强版知识库构建：RFC 文档使用 RFCChunker 专用切分。
    ChromaDB 后端，自动持久化。
    """
    from document_loader import load_all_md_documents, semantic_chunk
    from chunker import RFCChunker

    chroma_db_path = os.path.join(cache_dir, "chroma_db")

    if not force_rebuild and os.path.exists(chroma_db_path):
        info_print("从ChromaDB缓存中加载知识库（增强版）")
        kb = SbcRAG.load(cache_dir, emb_model)
        if kb is not None:
            if reranker:
                kb.reranker = reranker
            return kb

    info_print("正在重新构建知识库（增强版）：初始化model...")
    kb = SbcRAG(emb_model, reranker=reranker, chroma_path=chroma_db_path)

    info_print("正在导入rawdata中...")
    raw_docs = load_all_md_documents(base_dir)

    info_print("正在chunk中...")
    all_chunks = []
    for raw_doc in raw_docs:
        meta = raw_doc.meta
        doc_type = meta.get('type', '')
        if doc_type == 'rfc':
            rfc_chunker = RFCChunker()
            try:
                chunks = rfc_chunker.chunk(raw_doc.content, meta)
                for i, chunk in enumerate(chunks):
                    doc_id = f"{meta.get('title', 'doc')}_rfc_chunk_{i}"
                    all_chunks.append(Document(id=doc_id, text=chunk.content, meta=chunk.metadata))
            except Exception as e:
                info_print(f"RFC chunker处理失败，使用默认方法: {e}")
                chunk_list = semantic_chunk(raw_doc.content, meta)
                for i, chunk in enumerate(chunk_list):
                    doc_id = f"{meta.get('title', 'doc')}_chunk_{i}"
                    all_chunks.append(Document(id=doc_id, text=chunk.content, meta=chunk.metadata))
        else:
            chunk_list = semantic_chunk(raw_doc.content, meta)
            for i, chunk in enumerate(chunk_list):
                doc_id = f"{meta.get('title', 'doc')}_chunk_{i}"
                all_chunks.append(Document(id=doc_id, text=chunk.content, meta=chunk.metadata))

    info_print("正在批量向量化并写入ChromaDB...")
    kb.add_documents_batch(all_chunks)

    _write_complete_marker(cache_dir)
    kb.enable_hybrid_search()
    info_print(f"增强版知识库构建完成，共 {len(kb.documents)} 条文档已持久化至 {cache_dir}")
    return kb
