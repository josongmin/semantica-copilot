"""Routing 함수"""

import logging

from semantica_copilot.agent.state import AgentState

logger = logging.getLogger(__name__)


def check_enough_context_heuristic(state: AgentState) -> bool:
    """
    휴리스틱 기반 종료 조건

    Phase 2: 단순 휴리스틱
    - 최대 스텝 도달
    - 충분한 결과 수
    - 최상위 점수가 높음

    Phase 3에서 LLM 기반으로 개선 예정
    """
    # 1. 최대 스텝 도달
    if state.search_steps >= state.max_search_steps:
        logger.info(f"Max steps reached: {state.search_steps}/{state.max_search_steps}")
        return True

    # 2. 충분한 결과 수
    if len(state.accumulated_context.results) >= 30:
        logger.info(f"Enough results: {len(state.accumulated_context.results)}")
        return True

    # 3. 최상위 결과 점수 (안전하게 get_top_k 사용)
    top_results = state.accumulated_context.get_top_k(1)
    if top_results and top_results[0].score > 0.9:
        logger.info(f"High score found: {top_results[0].score}")
        return True

    logger.info(
        f"Continue search: steps={state.search_steps}, "
        f"results={len(state.accumulated_context.results)}"
    )
    return False


def route_enough_context(state: AgentState) -> str:
    """
    종료 조건 라우팅

    Returns:
        "continue": 더 검색 (search_plan으로)
        "finish": 답변 생성 (generate_answer로)
    """
    logger.info("route_enough_context: Checking...")

    # 1. 에러 발생 시 종료
    if state.error:
        logger.error(f"Error detected, finishing: {state.error}")
        return "finish"

    # 2. 결과 없으면 종료 (첫 검색 실패)
    if state.search_steps > 0 and not state.accumulated_context.results:
        logger.warning("No results after search, finishing")
        return "finish"

    # 3. 휴리스틱 체크
    if check_enough_context_heuristic(state):
        logger.info("Enough context, finishing")
        return "finish"

    # 4. 계속 검색
    logger.info("Not enough, continuing")
    return "continue"
