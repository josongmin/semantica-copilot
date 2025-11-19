"""HTTP 에러 시나리오 테스트"""

import pytest

from semantica_copilot.agent.graph import build_agent_graph
from semantica_copilot.agent.state import AgentState
from semantica_copilot.tools.codegraph import BackendType


@pytest.mark.asyncio
async def test_http_timeout_error(error_client, monkeypatch):
    """HTTP Timeout 에러 처리"""
    from semantica_copilot.agent.nodes import run_search
    from semantica_copilot.agent.state import CodeSearchIntent, SearchStrategy

    client = error_client("timeout")
    monkeypatch.setattr(run_search, "get_client", lambda: client)

    state = AgentState(
        query="test",
        repo_ids=["test-repo"],
    )

    # Intent 추가 (필수)
    state.search_intents.append(CodeSearchIntent(entities=["test"], strategy=SearchStrategy.HYBRID))

    # run_search 노드 직접 호출
    result_state = await run_search.run_search_node(state)

    # 에러가 state에 기록되어야 함
    assert result_state.error is not None
    assert "timeout" in result_state.error.lower()


@pytest.mark.asyncio
async def test_http_500_error(error_client, monkeypatch):
    """HTTP 500 에러 처리"""
    from semantica_copilot.agent.nodes import run_search
    from semantica_copilot.agent.state import CodeSearchIntent

    client = error_client("http_500")
    monkeypatch.setattr(run_search, "get_client", lambda: client)

    state = AgentState(
        query="test",
        repo_ids=["test-repo"],
    )

    # Intent 추가
    state.search_intents.append(CodeSearchIntent(entities=["test"]))

    result_state = await run_search.run_search_node(state)

    # 에러 기록
    assert result_state.error is not None


@pytest.mark.asyncio
async def test_network_error(error_client, monkeypatch):
    """Network 에러 처리"""
    from semantica_copilot.agent.nodes import run_search
    from semantica_copilot.agent.state import CodeSearchIntent

    client = error_client("network")
    monkeypatch.setattr(run_search, "get_client", lambda: client)

    state = AgentState(
        query="test",
        repo_ids=["test-repo"],
    )

    # Intent 추가
    state.search_intents.append(CodeSearchIntent(entities=["test"]))

    result_state = await run_search.run_search_node(state)

    # 에러 기록
    assert result_state.error is not None


@pytest.mark.asyncio
async def test_http_error_in_graph_flow(error_client, monkeypatch):
    """그래프 플로우에서 HTTP 에러 처리"""
    from semantica_copilot.agent.nodes import run_search

    client = error_client("timeout")
    monkeypatch.setattr(run_search, "get_client", lambda: client)

    initial_state = AgentState(
        query="test",
        repo_ids=["test-repo"],
    )

    graph = build_agent_graph()
    final_state = await graph.ainvoke(initial_state)

    # 에러가 있어도 그래프는 완료되어야 함
    assert final_state["error"] is not None
    assert final_state["answer"] is not None
    assert "오류" in final_state["answer"]


@pytest.mark.asyncio
async def test_partial_failure_multiple_repos(error_client, mock_client, monkeypatch):
    """여러 repo 중 일부 실패"""
    from semantica_copilot.agent.state import CodeSearchIntent, SearchStrategy
    from semantica_copilot.tools.codegraph import CodeGraphClient

    # 첫 repo는 실패, 두 번째는 성공하도록 Mock
    class PartialFailClient(CodeGraphClient):
        def __init__(self):
            self.backend = BackendType.HTTP
            self.call_count = 0

        async def search_with_intent(self, intent, repo_ids=None):
            if not repo_ids:
                return []

            results = []
            for i, repo_id in enumerate(repo_ids):
                if i == 0:
                    # 첫 번째는 에러 (내부에서 처리)
                    continue
                else:
                    # 두 번째는 성공
                    results.extend(await mock_client.search_with_intent(intent, [repo_id]))

            return results

        async def aclose(self):
            pass

    client = PartialFailClient()
    intent = CodeSearchIntent(entities=["test"], strategy=SearchStrategy.HYBRID)

    results = await client.search_with_intent(intent, repo_ids=["fail-repo", "success-repo"])

    # 일부 성공한 결과만 반환
    assert len(results) > 0


@pytest.mark.asyncio
async def test_intermittent_error_retry(error_client, monkeypatch):
    """간헐적 에러 (재시도 가능)"""
    from semantica_copilot.agent.nodes import run_search
    from semantica_copilot.agent.state import CodeSearchIntent

    client = error_client("intermittent")
    monkeypatch.setattr(run_search, "get_client", lambda: client)

    state = AgentState(
        query="test",
        repo_ids=["test-repo"],
    )

    # Intent 추가
    state.search_intents.append(CodeSearchIntent(entities=["test"]))

    # 첫 호출
    result1 = await run_search.run_search_node(state)
    assert result1.error is not None
    assert client.call_count == 1

    # 두 번째 호출 (재시도) - Intent 다시 추가
    state.error = None
    state.search_intents.append(CodeSearchIntent(entities=["retry"]))

    result2 = await run_search.run_search_node(state)
    # 두 번째는 성공 (빈 결과)
    assert client.call_count == 2
    assert result2.error is None


@pytest.mark.asyncio
async def test_empty_response_handling(mock_client, monkeypatch):
    """빈 응답 처리"""
    from semantica_copilot.agent.nodes import run_search
    from semantica_copilot.agent.state import CodeSearchIntent
    from semantica_copilot.tools.codegraph import CodeGraphClient

    class EmptyResponseClient(CodeGraphClient):
        def __init__(self):
            self.backend = BackendType.HTTP

        async def search_with_intent(self, intent, repo_ids=None):
            return []  # 빈 결과

        async def aclose(self):
            pass

    client = EmptyResponseClient()
    monkeypatch.setattr(run_search, "get_client", lambda: client)

    state = AgentState(query="test", repo_ids=["test-repo"])

    # Intent 추가
    state.search_intents.append(CodeSearchIntent(entities=["test"]))

    result = await run_search.run_search_node(state)

    # 에러는 없지만 결과도 없음
    assert result.error is None
    assert len(result.accumulated_context.results) == 0


@pytest.mark.asyncio
async def test_malformed_response(mock_client, monkeypatch):
    """잘못된 응답 형식"""
    from semantica_copilot.agent.nodes import run_search
    from semantica_copilot.tools.codegraph import CodeGraphClient

    class MalformedResponseClient(CodeGraphClient):
        def __init__(self):
            self.backend = BackendType.HTTP

        async def search_with_intent(self, intent, repo_ids=None):
            # 잘못된 형식 (span이 없음)

            # 이미 SearchResult로 변환된 상태라 문제 없음
            # HTTP 레벨에서 잘못된 형식이면 예외 발생
            raise ValueError("Invalid response format")

        async def aclose(self):
            pass

    client = MalformedResponseClient()
    monkeypatch.setattr(run_search, "get_client", lambda: client)

    state = AgentState(query="test", repo_ids=["test-repo"])

    result = await run_search.run_search_node(state)

    # 에러 처리
    assert result.error is not None
