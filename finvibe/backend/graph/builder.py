"""
LangGraph Builder — constructs and compiles the FinVibe agent graph.

Day 2 graph (5 nodes + conditional routing):
  START → Researcher → Vibe Analyst → Strategist
    → [if trades]   → Executor → Reflector → END
    → [if alert]    → Alerter → END
    → [otherwise]   → END
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.mongodb import MongoDBSaver

from backend.schemas.agent_state import AgentState
from backend.graph.nodes.researcher import researcher_node
from backend.graph.nodes.vibe_analyst import vibe_analyst_node
from backend.graph.nodes.strategist import strategist_node
from backend.graph.nodes.executor import executor_node
from backend.graph.nodes.reflector import reflector_node
from backend.graph.nodes.alerter import alerter_node
from backend.graph.edges import route_after_strategy
from backend.config import settings


def build_graph() -> StateGraph:
    """
    Build the FinVibe agent graph (does NOT compile it — caller chooses checkpointer).
    """
    graph_builder = StateGraph(AgentState)

    # ── Register all nodes ──
    graph_builder.add_node("researcher", researcher_node)
    graph_builder.add_node("vibe_analyst", vibe_analyst_node)
    graph_builder.add_node("strategist", strategist_node)
    graph_builder.add_node("executor", executor_node)
    graph_builder.add_node("reflector", reflector_node)
    graph_builder.add_node("alerter", alerter_node)

    # ── Linear edges: START → Researcher → Vibe Analyst → Strategist ──
    graph_builder.add_edge(START, "researcher")
    graph_builder.add_edge("researcher", "vibe_analyst")
    graph_builder.add_edge("vibe_analyst", "strategist")

    # ── Conditional edge after Strategist ──
    graph_builder.add_conditional_edges(
        "strategist",
        route_after_strategy,
        {
            "executor": "executor",
            "alerter": "alerter",
            "__end__": END,
        },
    )

    # ── After Executor → Reflector → END ──
    graph_builder.add_edge("executor", "reflector")
    graph_builder.add_edge("reflector", END)

    # ── After Alerter → END ──
    graph_builder.add_edge("alerter", END)

    return graph_builder


def compile_graph_with_checkpointer():
    """
    Compile the graph with MongoDB checkpointing.
    Returns: (compiled_graph, checkpointer) — caller manages checkpointer lifecycle.
    """
    graph_builder = build_graph()
    checkpointer = MongoDBSaver.from_conn_string(settings.mongo_uri)
    compiled = graph_builder.compile(checkpointer=checkpointer)
    return compiled, checkpointer


def compile_graph_simple():
    """
    Compile without checkpointing — useful for quick one-shot runs and testing.
    """
    graph_builder = build_graph()
    return graph_builder.compile()
