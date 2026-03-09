from typing import TypedDict, Annotated, List, Optional, Any
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage


class GraphState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    query: str
    images: List[dict]
    model_name: str
    retrieved_docs: List[str]
    mcp_result: Optional[dict]
    output_content: str
    should_stop: bool
    conversation_id: str
    has_document: bool
    document_context: str
    disclosure_level: str
    history_context: str


DISCLOSURE_LEVELS = {
    "summary": {"n_chunks": 30, "description": "摘要"},
    "relevant": {"k": 8, "description": "相关片段"},
    "full": {"n_chunks": 100, "description": "完整内容"}
}


def decide_disclosure_level(query: str) -> str:
    query_lower = query.lower()
    
    if any(kw in query_lower for kw in ["总结", "概括", "概述", "摘要", "main idea", "summary", "abstract"]):
        return "summary"
    elif any(kw in query_lower for kw in ["详细", "完整", "全部", "具体", "full", "complete", "entire"]):
        return "full"
    else:
        return "relevant"


def create_initial_state(query: str, model_name: str = "qwen3.5:4b", images: List[dict] = None) -> dict:
    return {
        "messages": [],
        "query": query,
        "images": images or [],
        "model_name": model_name,
        "retrieved_docs": [],
        "mcp_result": None,
        "output_content": "",
        "should_stop": False,
        "conversation_id": "",
        "has_document": False,
        "document_context": "",
        "disclosure_level": "relevant"
    }
