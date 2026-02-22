"""
Conditional edge functions for the LangGraph.
These decide WHERE the graph goes next based on the current state.
"""
from backend.schemas.agent_state import AgentState


def route_after_strategy(state: AgentState) -> str:
    """
    After the Strategist node, decide next step:
    - If there are trades to execute → go to executor
    - If just an alert needed (no trades) → go to alerter
    - Otherwise → end
    """
    trade_decisions = state.get("trade_decisions", [])
    should_alert = state.get("should_alert", False)

    if trade_decisions:
        return "executor"
    elif should_alert:
        return "alerter"
    else:
        return "__end__"
