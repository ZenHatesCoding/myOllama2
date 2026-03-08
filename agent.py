import json
from typing import Optional, Dict, Any, List
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool

from graph import GraphState, create_initial_state
from tools import get_all_tools, news_toolkit
from document_tools import document_tools, get_document_summary, search_document, get_document_outline
from extensions import state
from llm_factory import create_llm


def detect_tool_intent(llm, query: str, tools_schema: str) -> Optional[Dict[str, Any]]:
    system_prompt = f"""你是一个智能助手，负责判断用户是否需要使用工具来完成任务。

{tools_schema}

请分析用户的输入，判断是否需要使用上述工具。
如果需要使用工具，请返回JSON格式：
{{
    "need_tool": true,
    "tool_name": "工具名称",
    "parameters": {{
        "参数名": "参数值"
    }}
}}

如果不需要使用工具，请返回：
{{
    "need_tool": false,
    "reason": "原因说明"
}}

只返回JSON，不要有其他内容。"""

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ])
        
        result_text = response.content.strip()
        result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        try:
            result = json.loads(result_text)
            return result
        except json.JSONDecodeError:
            return None
    except Exception as e:
        print(f"检测工具意图失败: {str(e)}")
        return None


def build_tools_schema() -> str:
    tools = get_all_tools() + document_tools
    schema = "可用工具列表：\n\n"
    for tool in tools:
        schema += f"工具名称: {tool.name}\n"
        schema += f"描述: {tool.description}\n"
        if tool.args_schema:
            schema += "参数:\n"
            properties = tool.args_schema.schema().get("properties", {})
            required = tool.args_schema.schema().get("required", [])
            for param_name, param_info in properties.items():
                req = " (必需)" if param_name in required else " (可选)"
                desc = param_info.get("description", "")
                schema += f"  - {param_name}: {param_info.get('type', 'any')}{req} - {desc}\n"
        schema += "\n"
    return schema


def node_detect_tool(state: GraphState) -> dict:
    from graph import decide_disclosure_level, DISCLOSURE_LEVELS
    
    if state.get("should_stop"):
        return {}
    
    query = state.get("query", "")
    if not query:
        return {"mcp_result": None}
    
    disclosure_level = decide_disclosure_level(query)
    level_config = DISCLOSURE_LEVELS.get(disclosure_level, DISCLOSURE_LEVELS["relevant"])
    
    model_name = state.get("model_name", "qwen3.5:9b")
    provider = state.llm_provider if hasattr(state, 'llm_provider') else 'ollama'
    
    if provider == "ollama":
        llm = ChatOllama(
            model=model_name,
            base_url=state.ollama_base_url if hasattr(state, 'ollama_base_url') else "http://localhost:11434",
            temperature=0.3
        )
    elif provider == "openai":
        llm = create_llm(
            provider="openai",
            model=state.openai_model if hasattr(state, 'openai_model') else model_name,
            base_url=state.openai_base_url if hasattr(state, 'openai_base_url') else None,
            api_key=state.openai_api_key if hasattr(state, 'openai_api_key') else None,
            temperature=0.3
        )
    elif provider == "anthropic":
        llm = create_llm(
            provider="anthropic",
            model=state.anthropic_model if hasattr(state, 'anthropic_model') else model_name,
            api_key=state.anthropic_api_key if hasattr(state, 'anthropic_api_key') else None,
            temperature=0.3
        )
    else:
        llm = ChatOllama(
            model=model_name,
            base_url="http://localhost:11434",
            temperature=0.3
        )
    
    tools_schema = build_tools_schema()
    intent = detect_tool_intent(llm, query, tools_schema)
    
    if intent and intent.get("need_tool"):
        tool_name = intent.get("tool_name")
        parameters = intent.get("parameters", {})
        
        result = None
        if tool_name == "get_headlines":
            result = news_toolkit.get_headlines(parameters.get("page_size", 10))
        elif tool_name == "get_news_by_type":
            result = news_toolkit.get_news_by_type(
                parameters.get("news_type", "头条"),
                parameters.get("page_size", 10)
            )
        elif tool_name == "search_news":
            result = news_toolkit.search_news(
                parameters.get("keyword", ""),
                parameters.get("page_size", 10)
            )
        elif tool_name == "get_document_summary":
            n_chunks = level_config.get("n_chunks", 30)
            result = {"success": True, "tool_name": tool_name, "formatted_text": get_document_summary.invoke({"n_chunks": n_chunks})}
        elif tool_name == "search_document":
            k = level_config.get("k", 8)
            result = {"success": True, "tool_name": tool_name, "formatted_text": search_document.invoke({
                "query": parameters.get("query", query),
                "k": k
            })}
        elif tool_name == "get_document_outline":
            result = {"success": True, "tool_name": tool_name, "formatted_text": get_document_outline.invoke({})}
        
        if result and result.get("success"):
            result["disclosure_level"] = disclosure_level
            return {"mcp_result": result, "disclosure_level": disclosure_level}
    
    return {"mcp_result": None, "disclosure_level": disclosure_level}


