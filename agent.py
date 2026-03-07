import json
from typing import Optional, Dict, Any, List
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool

from graph import GraphState, create_initial_state
from tools import get_all_tools, news_toolkit
from document_tools import document_tools, get_document_summary, search_document, expand_context, get_document_outline
from models import state


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
    if state.get("should_stop"):
        return {}
    
    query = state.get("query", "")
    if not query:
        return {"mcp_result": None}
    
    llm = ChatOllama(
        model="qwen3.5:4b",
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
            result = {"success": True, "tool_name": tool_name, "formatted_text": get_document_summary.invoke({})}
        elif tool_name == "search_document":
            result = {"success": True, "tool_name": tool_name, "formatted_text": search_document.invoke({
                "query": parameters.get("query", query),
                "k": parameters.get("k", 4)
            })}
        elif tool_name == "expand_context":
            result = {"success": True, "tool_name": tool_name, "formatted_text": expand_context.invoke({
                "chunk_id": parameters.get("chunk_id", 0),
                "direction": parameters.get("direction", "both")
            })}
        elif tool_name == "get_document_outline":
            result = {"success": True, "tool_name": tool_name, "formatted_text": get_document_outline.invoke({})}
        
        if result and result.get("success"):
            return {"mcp_result": result}
    
    return {"mcp_result": None}


def node_retrieve_document(state: GraphState) -> dict:
    if state.get("should_stop"):
        return {}
    
    conversation = state.get_current_conversation() if hasattr(state, 'get_current_conversation') else None
    
    if not conversation:
        from models import state as app_state
        conversation = app_state.get_current_conversation()
    
    if conversation and conversation.vector_store:
        query = state.get("query", "")
        relevant_docs = conversation.vector_store.similarity_search(query, k=4)
        context = "\n\n".join([doc.page_content for doc in relevant_docs]) if relevant_docs else "无相关内容"
        return {
            "has_document": True,
            "document_context": context
        }
    
    return {
        "has_document": False,
        "document_context": ""
    }


def node_generate(state: GraphState) -> dict:
    if state.get("should_stop"):
        return {"output_content": "操作已中断"}
    
    mcp_result = state.get("mcp_result")
    
    if mcp_result and mcp_result.get("success"):
        tool_name = mcp_result.get("tool_name", "")
        formatted_text = mcp_result.get("formatted_text", "")
        
        tool_display_names = {
            "get_headlines": "头条新闻",
            "get_news_by_type": "分类新闻",
            "search_news": "新闻搜索"
        }
        tool_display_name = tool_display_names.get(tool_name, tool_name)
        
        full_text = f"📰 正在从{tool_display_name}获取信息...\n\n{formatted_text}"
        return {"output_content": full_text}
    
    model_name = state.get("model_name", "qwen3.5:4b")
    query = state.get("query", "")
    images = state.get("images", [])
    has_document = state.get("has_document", False)
    document_context = state.get("document_context", "")
    
    llm = ChatOllama(
        model=model_name,
        base_url="http://localhost:11434",
        temperature=0.7
    )
    
    from models import state as app_state
    conversation = app_state.get_current_conversation()
    
    if has_document and document_context:
        system_prompt = f"你是一个文档问答助手。仅基于以下内容回答问题：\n\n{document_context}"
    else:
        system_prompt = "你是一个乐于助人的助手"
    
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
    from models import state as app_state
    
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
                        "expand_context": "扩展上下文",
                        "get_document_outline": "文档大纲"
                    }
                    tool_display_name = tool_display_names.get(tool_name, tool_name)
                    yield f"📰 正在从{tool_display_name}获取信息...\n\n"
            
            elif node_name == "generate":
                output = node_output.get("output_content", "")
                if mcp_result and mcp_result.get("success"):
                    formatted_text = mcp_result.get("formatted_text", "")
                    for i in range(0, len(formatted_text), 10):
                        if app_state.should_stop:
                            yield "\n\n操作已中断"
                            return
                        yield formatted_text[i:i+10]
                else:
                    yield output
