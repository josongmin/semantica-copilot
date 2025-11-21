"""엣지 케이스 테스트"""

import pytest

from semantica_copilot.agent.routing import check_enough_context_heuristic, route_enough_context
from semantica_copilot.agent.state import AgentState
from semantica_copilot.tools.codegraph import CodeSearchIntent, SearchResult, SearchStrategy


def test_empty_query():
    """빈 쿼리 처리"""
    state = AgentState(query="", repo_ids=["test"])
    assert state.query == ""
    assert state.repo_ids == ["test"]


def test_no_repo_ids():
    """repo_ids 없음"""
    state = AgentState(query="test", repo_ids=None)
    assert state.query == "test"
    assert state.repo_ids is None


def test_empty_repo_ids_list():
    """repo_ids 빈 리스트"""
    state = AgentState(query="test", repo_ids=[])
    assert state.repo_ids == []


@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
def test_retrieved_context_empty():
    """빈 RetrievedContext"""
    ctx = None  # RetrievedContext()
    assert len(ctx.results) == 0
    assert len(ctx.dedupe_keys) == 0
    assert ctx.get_top_k(5) == []


@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
def test_get_top_k_more_than_results():
    """get_top_k: k > len(results)"""
    ctx = None  # RetrievedContext()

    ctx.add_result(
        SearchResult(
            repo_id="test",
            chunk_id="c1",
            file_path="f1.py",
            line_start=1,
            line_end=2,
            text="code",
            score=0.9,
            scores={},
        )
    )

    # k=10이지만 결과는 1개만
    top = ctx.get_top_k(10)
    assert len(top) == 1


@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
def test_get_top_k_zero():
    """get_top_k: k=0"""
    ctx = None  # RetrievedContext()
    ctx.add_result(
        SearchResult(
            repo_id="test",
            chunk_id="c1",
            file_path="f1.py",
            line_start=1,
            line_end=2,
            text="code",
            score=0.9,
            scores={},
        )
    )

    top = ctx.get_top_k(0)
    assert len(top) == 0


@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
def test_duplicate_detection_exact():
    """정확한 중복 감지"""
    ctx = None  # RetrievedContext()

    result = SearchResult(
        repo_id="test",
        chunk_id="c1",
        file_path="same.py",
        line_start=10,
        line_end=20,
        text="code",
        score=0.9,
        scores={},
    )

    assert ctx.add_result(result) is True
    assert len(ctx.results) == 1

    # 같은 repo_id:file_path:line_start
    assert ctx.add_result(result) is False
    assert len(ctx.results) == 1  # 여전히 1개


@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
def test_duplicate_different_chunk_id():
    """chunk_id는 다르지만 file:line이 같으면 중복"""
    ctx = None  # RetrievedContext()

    result1 = SearchResult(
        repo_id="test",
        chunk_id="c1",
        file_path="file.py",
        line_start=10,
        line_end=20,
        text="code",
        score=0.9,
        scores={},
    )

    result2 = SearchResult(
        repo_id="test",
        chunk_id="c2",  # 다른 chunk_id
        file_path="file.py",
        line_start=10,  # 같은 line_start
        line_end=20,
        text="code",
        score=0.8,
        scores={},
    )

    assert ctx.add_result(result1) is True
    assert ctx.add_result(result2) is False  # 중복!


def test_routing_no_results():
    """결과 없을 때 routing"""
    state = AgentState(query="test", search_steps=1, repo_ids=["test"])

    # 결과 없으면 finish
    assert route_enough_context(state) == "finish"


def test_routing_max_steps():
    """최대 스텝 도달"""
    state = AgentState(query="test", search_steps=3, max_search_steps=3)

    assert route_enough_context(state) == "finish"


def test_routing_high_score():
    """높은 점수로 조기 종료"""
    state = AgentState(query="test", search_steps=1, max_search_steps=3)

    # 점수 0.95 (>0.9)
    state.accumulated_context.add_result(
        SearchResult(
            repo_id="test",
            chunk_id="c1",
            file_path="f1.py",
            line_start=1,
            line_end=2,
            text="code",
            score=0.95,
            scores={},
        )
    )

    # 높은 점수로 조기 종료
    assert check_enough_context_heuristic(state) is True
    assert route_enough_context(state) == "finish"


def test_intent_with_empty_entities():
    """entities 없는 Intent"""
    intent = CodeSearchIntent(
        entities=[],
        keywords=["test"],
        strategy=SearchStrategy.HYBRID,
    )

    assert intent.entities == []
    assert intent.keywords == ["test"]


def test_intent_with_empty_keywords():
    """keywords 없는 Intent"""
    intent = CodeSearchIntent(
        entities=["UserService"],
        keywords=[],
        strategy=SearchStrategy.GRAPH,
    )

    assert intent.entities == ["UserService"]
    assert intent.keywords == []


def test_search_result_no_text():
    """text 없는 SearchResult"""
    result = SearchResult(
        repo_id="test",
        chunk_id="c1",
        file_path="f1.py",
        line_start=1,
        line_end=2,
        text="",  # 빈 문자열
        score=0.5,
        scores={},
    )

    assert result.text == ""
    assert len(result.text) == 0


def test_very_long_query():
    """매우 긴 쿼리"""
    long_query = "a" * 1000
    state = AgentState(query=long_query, repo_ids=["test"])

    assert len(state.query) == 1000
