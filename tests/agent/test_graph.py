"""Graph 테스트"""

import pytest

from semantica_copilot.agent.graph import build_agent_graph
from semantica_copilot.agent.state import AgentState


@pytest.mark.asyncio
async def test_graph_basic_flow(mock_client, monkeypatch):
    """기본 그래프 플로우 테스트 (Phase 2: Loop)"""
    # Mock 클라이언트 주입
    from semantica_copilot.agent.nodes import run_search

    monkeypatch.setattr(run_search, "get_client", lambda: mock_client)

    # 초기 state
    initial_state = AgentState(
        query="test function",
        repo_ids=["test-repo"],
    )

    # 그래프 실행
    graph = build_agent_graph()
    final_state = await graph.ainvoke(initial_state)

    # 검증
    assert final_state["plan"] is not None
    assert final_state["plan"]["task"] == "code_explanation"
    assert final_state["search_steps"] >= 1  # Phase 2: 1-2회 검색
    assert final_state["search_steps"] <= 2
    assert len(final_state["accumulated_context"].results) > 0
    assert final_state["answer"] is not None
    assert "test function" in final_state["answer"]


@pytest.mark.asyncio
async def test_graph_with_error(monkeypatch):
    """에러 발생 시 그래프 동작 테스트"""
    from semantica_copilot.agent.nodes import run_search
    from semantica_copilot.tools.codegraph import CodeGraphClient

    # 에러를 발생시키는 Mock 클라이언트
    class ErrorClient(CodeGraphClient):
        def __init__(self):
            pass

        async def search_with_intent(self, intent, repo_ids=None):
            raise Exception("Test error")

    monkeypatch.setattr(run_search, "get_client", ErrorClient)

    initial_state = AgentState(
        query="test",
        repo_ids=["test-repo"],
    )

    graph = build_agent_graph()
    final_state = await graph.ainvoke(initial_state)

    # 에러 응답 확인
    assert final_state["error"] is not None
    assert "Test error" in final_state["error"]
    assert "오류" in final_state["answer"]
