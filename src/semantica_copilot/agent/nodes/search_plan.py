"""Search Plan 노드 (Phase 2: 패턴 기반)"""

import logging

from semantica_copilot.agent.state import AgentState, CodeSearchIntent, SearchStrategy

logger = logging.getLogger(__name__)


def search_plan_node(state: AgentState) -> AgentState:
    """
    Search Plan 노드

    Phase 2: 단계별 고정 패턴
    - Step 0: 심볼/파일 찾기 (hybrid)
    - Step 1: 호출 관계 확장 (graph)
    - Step 2+: 타입 정보 수집 (semantic)
    """
    step = state.search_steps
    logger.info(f"search_plan_node: Planning step {step}/{state.max_search_steps}")

    # Step별 전략
    if step == 0:
        # 초기 검색: 심볼 찾기
        intent = CodeSearchIntent(
            entities=[state.query],  # 쿼리를 그대로 entity로
            keywords=[],
            strategy=SearchStrategy.HYBRID,
            limit=20,
            step=step,
        )
        logger.info(f"Step 0: Hybrid search for '{state.query}'")

    elif step == 1:
        # 확장 검색: 관계 탐색
        intent = CodeSearchIntent(
            entities=[],
            keywords=["caller", "usage", "calls"],
            strategy=SearchStrategy.GRAPH,
            graph_depth=2,
            edge_types=["calls", "uses"],
            limit=10,
            step=step,
        )
        logger.info("Step 1: Graph search for relationships")

    elif step == 2:
        # 타입 정보 수집
        intent = CodeSearchIntent(
            entities=[],
            keywords=["type", "interface", "class"],
            strategy=SearchStrategy.SEMANTIC,
            limit=10,
            step=step,
        )
        logger.info("Step 2: Semantic search for types")

    else:
        # 추가 검색 (generic)
        intent = CodeSearchIntent(
            entities=[],
            keywords=["related", "similar"],
            strategy=SearchStrategy.HYBRID,
            limit=5,
            step=step,
        )
        logger.info(f"Step {step}: Generic search")

    state.search_intents.append(intent)
    logger.info(
        f"Intent created: strategy={intent.strategy.value}, "
        f"entities={intent.entities}, keywords={intent.keywords}"
    )

    return state
