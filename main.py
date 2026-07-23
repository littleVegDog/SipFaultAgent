# main.py - 第一行
import transformers.modeling_utils
import torch
from functools import partial

import os
os.environ['NO_PROXY'] = 'api.openai.rnd.huawei.com'
os.environ['no_proxy'] = 'api.openai.rnd.huawei.com'

from openai import OpenAI
from config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL_ID, BASE_DIR, KNOWLEDGE_BASE_DIR, EMBED_MODEL, INPUT_ENHANCER_MODEL, KB_CACHE_DIR, RERANKER_MODEL
from input_enhancer import InputEnhancer
from agent import SipFaultDiagAgent
from router import RouterAgent
from reranker import BGEReranker
from tools import SIPDiagnosticTools
from rag import build_knowledge_base, incremental_add, SbcRAG
import ssl
import json

from logger_config import user_print, info_print, debug_print, error_print, warn_print

def main():
    # 初始化管理功能
    info_print("正在加载知识库...")
    kb = None

    # 首先尝试加载现有知识库
    cached_kb = SbcRAG.load(KB_CACHE_DIR, EMBED_MODEL)
    if cached_kb is not None:
        kb = cached_kb
        info_print("知识库加载成功")
    else:
        info_print("未找到现有知识库，需要全量构建")
        kb = build_knowledge_base(KNOWLEDGE_BASE_DIR, emb_model=EMBED_MODEL, cache_dir=KB_CACHE_DIR, force_rebuild=True)
        info_print("知识库已重新构建并保存")

    llm_client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
    reranker = BGEReranker(RERANKER_MODEL)
    if reranker and kb:
        kb.reranker = reranker
    tools = SIPDiagnosticTools()
    enhancer = InputEnhancer(llm_client, INPUT_ENHANCER_MODEL)
    agent = SipFaultDiagAgent(llm_client, tools, kb, LLM_MODEL_ID, input_enhancer=enhancer)
    router = RouterAgent()

    while True:
        user_print("\n" + "="*60)
        user_print("SBC诊断助手菜单：")
        user_print("1. 输入问题查询")
        user_print("2. 删除文档")
        user_print("3. 查看知识库文档数量")
        user_print("4. 退出")
        user_print("="*60)

        choice = input("请选择操作: ").strip()

        if choice == "1":
            raw = input("\n请输入问题，(输入exit退出):")
            if raw.lower() in ("exit", "quit"):
                break

            # 路由查询，判断是协议查询还是故障诊断
            result = router.route_query(raw)
            confidence = router.get_routing_confidence(raw)

            info_print(f"路由判断 - 类型: {result}, 置信度: 协议={confidence['protocol']:.2f}, 故障诊断={confidence['diagnosis']:.2f}")

            if result == "protocol_query":
                user_print("正在处理协议查询...")
                enhanced = enhancer.enhance(raw)
                enhanced_query = enhanced.get("expanded_queries", [raw])[0] if enhanced.get("expanded_queries") else raw
                user_print(f"处理查询: {enhanced_query}")

                # 使用RAG系统处理协议查询
                result_text = kb.protocol_query(enhanced_query, top_k=5, llm_client=llm_client, model_id=LLM_MODEL_ID)
                user_print("\n=== 协议查询结果 ===")
                user_print(result_text)
            else:
                user_print("故障agent根据问题思考中...\n")
                enhanced = enhancer.enhance(raw)
                enhanced_query = enhanced.get("expanded_queries", [raw])[0] if enhanced.get("expanded_queries") else raw
                keywords = enhanced.get("keywords", [])
                user_print(f"整理查询请求为:{enhanced}")

                conclusion, sources = agent.run(enhanced_query, keywords=keywords)

                user_print("\n=== 最终定位定界结论 ===")
                user_print(conclusion)
                if sources:
                    user_print("\n=== 引用来源 ===")
                    for src in sources:
                        user_print(src)

        elif choice == "2":
            info_print("文档删除模式")
            info_print("1. 按文档ID删除")
            info_print("2. 按元数据条件删除")
            del_choice = input("请选择删除方式: ")

            if del_choice == "1":
                doc_id = input("请输入要删除的文档ID: ").strip()
                if doc_id:
                    kb.delete_document(doc_id)
                    kb.save(KB_CACHE_DIR)
                    info_print("文档删除完成")
                else:
                    info_print("文档ID不能为空")
            elif del_choice == "2":
                info_print("请输入删除条件（例如：{'type': 'rfc'}）")
                try:
                    filter_str = input("删除条件JSON: ")
                    filter_meta = json.loads(filter_str)
                    deleted_count = kb.delete_documents_by_metadata(filter_meta)
                    kb.save(KB_CACHE_DIR)
                    info_print(f"成功删除 {deleted_count} 个文档")
                except Exception as e:
                    info_print(f"条件解析失败: {e}")

        elif choice == "3":
            info_print(f"当前知识库文档数量: {kb.document_count}")

        elif choice == "4":
            info_print("程序退出")
            break
        else:
            info_print("无效选择")

if __name__ == "__main__":
    # 可选择启动模式：全量重建、增量添加、或直接运行
    info_print("请选择启动模式：")
    info_print("1. 直接运行（加载现有知识库）")
    info_print("2. 全量重建知识库")
    info_print("3. 增量添加文档")

    choice = input("请输入选择 (1/2/3): ").strip()

    if choice == "2":
        info_print("正在全量重建知识库...")
        kb = build_knowledge_base(KNOWLEDGE_BASE_DIR, emb_model=EMBED_MODEL, cache_dir=KB_CACHE_DIR, force_rebuild=True)
        info_print("全量知识库重建完成！")
    elif choice == "3":
        new_dir = input("输入新文档目录: ").strip()
        if new_dir:
            incremental_add(new_dir, KB_CACHE_DIR, EMBED_MODEL)
            info_print("增量添加完成！")
        else:
            info_print("未输入有效目录")

    main()