def node_retrieve_document(state: GraphState) -> dict:
    from graph import DISCLOSURE_LEVELS
    
    if state.get("should_stop"):
        return {}
    
    disclosure_level = state.get("disclosure_level", "relevant")
    level_config = DISCLOSURE_LEVELS.get(disclosure_level, DISCLOSURE_LEVELS["relevant"])
    
    conversation = state.get_current_conversation() if hasattr(state, 'get_current_conversation') else None
    
    if not conversation:
        from extensions import state as app_state
        conversation = app_state.get_current_conversation()
    
    if conversation and conversation.vector_store:
        query = state.get("query", "")
        k = level_config.get("k", 8)
        relevant_docs = conversation.vector_store.similarity_search(query, k=k)
        context = "\n\n".join([doc.page_content for doc in relevant_docs]) if relevant_docs else "无相关内容"
        return {
            "has_document": True,
            "document_context": context,
            "disclosure_level": disclosure_level
        }
    
    return {
        "has_document": False,
        "document_context": "",
        "disclosure_level": disclosure_level
    }


def node_generate(state: GraphState) -> dict:
    if state.get("should_stop"):
        return {"output_content": "操作已中断"}
    
    mcp_result = state.get("mcp_result")
    model_name = state.get("model_name", "qwen3.5:9b")
    query = state.get("query", "")
    images = state.get("images", [])
    has_document = state.get("has_document", False)
    document_context = state.get("document_context", "")
    
    news_tools = ["get_headlines", "get_news_by_type", "search_news"]
    document_tools_list = ["get_document_summary", "search_document", "get_document_outline"]
    
    if mcp_result and mcp_result.get("success"):
        tool_name = mcp_result.get("tool_name", "")
        formatted_text = mcp_result.get("formatted_text", "")
        
        if tool_name in news_tools:
            tool_display_names = {
                "get_headlines": "头条新闻",
                "get_news_by_type": "分类新闻",
                "search_news": "新闻搜索"
            }
            tool_display_name = tool_display_names.get(tool_name, tool_name)
            full_text = f"📰 正在从{tool_display_name}获取信息...\n\n{formatted_text}"
            return {"output_content": full_text}
        
        if tool_name in document_tools_list:
            document_context = formatted_text
            has_document = True
    
    from extensions import state as app_state
    provider = app_state.llm_provider if hasattr(app_state, 'llm_provider') else 'ollama'
    
    if provider == "ollama":
        llm = ChatOllama(
            model=model_name,
            base_url=app_state.ollama_base_url if hasattr(app_state, 'ollama_base_url') else "http://localhost:11434",
            temperature=0.7,
            num_ctx=32000,
            num_predict=8000
        )
    elif provider == "openai":
        llm = create_llm(
            provider="openai",
            model=app_state.openai_model if hasattr(app_state, 'openai_model') else model_name,
            base_url=app_state.openai_base_url if hasattr(app_state, 'openai_base_url') else None,
            api_key=app_state.openai_api_key if hasattr(app_state, 'openai_api_key') else None,
            temperature=0.7
        )
    elif provider == "anthropic":
        llm = create_llm(
            provider="anthropic",
            model=app_state.anthropic_model if hasattr(app_state, 'anthropic_model') else model_name,
            api_key=app_state.anthropic_api_key if hasattr(app_state, 'anthropic_api_key') else None,
            temperature=0.7
        )
    else:
        llm = ChatOllama(
            model=model_name,
            base_url="http://localhost:11434",
            temperature=0.7,
            num_ctx=32000,
            num_predict=8000
        )
    
    conversation = app_state.get_current_conversation()
    
    if has_document and document_context:
        system_prompt = f"""你是一个专业的文档助手。
你的任务是根据下面提供的文档内容，回答用户的问题。

【用户问题】
{query}

【文档内容】
{document_context}

【回答要求】
1. 直接基于文档内容回答，不要复述上述指令
2. 用户用什么语言提问，你就用什么语言回答
3. 如果文档中没有相关信息，请如实说明
4. 回答要简洁、有条理

请开始回答："""
    else:
        system_prompt = """你是一个专业、友好的AI助手。
请根据对话历史和上下文回答用户的问题。
用户用什么语言提问，你就用什么语言回答。
保持简洁、有条理。"""
    
    from utils import prepare_messages
    messages = prepare_messages(conversation, query, system_prompt, images if images else None)
    
    output_content = ""
    for chunk in llm.stream(messages):
        if app_state.should_stop:
            output_content += "\n\n操作已中断"
            break
        chunk_text = str(chunk.content)
        output_content += chunk_text
    
    return {"output_content": output_content}


