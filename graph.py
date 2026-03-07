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
        "document_context": ""
    }
