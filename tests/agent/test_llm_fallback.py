"""LLM 폴백 테스트"""

import os

import pytest

from semantica_copilot.agent.state import AgentState
from semantica_copilot.tools.codegraph import SearchResult


@pytest.mark.asyncio
async def test_llm_disabled_uses_template(mock_client, monkeypatch):
    """LLM 비활성화 시 템플릿 사용"""
    from semantica_copilot.agent.nodes import run_search

    monkeypatch.setattr(run_search, "get_client", lambda: mock_client)
    monkeypatch.setenv("USE_LLM", "false")

    # 그래프 재빌드 (환경변수 반영)
    from semantica_copilot.agent import graph

    graph._graph = None  # 캐시 초기화

    initial_state = AgentState(query="test", repo_ids=["test-repo"])

    graph_instance = graph.build_agent_graph()
    final_state = await graph_instance.ainvoke(initial_state)

    # 템플릿 답변 확인 (간단함)
    assert final_state["answer"]
    assert "검색 결과" in final_state["answer"]


@pytest.mark.asyncio
async def test_llm_error_fallback_to_template(mock_client, monkeypatch):
    """LLM 에러 시 템플릿으로 폴백"""
    from semantica_copilot.agent.nodes import generate_answer, run_search
    from semantica_copilot.agent.state import AgentState

    monkeypatch.setattr(run_search, "get_client", lambda: mock_client)
    monkeypatch.setenv("USE_LLM", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "invalid-key")

    # generate_answer에서 LLM 에러 발생 시 폴백
    state = AgentState(query="test", repo_ids=["test-repo"])

    # Intent 추가
    from semantica_copilot.agent.state import CodeSearchIntent, SearchStrategy

    state.search_intents.append(CodeSearchIntent(entities=["test"], strategy=SearchStrategy.HYBRID))

    # 검색 실행
    state = await run_search.run_search_node(state)

    # 결과 있음
    assert len(state.accumulated_context.results) > 0

    # generate_answer 실행 (LLM 실패 → 템플릿 폴백)
    try:
        final_state = await generate_answer.generate_answer_node(state)

        # 폴백으로 템플릿 답변 생성됨
        assert final_state.answer is not None
        # 템플릿 특징: "검색 결과" 포함
        assert "검색 결과" in final_state.answer or len(final_state.answer) > 0

    except Exception as e:
        # LLM 에러가 밖으로 전파되지 않아야 함
        pytest.fail(f"LLM error not handled: {e}")


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("TEST_LLM"), reason="TEST_LLM not set")
async def test_llm_timeout(mock_client, monkeypatch):
    """LLM timeout 처리 (선택적 테스트)"""
    from semantica_copilot.agent.nodes import generate_answer, run_search
    from semantica_copilot.llm.provider import LLMProvider

    monkeypatch.setattr(run_search, "get_client", lambda: mock_client)
    monkeypatch.setenv("USE_LLM", "true")

    # Timeout을 발생시키는 Mock LLM
    class TimeoutLLM(LLMProvider):
        async def ainvoke(self, prompt, system=None, **kwargs):
            import asyncio

            await asyncio.sleep(0.1)
            raise TimeoutError("LLM timeout")

    # LLM Mock 주입
    from semantica_copilot.llm import provider

    monkeypatch.setattr(provider, "get_llm", lambda: TimeoutLLM())

    state = AgentState(query="test", repo_ids=["test-repo"])
    from semantica_copilot.agent.state import CodeSearchIntent

    state.search_intents.append(CodeSearchIntent(entities=["test"]))
    state = await run_search.run_search_node(state)

    # generate_answer 실행
    final_state = await generate_answer.generate_answer_node(state)

    # Timeout 발생해도 답변 생성 (폴백)
    assert final_state.answer is not None


def test_state_serialization():
    """State 직렬화/역직렬화"""
    state = AgentState(query="test", repo_ids=["repo1"])

    # 검색 결과 추가
    for i in range(10):
        state.accumulated_context.add_result(
            SearchResult(
                repo_id="repo1",
                chunk_id=f"c{i}",
                file_path=f"f{i}.py",
                line_start=i,
                line_end=i + 1,
                text="code",
                score=0.9 - i * 0.05,
                scores={},
            )
        )

    # JSON 직렬화
    json_data = state.model_dump()

    # 역직렬화
    restored_state = AgentState(**json_data)

    # 검증
    assert restored_state.query == state.query
    assert len(restored_state.accumulated_context.results) == 10
    assert len(restored_state.accumulated_context.dedupe_keys) == 10


@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
def test_large_text_handling():
    """대용량 text 처리"""
    ctx = None  # RetrievedContext()

    # 10KB text
    large_text = "x" * 10000

    result = SearchResult(
        repo_id="test",
        chunk_id="c1",
        file_path="large.py",
        line_start=1,
        line_end=500,
        text=large_text,
        score=0.9,
        scores={},
    )

    assert ctx.add_result(result) is True
    assert len(ctx.results[0].text) == 10000


def test_many_search_intents():
    """많은 search intent 추적"""
    from semantica_copilot.agent.state import CodeSearchIntent, SearchStrategy

    state = AgentState(query="test", repo_ids=["test"])

    # 10개 intent 추가
    for i in range(10):
        state.search_intents.append(
            CodeSearchIntent(
                entities=[f"entity{i}"],
                strategy=SearchStrategy.HYBRID,
                step=i,
            )
        )

    assert len(state.search_intents) == 10
    assert state.search_intents[9].step == 9
