"""성능 테스트"""

import time

import pytest

from semantica_copilot.agent.state import AgentState
from semantica_copilot.tools.codegraph import SearchResult


@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
def test_dedupe_performance_100_results():
    """중복 제거 성능 (100개 결과)"""
    ctx = None  # RetrievedContext()

    start = time.time()

    # 100개 결과 추가 (50% 중복)
    for i in range(100):
        result = SearchResult(
            repo_id="test",
            chunk_id=f"chunk-{i}",
            file_path=f"file_{i % 50}.py",  # 50% 중복
            line_start=i % 50,
            line_end=(i % 50) + 5,
            text=f"code {i}",
            score=0.9,
            scores={},
        )
        ctx.add_result(result)

    elapsed = time.time() - start

    # 성능 확인
    assert len(ctx.results) == 50  # 50개만 추가됨 (50% 중복)
    assert elapsed < 0.1  # 100ms 이내


@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
def test_dedupe_performance_1000_results():
    """중복 제거 성능 (1000개 결과)"""
    ctx = None  # RetrievedContext()

    start = time.time()

    # 1000개 결과 추가 (10% 중복)
    for i in range(1000):
        result = SearchResult(
            repo_id="test",
            chunk_id=f"chunk-{i}",
            file_path=f"file_{i % 100}.py",
            line_start=i % 100,
            line_end=(i % 100) + 5,
            text=f"code {i}",
            score=0.9,
            scores={},
        )
        ctx.add_result(result)

    elapsed = time.time() - start

    # 성능 확인
    assert len(ctx.results) == 100  # 100개만 추가됨
    assert elapsed < 1.0  # 1초 이내


@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
def test_get_top_k_performance():
    """get_top_k 정렬 성능"""
    ctx = None  # RetrievedContext()

    # 1000개 결과 추가
    for i in range(1000):
        ctx.add_result(
            SearchResult(
                repo_id="test",
                chunk_id=f"c{i}",
                file_path=f"f{i}.py",
                line_start=i,
                line_end=i + 1,
                text="code",
                score=0.5 + (i % 100) * 0.001,  # 무작위 점수
                scores={},
            )
        )

    start = time.time()
    top10 = ctx.get_top_k(10)
    elapsed = time.time() - start

    # 성능 확인
    assert len(top10) == 10
    assert elapsed < 0.1  # 100ms 이내

    # 정렬 확인
    for i in range(9):
        assert top10[i].score >= top10[i + 1].score


@pytest.mark.asyncio
async def test_large_context_aggregate(large_results_client, monkeypatch):
    """대량 컨텍스트 aggregate 동작"""
    from semantica_copilot.agent.nodes import aggregate_context, run_search

    client = large_results_client(100)
    monkeypatch.setattr(run_search, "get_client", lambda: client)

    state = AgentState(query="test", repo_ids=["test-repo"])

    # Intent 추가
    from semantica_copilot.agent.state import CodeSearchIntent, SearchStrategy

    state.search_intents.append(CodeSearchIntent(entities=["test"], strategy=SearchStrategy.HYBRID))

    # 검색 실행
    state = await run_search.run_search_node(state)

    # 100개 결과 수집
    assert len(state.accumulated_context.results) == 100

    # Aggregate 실행
    state = aggregate_context.aggregate_context_node(state)

    # 상위 50개만 유지
    assert len(state.accumulated_context.results) == 50

    # 점수순 정렬 확인
    results = state.accumulated_context.results
    for i in range(len(results) - 1):
        assert results[i].score >= results[i + 1].score


@pytest.mark.asyncio
async def test_multiple_search_steps_performance(large_results_client, monkeypatch):
    """여러 검색 단계 성능"""
    from semantica_copilot.agent.nodes import aggregate_context, run_search

    client = large_results_client(30)
    monkeypatch.setattr(run_search, "get_client", lambda: client)

    state = AgentState(query="test", repo_ids=["test-repo"], max_search_steps=5)

    start = time.time()

    # 5번 검색 시뮬레이션
    from semantica_copilot.agent.state import CodeSearchIntent, SearchStrategy

    for step in range(5):
        state.search_intents.append(
            CodeSearchIntent(entities=["test"], strategy=SearchStrategy.HYBRID, step=step)
        )
        state = await run_search.run_search_node(state)
        state = aggregate_context.aggregate_context_node(state)

    elapsed = time.time() - start

    # 성능 확인
    assert state.search_steps == 5
    assert len(state.accumulated_context.results) <= 50  # aggregate로 제한
    assert elapsed < 1.0  # 1초 이내


@pytest.mark.skip(reason="RetrievedContext는 더 이상 사용되지 않음")
def test_dedupe_set_creation_overhead():
    """_dedupe_set 생성 오버헤드 측정"""
    ctx = None  # RetrievedContext()

    # 100개 추가
    for i in range(100):
        ctx.add_result(
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

    # 중복 체크 성능 (매번 set 생성)
    start = time.time()

    for _ in range(1000):
        # 중복 체크 1000회
        _ = ctx._dedupe_set

    elapsed = time.time() - start

    # O(n) × 1000회
    # 100개 기준 0.1초 이내여야 함
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_concurrent_searches(mock_client, monkeypatch):
    """동시 검색 (미래: 병렬 검색 지원 시)"""
    from semantica_copilot.agent.nodes import run_search

    monkeypatch.setattr(run_search, "get_client", lambda: mock_client)

    # 여러 state 동시 실행
    import asyncio

    states = [AgentState(query=f"test{i}", repo_ids=["test-repo"]) for i in range(10)]

    # 동시 실행
    results = await asyncio.gather(*[build_and_run_graph(state) for state in states])

    # 10개를 순차로 하면 ~2초, 병렬이면 ~0.5초
    assert len(results) == 10
    # 모두 완료
    for result in results:
        assert result["answer"] is not None


async def build_and_run_graph(state):
    """헬퍼: 그래프 빌드 및 실행"""
    from semantica_copilot.agent.graph import build_agent_graph

    graph = build_agent_graph()
    return await graph.ainvoke(state)
