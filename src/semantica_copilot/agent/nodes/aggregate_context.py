"""Aggregate Context 노드"""

import logging

from semantica_copilot.agent.state import AgentState

logger = logging.getLogger(__name__)


def aggregate_context_node(state: AgentState) -> AgentState:
    """
    Aggregate Context 노드

    역할:
    - 중복 제거는 이미 add_result에서 처리됨
    - 상위 k개만 유지 (메모리 효율)
    - 통계 로깅
    """
    logger.info("aggregate_context_node: Aggregating...")

    total_results = len(state.accumulated_context.results)
    unique_files = len({r.file_path for r in state.accumulated_context.results})

    logger.info(f"Total results: {total_results}, Unique files: {unique_files}")

    # 상위 k개만 유지 (메모리 효율)
    max_results = 50
    if total_results > max_results:
        logger.info(f"Keeping top {max_results} results (was {total_results})")
        top_results = state.accumulated_context.get_top_k(max_results)
        state.accumulated_context.results = top_results
        # dedupe_keys도 동기화
        state.accumulated_context.dedupe_keys = [
            f"{r.repo_id}:{r.file_path}:{r.line_start}" for r in top_results
        ]

    # 통계 정보 (디버깅용)
    if state.accumulated_context.results:
        top3 = state.accumulated_context.get_top_k(3)
        scores = [r.score for r in top3]
        logger.info(f"Top 3 scores: {scores}")

    return state
