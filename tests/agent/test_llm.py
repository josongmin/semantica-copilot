"""LLM 통합 테스트"""

import os

import pytest

from semantica_copilot.agent.prompts.templates import build_code_explain_prompt
from semantica_copilot.agent.state import AgentState, SearchResult


def test_build_code_explain_prompt():
    """Code explain 프롬프트 생성 테스트"""
    state = AgentState(query="What is HybridRetriever?")

    # 결과 추가
    for i in range(3):
        state.accumulated_context.add_result(
            SearchResult(
                repo_id="test",
                chunk_id=f"c{i}",
                file_path=f"file{i}.py",
                line_start=i * 10,
                line_end=i * 10 + 5,
                text=f"def function{i}():\n    pass",
                score=0.9 - i * 0.1,
                scores={},
            )
        )

    prompt = build_code_explain_prompt(state)

    # 프롬프트 검증
    assert "What is HybridRetriever?" in prompt
    assert "file0.py" in prompt
    assert "def function0():" in prompt


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
async def test_llm_generation(mock_client, monkeypatch):
    """실제 LLM 생성 테스트 (OPENAI_API_KEY 필요)"""
    from semantica_copilot.agent.graph import build_agent_graph
    from semantica_copilot.agent.nodes import run_search

    monkeypatch.setattr(run_search, "get_client", lambda: mock_client)
    monkeypatch.setenv("USE_LLM", "true")

    # 초기 state
    initial_state = AgentState(
        query="What is a class?",
        repo_ids=["test-repo"],
    )

    # 그래프 실행
    graph = build_agent_graph()
    final_state = await graph.ainvoke(initial_state)

    # LLM 답변 확인
    assert final_state["answer"]
    assert len(final_state["answer"]) > 100  # LLM은 더 긴 답변 생성
    # "요약", "상세" 같은 섹션이 있을 것으로 예상