def should_use_tool(state: GraphState) -> str:
    mcp_result = state.get("mcp_result")
    if mcp_result and mcp_result.get("success"):
        return "generate"
    return "retrieve_document"


def build_graph():
    graph = StateGraph(GraphState)
    
    graph.add_node("detect_tool", node_detect_tool)
    graph.add_node("retrieve_document", node_retrieve_document)
    graph.add_node("generate", node_generate)
    
    graph.set_entry_point("detect_tool")
    
    graph.add_conditional_edges(
        "detect_tool",
        should_use_tool,
        {
            "generate": "generate",
            "retrieve_document": "retrieve_document"
        }
    )
    
    graph.add_edge("retrieve_document", "generate")
    graph.add_edge("generate", END)
    
    return graph.compile(checkpointer=MemorySaver())


graph_executor = None


def get_graph_executor():
    global graph_executor
    if graph_executor is None:
        graph_executor = build_graph()
    return graph_executor


def run_graph(query: str, model_name: str = "qwen3.5:4b", images: List[dict] = None) -> str:
    initial_state = create_initial_state(query, model_name, images)
    executor = get_graph_executor()
    
    result = executor.invoke(initial_state, config={"configurable": {"thread_id": "default"}})
    
    return result.get("output_content", "")


def stream_graph(query: str, model_name: str = "qwen3.5:4b", images: List[dict] = None):
    from extensions import state as app_state
    
    initial_state = create_initial_state(query, model_name, images)
    executor = get_graph_executor()
    
    mcp_result = None
    
    for event in executor.stream(initial_state, config={"configurable": {"thread_id": "default"}}):
        if app_state.should_stop:
            yield "操作已中断"
            return
        
        for node_name, node_output in event.items():
            if node_name == "detect_tool":
                mcp_result = node_output.get("mcp_result")
                if mcp_result and mcp_result.get("success"):
                    tool_name = mcp_result.get("tool_name", "")
                    tool_display_names = {
                        "get_headlines": "头条新闻",
                        "get_news_by_type": "分类新闻",
                        "search_news": "新闻搜索",
                        "get_document_summary": "文档摘要",
                        "search_document": "文档搜索",
                        "get_document_outline": "文档大纲"
                    }
                    tool_display_name = tool_display_names.get(tool_name, tool_name)
                    yield f"📰 正在从{tool_display_name}获取信息...\n\n"
            
            elif node_name == "generate":
                output = node_output.get("output_content", "")
                yield output
