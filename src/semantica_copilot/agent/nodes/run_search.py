"""Run Search 노드"""

import logging
import os

from semantica_copilot.agent.state import AgentState
from semantica_copilot.tools.codegraph import BackendType, CodeGraphClient

logger = logging.getLogger(__name__)

# 전역 클라이언트 (DI로 개선 가능)
_client: CodeGraphClient | None = None


def get_client() -> CodeGraphClient:
    """클라이언트 싱글톤"""
    global _client
    if _client is None:
        base_url = os.getenv("CODEGRAPH_BASE_URL", "http://localhost:8000")
        _client = CodeGraphClient(backend=BackendType.HTTP, base_url=base_url)
        logger.info(f"CodeGraphClient initialized with base_url: {base_url}")
    return _client


async def run_search_node(state: AgentState) -> AgentState:
    """
    Run Search 노드

    Phase 2: search_plan에서 생성된 Intent 사용
    - Intent를 state.search_intents에서 가져옴
    - search_with_intent 호출
    - 결과를 accumulated_context에 추가
    """
    logger.info(f"run_search_node: Step {state.search_steps}")

    # Intent 가져오기 (search_plan에서 생성됨)
    if not state.search_intents:
        logger.error("No search intent found!")
        state.error = "No search intent"
        return state

    intent = state.search_intents[-1]
    logger.info(
        f"Using intent: step={intent.step}, strategy={intent.strategy.value}, "
        f"entities={intent.entities}, keywords={intent.keywords}"
    )

    try:
        # 검색 실행
        client = get_client()
        results = await client.search_with_intent(intent, repo_ids=state.repo_ids)

        logger.info(f"Found {len(results)} results")

        # 결과 누적 (중복 제거)
        added_count = 0
        for result in results:
            if state.accumulated_context.add_result(result):
                added_count += 1

        logger.info(f"Added {added_count}/{len(results)} results (after dedup)")

        state.search_steps += 1

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        state.error = str(e)

    return state
