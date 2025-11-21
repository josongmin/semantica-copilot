"""State 모델 테스트"""

import pytest

from semantica_copilot.agent.state import AgentState
from semantica_copilot.tools.codegraph import CodeSearchIntent, SearchResult, SearchStrategy


def test_search_strategy_enum():
    """SearchStrategy Enum 테스트"""
    assert SearchStrategy.HYBRID.value == "hybrid"
    assert SearchStrategy.GRAPH.value == "graph"


def test_code_search_intent_default():
    """CodeSearchIntent 기본값 테스트"""
    intent = CodeSearchIntent()
    assert intent.entities == []
    assert intent.keywords == []
    assert intent.strategy == SearchStrategy.HYBRID
    assert intent.limit == 20
    assert intent.graph_depth == 1


@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
def test_retrieved_context_add_result():
    """RetrievedContext.add_result 테스트"""
    ctx = None  # RetrievedContext()

    result1 = SearchResult(
        repo_id="repo1",
        chunk_id="chunk1",
        file_path="test.py",
        line_start=10,
        line_end=20,
        text="code",
        score=0.9,
        scores={},
    )

    # 첫 추가
    assert ctx.add_result(result1) is True
    assert len(ctx.results) == 1
    assert len(ctx.dedupe_keys) == 1

    # 중복 추가
    assert ctx.add_result(result1) is False
    assert len(ctx.results) == 1  # 변화 없음


@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
def test_retrieved_context_get_top_k():
    """RetrievedContext.get_top_k 테스트"""
    ctx = None  # RetrievedContext()

    for i in range(5):
        ctx.add_result(
            SearchResult(
                repo_id="repo1",
                chunk_id=f"chunk{i}",
                file_path=f"test{i}.py",
                line_start=i,
                line_end=i + 1,
                text="code",
                score=0.5 + i * 0.1,  # 점수 증가
                scores={},
            )
        )

    top3 = ctx.get_top_k(3)
    assert len(top3) == 3
    # 점수 역순 확인
    assert top3[0].score > top3[1].score > top3[2].score


def test_agent_state_default():
    """AgentState 기본값 테스트"""
    state = AgentState(query="test")

    assert state.query == "test"
    assert state.repo_ids is None
    assert state.execution_plan is None
    assert len(state.execution_results) == 0
    assert len(state.accumulated_chunks) == 0
    assert state.answer is None
    assert state.error is None
