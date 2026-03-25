import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config.json")

DEFAULT_CONFIG = {
    "llm_provider": "ollama",
    "ollama_base_url": "http://localhost:11434",
    "max_context_turns": 5,
    "speech_recognition_lang": "zh-CN",
    "speech_synthesis_lang": "zh-CN",
    "max_recording_time": 30,
    "openai_endpoints": [],
    "openai_current_endpoint": "",
    "openai_current_model": "",
    "anthropic_endpoints": [],
    "anthropic_current_endpoint": "",
    "anthropic_current_model": ""
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
        config = _migrate_old_anthropic_config(config)
        config = _migrate_old_openai_config(config)
        return config
    except Exception:
        return DEFAULT_CONFIG.copy()


def _migrate_old_anthropic_config(config):
    if "anthropic_api_key" in config and config.get("anthropic_api_key"):
        has_endpoints = config.get("anthropic_endpoints") and len(config.get("anthropic_endpoints", [])) > 0
        if not has_endpoints:
            endpoint = {
                "name": "默认端点",
                "base_url": config.get("anthropic_base_url", ""),
                "api_key": config.get("anthropic_api_key", ""),
                "models": [config.get("anthropic_model", "")] if config.get("anthropic_model") else [],
                "is_default": True
            }
            if endpoint["base_url"] or endpoint["api_key"]:
                config["anthropic_endpoints"] = [endpoint]
                config["anthropic_current_endpoint"] = "默认端点"
                if endpoint["models"]:
                    config["anthropic_current_model"] = endpoint["models"][0]
        for key in ["anthropic_api_key", "anthropic_base_url", "anthropic_model"]:
            if key in config:
                del config[key]
    return config


def _migrate_old_openai_config(config):
    if "openai_api_key" in config and config.get("openai_api_key"):
        has_endpoints = config.get("openai_endpoints") and len(config.get("openai_endpoints", [])) > 0
        if not has_endpoints:
            endpoint = {
                "name": "默认端点",
                "base_url": config.get("openai_base_url", ""),
                "api_key": config.get("openai_api_key", ""),
                "models": [config.get("openai_model", "")] if config.get("openai_model") else [],
                "is_default": True
            }
            if endpoint["base_url"] or endpoint["api_key"]:
                config["openai_endpoints"] = [endpoint]
                config["openai_current_endpoint"] = "默认端点"
                if endpoint["models"]:
                    config["openai_current_model"] = endpoint["models"][0]
        for key in ["openai_api_key", "openai_base_url", "openai_model"]:
            if key in config:
                del config[key]
    return config


def save_config(config):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存配置失败: {e}")
        return False
