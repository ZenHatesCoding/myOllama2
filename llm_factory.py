from typing import Optional
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


class LLMProvider:
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


def create_llm(
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    **kwargs
):
    if provider == LLMProvider.OLLAMA:
        return ChatOllama(
            model=model,
            base_url=base_url or DEFAULT_OLLAMA_BASE_URL,
            temperature=temperature,
            **kwargs
        )
    elif provider == LLMProvider.OPENAI:
        return ChatOpenAI(
            model=model,
            base_url=base_url or DEFAULT_OPENAI_BASE_URL,
            api_key=api_key,
            temperature=temperature,
            **kwargs
        )
    elif provider == LLMProvider.ANTHROPIC:
        return ChatAnthropic(
            model=model,
            anthropic_api_key=api_key,
            temperature=temperature,
            **kwargs
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")
