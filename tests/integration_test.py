"""실제 codegraph 연동 테스트 (수동 실행)"""

import asyncio
import logging

import httpx

from semantica_copilot.agent.graph import build_agent_graph
from semantica_copilot.agent.state import AgentState, CodeSearchIntent, SearchStrategy
from semantica_copilot.tools.codegraph import BackendType, CodeGraphClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_codegraph_connection():
    """codegraph API 연결 테스트"""
    print("\n" + "=" * 80)
    print("1. codegraph API 연결 테스트")
    print("=" * 80)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/")
            print(f"✅ codegraph 실행 중: {response.json()}")
            return True
        except Exception as e:
            print(f"❌ codegraph 연결 실패: {e}")
            print("\n⚠️  codegraph를 먼저 실행하세요:")
            print("cd ../semantica-codegraph")
            print("python -m apps.api.main")
            return False


async def test_list_repos():
    """저장소 목록 조회 테스트"""
    print("\n" + "=" * 80)
    print("2. 저장소 목록 조회")
    print("=" * 80)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:8000/api/repos/")
            response.raise_for_status()
            repos = response.json()

            # 응답이 리스트인지 확인
            if not isinstance(repos, list):
                print(f"❌ 응답 형식 오류: {repos}")
                return []

            print(f"✅ 저장소 {len(repos)}개:")
            for repo in repos:
                print(
                    f"  - {repo.get('repo_id', 'unknown')}: {repo.get('name', 'unknown')} ({repo.get('total_nodes', 0)} nodes)"
                )
            return repos
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP 에러 {e.response.status_code}: {e.response.text}")
            return []
        except Exception as e:
            print(f"❌ 저장소 목록 조회 실패: {e}")
            import traceback

            traceback.print_exc()
            return []


async def test_search_api_directly():
    """검색 API 직접 호출 테스트"""
    print("\n" + "=" * 80)
    print("3. 검색 API 직접 테스트")
    print("=" * 80)

    async with httpx.AsyncClient() as client:
        try:
            # 첫 번째 repo 가져오기
            repos_response = await client.get("http://localhost:8000/api/repos/")
            repos = repos_response.json()

            if not repos:
                print("❌ 인덱싱된 저장소가 없습니다")
                print("\n⚠️  저장소를 먼저 인덱싱하세요:")
                print("cd ../semantica-codegraph")
                print("python -m apps.cli.main index /path/to/repo --repo-id test-repo")
                return None

            repo_id = repos[0]["repo_id"]
            print(f"테스트 repo: {repo_id}")

            # 검색 호출 (새로운 /hybrid/search API 사용)
            response = await client.post(
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
            response.raise_for_status()
            data = response.json()

            print(f"✅ 검색 성공: {len(data['candidates'])}개 후보")

            # 응답 구조 확인
            if data["candidates"]:
                first = data["candidates"][0]
                print("\n첫 번째 후보:")
                print(f"  candidate_id: {first.get('candidate_id')}")
                print(f"  chunk_id: {first.get('chunk_id')}")
                print(f"  file_path: {first.get('file_path')}")
                print(f"  span: {first.get('span')}")
                print(f"  final_score: {first.get('final_score')}")
                print(f"  scores: {first.get('scores')}")
                print(f"  snippet: {first.get('snippet', '')[:100]}...")
                print(f"  snippet 필드: {'snippet' in first} {'❌' if 'snippet' not in first else '✅'}")

            return data

        except Exception as e:
            print(f"❌ 검색 실패: {e}")
            return None


async def test_codegraph_client():
    """CodeGraphClient 테스트"""
    print("\n" + "=" * 80)
    print("4. CodeGraphClient 테스트")
    print("=" * 80)

    client = CodeGraphClient(backend=BackendType.HTTP, base_url="http://localhost:8000")

    try:
        # 저장소 목록 가져오기
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get("http://localhost:8000/api/repos/")
            repos = response.json()

        if not repos:
            print("❌ 저장소 없음")
            return False

        repo_id = repos[0]["repo_id"]
        print(f"테스트 repo: {repo_id}")

        # Intent 생성
        intent = CodeSearchIntent(
            entities=["class"],
            strategy=SearchStrategy.HYBRID,
            limit=5,
        )

        # 검색 실행
        results = await client.search_with_intent(intent, repo_ids=[repo_id])

        print(f"✅ CodeGraphClient 검색 성공: {len(results)}개 결과")

        if results:
            first = results[0]
            print("\n첫 번째 결과:")
            print(f"  repo_id: {first.repo_id}")
            print(f"  file_path: {first.file_path}")
            print(f"  line_start: {first.line_start}")
            print(f"  line_end: {first.line_end}")
            print(f"  score: {first.score:.3f}")
            print(f"  text: {len(first.text)} chars {'⚠️ 빈 문자열' if not first.text else '✅'}")

        await client.aclose()
        return True

    except Exception as e:
        print(f"❌ CodeGraphClient 테스트 실패: {e}")
        await client.aclose()
        return False


async def test_agent_graph():
    """전체 Agent 그래프 테스트"""
    print("\n" + "=" * 80)
    print("5. Agent 그래프 테스트")
    print("=" * 80)

    try:
        # 저장소 목록 가져오기
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get("http://localhost:8000/api/repos/")
            repos = response.json()

        if not repos:
            print("❌ 저장소 없음")
            return False

        repo_id = repos[0]["repo_id"]
        print(f"테스트 repo: {repo_id}")

        # 초기 state
        initial_state = AgentState(
            query="class",
            repo_ids=[repo_id],
        )

        # 그래프 실행
        graph = build_agent_graph()
        print("그래프 실행 중...")
        final_state = await graph.ainvoke(initial_state)

        print("✅ 그래프 실행 완료:")
        print(f"  search_steps: {final_state['search_steps']}")
        print(f"  total_results: {len(final_state['accumulated_context'].results)}")
        print(f"  answer: {len(final_state.get('answer', ''))} chars")

        if final_state.get("error"):
            print(f"  ⚠️  error: {final_state['error']}")

        # 답변 미리보기
        if final_state.get("answer"):
            preview = final_state["answer"][:200]
            print(f"\n답변 미리보기:\n{preview}...")

        return True

    except Exception as e:
        print(f"❌ 그래프 테스트 실패: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """전체 연동 테스트"""
    print("\n" + "🚀 " * 20)
    print("Semantica Copilot - 연동 테스트")
    print("🚀 " * 20)

    # 1. 연결 확인
    connected = await test_codegraph_connection()
    if not connected:
        return

    # 2. 저장소 목록
    repos = await test_list_repos()
    if not repos:
        return

    # 3. 검색 API 직접 호출
    await test_search_api_directly()

    # 4. CodeGraphClient 테스트
    await test_codegraph_client()

    # 5. Agent 그래프 테스트
    await test_agent_graph()

    print("\n" + "✅ " * 20)
    print("연동 테스트 완료!")
    print("✅ " * 20 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
