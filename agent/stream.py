from typing import List
from graph import GraphState, create_initial_state
from agent.graph import build_qa_graph, build_agent_graph
from extensions import state as app_state


def run_graph(query: str, model_name: str = "qwen3.5:4b", images: List[dict] = None, mode: str = "qa") -> str:
    initial_state = create_initial_state(query, model_name, images, mode)
    
    if mode == "qa":
        executor = build_qa_graph()
    else:
        executor = build_agent_graph()
    
    result = executor.invoke(initial_state, config={"configurable": {"thread_id": "default"}})
    
    return result.get("output_content", "")


def stream_graph(query: str, model_name: str = "qwen3.5:4b", images: List[dict] = None, mode: str = "qa"):
    initial_state = create_initial_state(query, model_name, images, mode)
    
    if mode == "qa":
        executor = build_qa_graph()
    else:
        executor = build_agent_graph()
    
    mcp_result = None
    
    for event in executor.stream(initial_state, config={"configurable": {"thread_id": "default"}}):
        if app_state.should_stop:
            yield "操作已中断"
            return
        
        for node_name, node_output in event.items():
            if node_name == "classify_intent":
                mcp_result = node_output.get("mcp_result")
                if mcp_result and mcp_result.get("success"):
                    tool_name = mcp_result.get("tool_name", "")
                    tool_display_names = {
                        "get_headlines": "头条新闻",
                        "get_news_by_type": "分类新闻",
                        "search_news": "新闻搜索",
                        "get_document_summary": "文档摘要",
                        "get_document_outline": "文档大纲"
                    }
                    tool_display_name = tool_display_names.get(tool_name, tool_name)
                    yield f"📰 正在从{tool_display_name}获取信息...\n\n"
            
            elif node_name == "generate_response":
                output = node_output.get("output_content", "")
                yield output
