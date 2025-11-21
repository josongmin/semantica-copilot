"""LangGraph 그래프 구성"""

import logging

from langgraph.graph import END, StateGraph

from semantica_copilot.agent.nodes import (
    answer_generator_node,
    intent_router_node,
    plan_executor_node,
)
from semantica_copilot.agent.state import AgentState

logger = logging.getLogger(__name__)


def build_agent_graph():
    """
    Intent-based Router Architecture

    플로우:
    intent_router → plan_executor → answer_generator → END

    - 순차적 실행 (loop 없음)
    - intent_router: 질의 분석 → ExecutionPlan 생성
    - plan_executor: ExecutionPlan 순차 실행 → 결과 누적
    - answer_generator: 결과 기반 답변 생성
    """
    logger.info("Building agent graph (Intent-based Router)...")

    graph = StateGraph(AgentState)

    # 노드 추가 (모두 async)
    graph.add_node("intent_router", intent_router_node)
    graph.add_node("plan_executor", plan_executor_node)
    graph.add_node("answer_generator", answer_generator_node)

    # 순차 플로우 (loop 없음)
    graph.set_entry_point("intent_router")
    graph.add_edge("intent_router", "plan_executor")
    graph.add_edge("plan_executor", "answer_generator")
    graph.add_edge("answer_generator", END)

    logger.info("Graph built successfully (sequential pipeline)")

    return graph.compile()


# 전역 그래프 인스턴스 (lazy initialization)
_graph = None


def get_graph():
    """그래프 싱글톤"""
    global _graph
    if _graph is None:
        _graph = build_agent_graph()
    return _graph
