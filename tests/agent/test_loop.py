"""Loop 테스트 (Phase 2)"""

import pytest

from semantica_copilot.agent.graph import build_agent_graph
from semantica_copilot.agent.state import AgentState


@pytest.mark.asyncio
async def test_graph_loop_flow(mock_client, monkeypatch):
    """루프 플로우 테스트 (max_steps=2)"""
    from semantica_copilot.agent.nodes import run_search

    monkeypatch.setattr(run_search, "get_client", lambda: mock_client)

    # 초기 state
    initial_state = AgentState(
        query="test loop",
        repo_ids=["test-repo"],
    )

    # 그래프 실행
    graph = build_agent_graph()
    final_state = await graph.ainvoke(initial_state)

    # 검증
    assert final_state["search_steps"] == 2  # max_search_steps
    assert len(final_state["search_intents"]) == 2  # 2번 검색
    assert len(final_state["accumulated_context"].results) > 0
    assert final_state["answer"] is not None


@pytest.mark.asyncio
async def test_graph_early_termination(mock_client, monkeypatch):
    """조기 종료 테스트 (충분한 결과)"""
    from semantica_copilot.agent.nodes import run_search
    from semantica_copilot.agent.state import SearchResult
    from semantica_copilot.tools.codegraph import CodeGraphClient

    # 많은 결과를 반환하는 Mock
    class ManyResultsClient(CodeGraphClient):
        def __init__(self):
            pass

        async def search_with_intent(self, intent, repo_ids=None):
            # 31개 결과 반환 (종료 조건: >=30)
            return [
                SearchResult(
                    repo_id="test-repo",
                    chunk_id=f"chunk-{i}",
                    file_path=f"test_{i}.py",
                    line_start=i,
                    line_end=i + 1,
                    text="code",
                    score=0.8,
                    scores={},
                )
                for i in range(31)
            ]

    monkeypatch.setattr(run_search, "get_client", ManyResultsClient)

    initial_state = AgentState(
        query="test early",
        repo_ids=["test-repo"],
    )

    graph = build_agent_graph()
    final_state = await graph.ainvoke(initial_state)

    # 1번만 검색하고 종료
    assert final_state["search_steps"] == 1
    assert len(final_state["accumulated_context"].results) >= 30


@pytest.mark.asyncio
async def test_routing_function():
    """Routing 함수 단독 테스트"""
    from semantica_copilot.agent.routing import route_enough_context
    from semantica_copilot.agent.state import SearchResult

    # 케이스 1: 에러 발생
    state = AgentState(query="test", error="test error")
    assert route_enough_context(state) == "finish"

    # 케이스 2: 최대 스텝 도달
    state = AgentState(query="test", search_steps=3, max_search_steps=3)
    assert route_enough_context(state) == "finish"

    # 케이스 3: 충분한 결과
    state = AgentState(query="test")
    for i in range(31):
        state.accumulated_context.add_result(
            SearchResult(
                repo_id="test",
                chunk_id=f"c{i}",
                file_path=f"f{i}.py",
                line_start=i,
                line_end=i + 1,
                text="code",
                score=0.5,
                scores={},
            )
        )
    assert route_enough_context(state) == "finish"

    # 케이스 4: 계속 검색
    state = AgentState(query="test", search_steps=1, max_search_steps=3)
    state.accumulated_context.add_result(
        SearchResult(
            repo_id="test",
            chunk_id="c1",
            file_path="f1.py",
            line_start=1,
            line_end=2,
            text="code",
            score=0.5,
            scores={},
        )
    )
    assert route_enough_context(state) == "continue"
