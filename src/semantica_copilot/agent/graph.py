"""LangGraph 그래프 구성"""

import logging

from langgraph.graph import END, StateGraph

from semantica_copilot.agent.nodes import (
    aggregate_context_node,
    generate_answer_node,
    intent_plan_node,
    run_search_node,
    search_plan_node,
)
from semantica_copilot.agent.routing import route_enough_context
from semantica_copilot.agent.state import AgentState

logger = logging.getLogger(__name__)


def build_agent_graph():
    """
    Phase 2: Search Loop 에이전트 그래프

    플로우:
    intent_plan → search_plan ←───┐
                     ↓             │
                 run_search        │
                     ↓             │
                 aggregate         │
                     ↓             │
              check_enough ────────┘
                     ↓
                 generate → END

    - 조건부 루프 (max_search_steps까지)
    - routing 함수로 종료 판단
    """
    logger.info("Building agent graph (Phase 2)...")

    graph = StateGraph(AgentState)

    # 노드 추가 (async 노드는 자동 처리)
    graph.add_node("intent_plan", intent_plan_node)  # async (LLM 사용 시)
    graph.add_node("search_plan", search_plan_node)
    graph.add_node("run_search", run_search_node)  # async
    graph.add_node("aggregate", aggregate_context_node)
    graph.add_node("generate", generate_answer_node)  # async (LLM 사용 시)

    # 순차 플로우
    graph.set_entry_point("intent_plan")
    graph.add_edge("intent_plan", "search_plan")
    graph.add_edge("search_plan", "run_search")
    graph.add_edge("run_search", "aggregate")

    # 조건부 루프 (aggregate 후 판단)
    graph.add_conditional_edges(
        "aggregate",
        route_enough_context,
        {
            "continue": "search_plan",  # 더 검색
            "finish": "generate",  # 답변 생성
        },
    )

    graph.add_edge("generate", END)

    logger.info("Graph built successfully (with loop)")

    return graph.compile()


# 전역 그래프 인스턴스 (lazy initialization)
_graph = None


def get_graph():
    """그래프 싱글톤"""
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph
