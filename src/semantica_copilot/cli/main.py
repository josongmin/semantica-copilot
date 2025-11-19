"""CLI 진입점 (Phase 0: 함수 체인)"""

import asyncio
import logging
import sys
from typing import List

from semantica_copilot.agent.state import CodeSearchIntent, SearchStrategy
from semantica_copilot.tools.codegraph import BackendType, CodeGraphClient

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def simple_agent(
    query: str,
    repo_ids: List[str],
    base_url: str = "http://localhost:8000",
) -> str:
    """
    Phase 0: 단순 함수 체인

    목표: codegraph 연동 먼저 검증
    - LangGraph 없이 단순 함수 호출
    - 단일 검색
    - 템플릿 기반 답변
    """
    logger.info(f"Query: {query}")
    logger.info(f"Repo IDs: {repo_ids}")

    # 1. Intent 생성 (고정)
    intent = CodeSearchIntent(
        entities=[query],
        keywords=[],
        strategy=SearchStrategy.HYBRID,
        limit=10,
    )
    logger.info(f"Search intent: strategy={intent.strategy.value}, limit={intent.limit}")

    # 2. CodeGraphClient 초기화
    client = CodeGraphClient(
        backend=BackendType.HTTP,
        base_url=base_url,
    )

    try:
        # 3. 검색 실행
        logger.info("Searching...")
        results = await client.search_with_intent(intent, repo_ids)
        logger.info(f"Found {len(results)} results")

        if not results:
            return "검색 결과가 없습니다."

        # 4. 결과 포맷팅
        answer_parts = [f"검색 결과: {len(results)}개\n"]

        for i, result in enumerate(results[:5], 1):
            answer_parts.append(f"\n[{i}] {result.file_path}:{result.line_start}")
            answer_parts.append(f"Score: {result.score:.3f}")
            answer_parts.append(f"Scores: {result.scores}")

            # text 확인
            if result.text:
                preview = result.text[:200]
                if len(result.text) > 200:
                    preview += "..."
                answer_parts.append(f"Preview:\n{preview}")
            else:
                answer_parts.append("⚠️  text 필드 비어있음 (codegraph 수정 필요)")
            answer_parts.append("")

        return "\n".join(answer_parts)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return f"오류 발생: {e}"

    finally:
        await client.aclose()


async def async_main():
    """Async 진입점"""
    if len(sys.argv) < 2:
        print("Usage: python -m semantica_copilot.cli.main <query> [repo_id1,repo_id2,...]")
        print("\nExample:")
        print('  python -m semantica_copilot.cli.main "UserService" repo1')
        print('  python -m semantica_copilot.cli.main "async function" repo1,repo2')
        sys.exit(1)

    query = sys.argv[1]
    repo_ids = sys.argv[2].split(",") if len(sys.argv) > 2 else ["semantica-codegraph"]

    # 결과 출력
    answer = await simple_agent(query, repo_ids)
    print("\n" + "=" * 80)
    print(answer)
    print("=" * 80)


def main():
    """동기 진입점"""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
