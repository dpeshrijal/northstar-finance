from langgraph.graph import StateGraph, END

from .config import settings
from .models import AgentState
from .nodes import (
    router_node,
    discovery_node,
    policy_rag_node,
    sql_generator_node,
    synthesis_node,
    failure_node,
)


def should_retry(state: AgentState) -> str:
    if state["sql_error"] and state["iteration"] < settings.max_sql_retries:
        return "sql_gen"
    if state["sql_error"]:
        return "failure"
    return "synthesis"


def build_graph():
    builder = StateGraph(AgentState)
    builder.add_node("router", router_node)
    builder.add_node("discovery", discovery_node)
    builder.add_node("policy_rag", policy_rag_node)
    builder.add_node("sql_gen", sql_generator_node)
    builder.add_node("synthesis", synthesis_node)
    builder.add_node("failure", failure_node)

    builder.set_entry_point("router")
    builder.add_edge("router", "policy_rag")
    builder.add_edge("policy_rag", "discovery")
    builder.add_edge("discovery", "sql_gen")
    builder.add_conditional_edges("sql_gen", should_retry)
    builder.add_edge("synthesis", END)
    builder.add_edge("failure", END)
    return builder.compile()


app_graph = build_graph()
