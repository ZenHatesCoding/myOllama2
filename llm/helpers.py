from langchain_ollama import OllamaEmbeddings


def get_embedding_model(base_url: str):
    return OllamaEmbeddings(
        model="nomic-embed-text",
        base_url=base_url
    )


def get_llm_model(temperature=0.7):
    from core import state
    from llm.factory import create_llm
    
    provider = state.llm_provider
    
    if provider == "ollama":
        return create_llm(
            provider="ollama",
            model="qwen3.5:4b",
            base_url=state.ollama_base_url,
            temperature=temperature
        )
    elif provider == "openai":
        return create_llm(
            provider="openai",
            model=state.openai_current_model if hasattr(state, 'openai_current_model') and state.openai_current_model else model_name,
            base_url=state.get_openai_base_url() if hasattr(state, 'get_openai_base_url') else None,
            api_key=state.get_openai_api_key() if hasattr(state, 'get_openai_api_key') else None,
            temperature=temperature
        )
    elif provider == "anthropic":
        return create_llm(
            provider="anthropic",
            model=state.anthropic_current_model if hasattr(state, 'anthropic_current_model') and state.anthropic_current_model else "claude-3-sonnet-20240229",
            base_url=state.get_anthropic_base_url() if hasattr(state, 'get_anthropic_base_url') else None,
            api_key=state.get_anthropic_api_key() if hasattr(state, 'get_anthropic_api_key') else None,
            temperature=temperature
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")


def generate_summary(messages):
    try:
        prompt = """请仔细阅读以下对话记录，然后生成一个简洁的摘要。

【对话记录】
"""
        for msg in messages:
            prompt += f"{msg.role}: {msg.content}\n"

        prompt += """
【要求】
1. 一句话概括对话核心主题
2. 如果有文档问答，记录文档主题
3. 记录用户的主要意图

【摘要格式】
主题：[核心主题]
文档：[文档名称或无]
意图：[用户主要目的]

请生成摘要："""
        
        llm = get_llm_model(temperature=0.3)
        response = llm.invoke(prompt)
        
        content = response.content
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text':
                    text_parts.append(part.get('text', ''))
                elif isinstance(part, str):
                    text_parts.append(part)
            content = ''.join(text_parts)
        
        return content.strip()
    except Exception as e:
        print(f"生成摘要失败：{str(e)}")
        return None
