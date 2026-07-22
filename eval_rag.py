"""
RAG 专项评估脚本
测试内容：Recall@K、MRR@K、各优化项（Rerank / Query Expansion）的效果对比

用法:
    python eval_rag.py
"""

import time
import json
from openai import OpenAI
from rag import build_knowledge_base
from reranker import BGEReranker
from input_enhancer import InputEnhancer
from config import (
    EMBED_MODEL, KNOWLEDGE_BASE_DIR, KB_CACHE_DIR,
    RERANKER_MODEL, LLM_BASE_URL, LLM_API_KEY, INPUT_ENHANCER_MODEL
)

# -------- 测试集 --------
# 每项: query + 相关文档的 id 列表（部分匹配即可）
# 建议 15~20 条，覆盖注册/呼叫/认证/媒体等场景
TEST_SET = [
    {"query": "Cseq头域的定义", "doc_ids": ["rfc3261_8_1_1_5", "rfc3261_20_16", "rfc3261_12_2_1_1","rfc3261_25_1"]},
    {"query": "重定向是什么", "doc_ids": ["rfc3261_8_3","rfc3261_13_3_1_2","rfc3261_21_3","rfc3261_25_1","rfc3261_8_1_3_4"]},
    {"query": "REGISTER 401 未授权", "doc_ids": ["rfc3261_8_1_3_5","rfc3261_21_4_2", "rfc3261_22_2","rfc3261_22_3"]},
    {"query": "SIP NOTIFY 方法的作用", "doc_ids": ["rfc6665_3_2","rfc6665_3_2_1","rfc6665_5_4_5","rfc6665_5_4_5","rfc6665_5_4_7","rfc6665_5_4_8","rfc6665_8_1_2"]},
    {"query": "SIP BYE 消息格式", "doc_ids": ["rfc3261_12_3","rfc3261_15", "rfc3261_15_1_1","rfc3261_15_1_2","rfc3261_25_1"]},
    {"query": "INVITE 请求超时", "doc_ids": ["rfc3261_13_2_2","rfc3261_8_1_3_1","rfc3261_12_2_1_2","rfc3261_21_4_9"]},
    {"query": "PRACK 是什么协议", "doc_ids": ["rfc3262_1"]},
    {"query": "SUBSCRIBE NOTIFY 机制", "doc_ids": ["rfc6665_1_1","rfc6665_3_1","rfc6665_3_2", "rfc6665_3_1","rfc6665_3_1_1",
                                                   "rfc6665_3_1_2","rfc6665_3_1_3","rfc6665_3_2","rfc6665_3_2_1"]},
    {"query": "SDP 媒体协商", "doc_ids": ["rfc3264_1"]},
    {"query": "RTP 端口范围", "doc_ids": []},
    {"query": "NAT 穿越 SIP", "doc_ids": []},
    {"query": "486 BUSY HERE", "doc_ids": []},
    {"query": "403 Forbidden 认证失败", "doc_ids": []},
    {"query": "SIP 180 Ringing", "doc_ids": []},
    {"query": "488 Not Acceptable Here", "doc_ids": []},
    {"query": "ACK 消息作用", "doc_ids": []},
    {"query": "CANCEL 请求", "doc_ids": []},
    {"query": "REGISTER 刷新注册", "doc_ids": []},
    {"query": "SIP 路由机制", "doc_ids": []},
]


def compute_recall_mrr(retrieved_docs, relevant_ids, k=5):
    """计算单个 query 的 Recall@K 和 MRR@K"""
    retrieved_ids = [d.id for d in retrieved_docs[:k]]
    relevant_set = set(relevant_ids)

    # Recall
    hits = len(set(retrieved_ids) & relevant_set)
    recall = hits / len(relevant_set) if relevant_set else 0.0

    # MRR
    mrr = 0.0
    for i, doc_id in enumerate(retrieved_ids):
        if doc_id in relevant_set:
            mrr = 1.0 / (i + 1)
            break

    return recall, mrr


def eval_config(kb, test_set, use_rerank, use_expansion, enhancer=None, top_k=5):
    """
    在一种配置下跑完整个测试集，返回指标均值。
    use_rerank 通过 kb.enable_rerank 控制。
    """
    old_rerank = kb.enable_rerank
    kb.enable_rerank = use_rerank

    recalls, mrrs = [], []
    latencies = []

    for item in test_set:
        query = item["query"]
        relevant = item.get("doc_ids", [])

        start = time.time()
        docs = kb.search(
            query=query,
            top_k=top_k,
            input_enhancer=enhancer if use_expansion else None
        )
        elapsed = time.time() - start
        latencies.append(elapsed)

        recall, mrr = compute_recall_mrr(docs, relevant, k=top_k)
        recalls.append(recall)
        mrrs.append(mrr)

    kb.enable_rerank = old_rerank
    return {
        f"Recall@{top_k}": sum(recalls) / len(recalls),
        f"MRR@{top_k}": sum(mrrs) / len(mrrs),
        "AvgLatency(s)": sum(latencies) / len(latencies),
    }


def print_results(title, results):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")
    for k, v in results.items():
        print(f"  {k:<20}: {v:.4f}")


def main():
    print("初始化模型中（首次加载较慢）...")

    # 初始化 reranker（传入 kb 之前就加载好）
    reranker = BGEReranker(RERANKER_MODEL)

    # 初始化 LLM client（query expansion 用）
    llm_client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    enhancer = InputEnhancer(llm_client, INPUT_ENHANCER_MODEL)

    # 加载知识库（传入 reranker）
    kb = build_knowledge_base(
        KNOWLEDGE_BASE_DIR,
        emb_model=EMBED_MODEL,
        cache_dir=KB_CACHE_DIR,
        reranker=reranker
    )
    print(f"知识库加载完成，共 {len(kb.documents)} 条文档\n")

    top_k = 5
    configs = [
        {"title": "基线（无 rerank，无 expansion）",
         "use_rerank": False, "use_expansion": False, "enhancer": None},

        {"title": "+ Rerank",
         "use_rerank": True, "use_expansion": False, "enhancer": None},

        {"title": "+ Query Expansion",
         "use_rerank": False, "use_expansion": True, "enhancer": enhancer},

        {"title": "+ Rerank + Query Expansion（完整）",
         "use_rerank": True, "use_expansion": True, "enhancer": enhancer},
    ]

    all_results = []
    for cfg in configs:
        r = eval_config(
            kb, TEST_SET,
            use_rerank=cfg["use_rerank"],
            use_expansion=cfg["use_expansion"],
            enhancer=cfg["enhancer"],
            top_k=top_k
        )
        print_results(cfg["title"], r)
        all_results.append((cfg["title"], r))

    # 汇总对比
    print(f"\n{'='*50}")
    print("  优化效果对比（相对基线提升）")
    print(f"{'='*50}")
    baseline = all_results[0][1]
    for title, r in all_results[1:]:
        recall_delta = r["Recall@5"] - baseline["Recall@5"]
        mrr_delta = r["MRR@5"] - baseline["MRR@5"]
        print(f"  {title}")
        print(f"    Recall@5 提升: {recall_delta:+.4f}")
        print(f"    MRR@5 提升:    {mrr_delta:+.4f}")

    # 打印延迟
    print(f"\n{'='*50}")
    print("  各配置延迟（秒）")
    print(f"{'='*50}")
    for title, r in all_results:
        print(f"  {title:<45}: {r['AvgLatency(s)']:.3f}s")


if __name__ == "__main__":
    main()
