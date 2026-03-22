import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULT_CONFIG = {
    "llm_provider": "ollama",
    "ollama_base_url": "http://localhost:11434",
    "max_context_turns": 5,
    "speech_recognition_lang": "zh-CN",
    "speech_synthesis_lang": "zh-CN",
    "max_recording_time": 30,
    "openai_api_key": "",
    "openai_base_url": "",
    "openai_model": "",
    "anthropic_api_key": "",
    "anthropic_base_url": "",
    "anthropic_model": ""
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        for key in DEFAULT_CONFIG:
            if key not in config:
                config[key] = DEFAULT_CONFIG[key]
        return config
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False
