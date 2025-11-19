"""실제 codegraph API 연동 테스트"""

import httpx
import pytest

from semantica_copilot.agent.graph import build_agent_graph
from semantica_copilot.agent.state import AgentState, CodeSearchIntent, SearchStrategy
from semantica_copilot.tools.codegraph import BackendType, CodeGraphClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_codegraph_connection(codegraph_available):
    """codegraph API 연결 테스트"""
    is_available = await codegraph_available()

    if not is_available:
        pytest.skip("codegraph not running on localhost:8000")

    # 실제 API 호출
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/")
        assert response.status_code == 200
        data = response.json()
        assert data.get("service") == "semantica-codegraph"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_real_search_api(codegraph_available):
    """실제 검색 API 호출 테스트"""
    is_available = await codegraph_available()

    if not is_available:
        pytest.skip("codegraph not running")

    # 저장소 목록 확인
    async with httpx.AsyncClient() as client:
        repos_response = await client.get("http://localhost:8000/api/repos/")
        repos = repos_response.json()

        if not repos or not isinstance(repos, list) or len(repos) == 0:
            pytest.skip("No repositories indexed")

        # 첫 번째 repo로 검색 (새로운 /hybrid/search API 사용)
        repo_id = repos[0]["repo_id"]

        search_response = await client.post(
            "http://localhost:8000/hybrid/search",
            json={
                "query": "class",
                "k": 5,
                "location_ctx": {
                    "repo_id": repo_id,
                    "file_path": "",
                    "line": 0,
                    "column": 0,
                },
            },
        )

        assert search_response.status_code == 200
        data = search_response.json()
        assert "candidates" in data
        assert "query" in data
        assert "k" in data

        # 후보 필드 확인
        if data["candidates"]:
            first = data["candidates"][0]
            assert "candidate_id" in first
            assert "chunk_id" in first
            assert "file_path" in first
            assert "span" in first
            assert "final_score" in first
            assert "scores" in first
            assert "snippet" in first


@pytest.mark.asyncio
@pytest.mark.integration
async def test_codegraph_client_real(codegraph_available):
    """CodeGraphClient 실제 HTTP 연동"""
    is_available = await codegraph_available()

    if not is_available:
        pytest.skip("codegraph not running")

    # 저장소 확인
    async with httpx.AsyncClient() as http_client:
        repos_response = await http_client.get("http://localhost:8000/api/repos/")
        repos = repos_response.json()

        if not repos or len(repos) == 0:
            pytest.skip("No repositories")

    repo_id = repos[0]["repo_id"]

    # CodeGraphClient 사용
    client = CodeGraphClient(backend=BackendType.HTTP, base_url="http://localhost:8000")

    try:
        intent = CodeSearchIntent(
            entities=["class"],
            strategy=SearchStrategy.HYBRID,
            limit=5,
        )

        results = await client.search_with_intent(intent, repo_ids=[repo_id])

        # 검증
        assert isinstance(results, list)

        if results:
            first = results[0]
            assert first.repo_id == repo_id
            assert first.chunk_id
            assert first.file_path
            assert first.line_start >= 0
            assert first.line_end >= first.line_start
            assert first.score >= 0
            # text는 있을 수도 없을 수도 있음

    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_agent_full_flow_real(codegraph_available, monkeypatch):
    """Agent 전체 플로우 실제 연동"""
    is_available = await codegraph_available()

    if not is_available:
        pytest.skip("codegraph not running")

    # 저장소 확인
    async with httpx.AsyncClient() as http_client:
        repos_response = await http_client.get("http://localhost:8000/api/repos/")
        repos = repos_response.json()

        if not repos or len(repos) == 0:
            pytest.skip("No repositories")

    repo_id = repos[0]["repo_id"]

    # 실제 클라이언트 사용하도록 설정
    monkeypatch.setenv("CODEGRAPH_BASE_URL", "http://localhost:8000")

    # 초기 state
    initial_state = AgentState(
        query="class definition",
        repo_ids=[repo_id],
    )

    # 그래프 실행
    graph = build_agent_graph()
    final_state = await graph.ainvoke(initial_state)

    # 검증
    assert final_state["plan"] is not None
    assert final_state["search_steps"] >= 1
    assert final_state["search_steps"] <= 2
    assert final_state["answer"] is not None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_multiple_repos_real(codegraph_available):
    """여러 repo 동시 검색 (실제)"""
    is_available = await codegraph_available()

    if not is_available:
        pytest.skip("codegraph not running")

    # 저장소 목록
    async with httpx.AsyncClient() as http_client:
        repos_response = await http_client.get("http://localhost:8000/api/repos/")
        repos = repos_response.json()

        if not repos or len(repos) < 2:
            pytest.skip("Need at least 2 repositories")

    # 첫 2개 repo
    repo_ids = [repos[0]["repo_id"], repos[1]["repo_id"]]

    client = CodeGraphClient(backend=BackendType.HTTP, base_url="http://localhost:8000")

    try:
        intent = CodeSearchIntent(
            entities=["function"],
            strategy=SearchStrategy.HYBRID,
            limit=3,
        )

        results = await client.search_with_intent(intent, repo_ids=repo_ids)

        # 두 repo 모두에서 결과 수집
        assert isinstance(results, list)
        # 결과가 있다면 여러 repo에서 온 것
        if results:
            unique_repos = set(r.repo_id for r in results)
            # 최소 1개 repo에서 결과 (2개일 수도)
            assert len(unique_repos) >= 1

    finally:
        await client.aclose()
