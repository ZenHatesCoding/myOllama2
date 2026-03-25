from typing import Dict, Any


MODEL_CONTEXT_CONFIGS = {
    "small": {
        "max_tokens": 8192,
        "description": "8k 上下文窗口",
        "summary_max_chars": 300,
        "search_k": 2,
        "chunk_size": 500,
        "chunk_overlap": 50
    },
    "medium": {
        "max_tokens": 32768,
        "description": "32k 上下文窗口",
        "summary_max_chars": 800,
        "search_k": 4,
        "chunk_size": 800,
        "chunk_overlap": 100
    },
    "large": {
        "max_tokens": 131072,
        "description": "128k+ 上下文窗口",
        "summary_max_chars": 1500,
        "search_k": 6,
        "chunk_size": 1200,
        "chunk_overlap": 200
    }
}

MODEL_WINDOW_MAP = {
    "qwen3:8b": "small",
    "qwen3:14b": "medium",
    "qwen3.5:0.8b": "small",
    "qwen3.5:4b": "medium",
    "qwen3.5:9b": "medium",
    "qwen3-vl:8b": "medium",
    "deepseek-r1:8b": "medium",
    "deepseek-r1:14b": "large",
    "llama3:8b": "small",
    "llama3:70b": "large",
    "mistral:7b": "small",
    "mixtral:8x7b": "large",
}


def get_model_context_config(model_name: str) -> Dict[str, Any]:
    base_name = model_name.split(":")[0] if ":" in model_name else model_name
    
    window_size = "medium"
    
    for model_key, size in MODEL_WINDOW_MAP.items():
        if model_key.lower() in model_name.lower() or base_name.lower() in model_key.lower():
            window_size = size
            break
    
    if any(x in model_name.lower() for x in ["70b", "72b", "128k", "large"]):
        window_size = "large"
    elif any(x in model_name.lower() for x in ["0.5b", "0.8b", "1b", "1.5b", "2b", "3b", "7b", "8b", "small"]):
        window_size = "small"
    
    return MODEL_CONTEXT_CONFIGS[window_size]


def get_search_k(model_name: str) -> int:
    config = get_model_context_config(model_name)
    return config["search_k"]


def get_chunk_config(model_name: str) -> Dict[str, int]:
    config = get_model_context_config(model_name)
    return {
        "chunk_size": config["chunk_size"],
        "chunk_overlap": config["chunk_overlap"]
    }


def get_summary_max_chars(model_name: str) -> int:
    config = get_model_context_config(model_name)
    return config["summary_max_chars"]
