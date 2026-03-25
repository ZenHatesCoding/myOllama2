from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from core.graph import GraphState
from agent.nodes import (
    node_classify_intent,
    node_retrieve_docs,
    node_retrieve_history,
    node_generate_response,
    node_match_skill,
    node_activate_skill
)


def route_by_mode(state: GraphState) -> str:
    mode = state.get("mode", "qa")
    
    if mode == "agent":
        target_skill = state.get("target_skill")
        if target_skill:
            return "activate_skill"
        return "match_skill"
    
    return "classify_intent"


def should_use_tool(state: GraphState) -> str:
    mode = state.get("mode", "qa")
    target_skill = state.get("target_skill")
    mcp_result = state.get("mcp_result")

    if target_skill:
        return "activate_skill"
    elif mcp_result and mcp_result.get("success"):
        return "generate_response"
    
    if mode == "qa":
        return "retrieve_docs"
    return "match_skill"


def should_use_skill(state: GraphState) -> str:
    mode = state.get("mode", "qa")
    target_skill = state.get("target_skill")
    skill_context = state.get("skill_context")

    if target_skill:
        return "activate_skill"
    if skill_context:
        return "generate_response"
    if mode == "agent":
        return "generate_response"
    return "retrieve_docs"


def should_use_skill_agent(state: GraphState) -> str:
    target_skill = state.get("target_skill")
    skill_context = state.get("skill_context")

    if target_skill:
        return "activate_skill"
    if skill_context:
        return "generate_response"
    return "generate_response"


def should_use_tool_qa(state: GraphState) -> str:
    mcp_result = state.get("mcp_result")
    if mcp_result and mcp_result.get("success"):
        return "generate_response"
    return "retrieve_docs"


_qa_graph = None
_agent_graph = None


def build_qa_graph():
    global _qa_graph
    if _qa_graph is None:
        graph = StateGraph(GraphState)

        graph.add_node("classify_intent", node_classify_intent)
        graph.add_node("retrieve_docs", node_retrieve_docs)
        graph.add_node("retrieve_history", node_retrieve_history)
        graph.add_node("generate_response", node_generate_response)

        graph.set_entry_point("classify_intent")

        graph.add_conditional_edges(
            "classify_intent",
            should_use_tool_qa,
            {
                "generate_response": "generate_response",
                "retrieve_docs": "retrieve_docs"
            }
        )

        graph.add_edge("retrieve_docs", "retrieve_history")
        graph.add_edge("retrieve_history", "generate_response")
        graph.add_edge("generate_response", END)

        _qa_graph = graph.compile(checkpointer=MemorySaver())
    return _qa_graph


def build_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        graph = StateGraph(GraphState)

        graph.add_node("match_skill", node_match_skill)
        graph.add_node("activate_skill", node_activate_skill)
        graph.add_node("generate_response", node_generate_response)

        graph.set_entry_point("match_skill")

        graph.add_conditional_edges(
            "match_skill",
            should_use_skill_agent,
            {
                "activate_skill": "activate_skill",
                "generate_response": "generate_response"
            }
        )

        graph.add_edge("activate_skill", "generate_response")
        graph.add_edge("generate_response", END)

        _agent_graph = graph.compile(checkpointer=MemorySaver())
    return _agent_graph


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("route_by_mode", lambda state: state)
    graph.add_node("classify_intent", node_classify_intent)
    graph.add_node("match_skill", node_match_skill)
    graph.add_node("activate_skill", node_activate_skill)
    graph.add_node("retrieve_docs", node_retrieve_docs)
    graph.add_node("retrieve_history", node_retrieve_history)
    graph.add_node("generate_response", node_generate_response)

    graph.set_entry_point("route_by_mode")

    graph.add_conditional_edges(
        "route_by_mode",
        route_by_mode,
        {
            "qa": "classify_intent",
            "agent": "match_skill"
        }
    )

    graph.add_conditional_edges(
        "classify_intent",
        should_use_tool,
        {
            "activate_skill": "activate_skill",
            "generate_response": "generate_response",
            "match_skill": "match_skill"
        }
    )

    graph.add_conditional_edges(
        "match_skill",
        should_use_skill,
        {
            "activate_skill": "activate_skill",
            "generate_response": "generate_response"
        }
    )

    graph.add_edge("activate_skill", "generate_response")
    graph.add_edge("retrieve_docs", "retrieve_history")
    graph.add_edge("retrieve_history", "generate_response")
    graph.add_edge("generate_response", END)
    
    return graph.compile(checkpointer=MemorySaver())


graph_executor = None


def get_graph_executor():
    global graph_executor
    if graph_executor is None:
        graph_executor = build_graph()
    return graph_executor
