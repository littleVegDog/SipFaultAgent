import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ===== API 配置（通过环境变量设置，不要硬编码 Key）=====

# Tavily API: export TAVILY_API_KEY="your-key"
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# SerpAPI: export SERPAPI_API_KEY="your-key"
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")

# LLM API: export LLM_API_KEY / LLM_BASE_URL / LLM_MODEL_ID
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "deepseek-v4-pro")

INPUT_ENHANCER_MODEL = "deepseek-v4-pro"

# ===== 模型与路径配置 =====
KNOWLEDGE_BASE_DIR = "knowledge_base"
EMBED_MODEL = os.path.join(BASE_DIR, "model_files", "BAAI", "bge-m3")
KB_CACHE_DIR = "chroma_db"
RERANKER_MODEL = os.path.join(BASE_DIR, "model_files", "BAAI", "bge-reranker-base")
