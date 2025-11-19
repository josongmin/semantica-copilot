#!/usr/bin/env python
"""간단한 E2E 테스트 스크립트"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from semantica_copilot.agent.graph import get_graph
from semantica_copilot.agent.state import AgentState

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# .env 파일 로드
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # 상위 디렉토리에서도 찾기
    load_dotenv(Path(__file__).parent.parent / ".env")

# Codegraph API URL 확인
codegraph_url = os.getenv("CODEGRAPH_BASE_URL", "http://localhost:8000")
print(f"Codegraph API URL: {codegraph_url}")

# LLM 모드 설정 (선택)
USE_LLM = len(sys.argv) > 1 and sys.argv[1] == "--llm"

if USE_LLM:
    print("LLM 모드")
    if not os.getenv("OPENAI_API_KEY"):
        print("경고: OPENAI_API_KEY가 설정되지 않았습니다")
        print(".env 파일에 OPENAI_API_KEY를 설정하거나 환경변수로 export하세요")
        sys.exit(1)
    os.environ["USE_LLM"] = "true"
else:
    print("템플릿 모드")
    os.environ["USE_LLM"] = "false"


async def test():
    """간단한 E2E 테스트"""

    # State 생성
    state: AgentState = AgentState(
        query="HybridRetriever는 무엇인가?", repo_ids=["semantica-codegraph"]
    )

    print("\n" + "=" * 80)
    print(f"Query: {state.query}")
    print(f"Repo: {state.repo_ids}")
    print("=" * 80)

    # 그래프 실행
    logger.info("그래프 초기화 중...")
    graph = get_graph()

    logger.info("그래프 실행 시작 (intent_plan_node부터 자동 실행)")
    result = await graph.ainvoke(state)
    logger.info(
        f"그래프 실행 완료: {result['search_steps']}단계, {len(result['accumulated_context'].results)}개 결과"
    )

    # 결과 출력
    print("=" * 80)
    print("결과:")
    print("=" * 80)
    print(f"검색 단계: {result['search_steps']}")
    print(f"총 결과: {len(result['accumulated_context'].results)}")
    print(f"답변 길이: {len(result.get('answer', ''))} chars")

    if result.get("error"):
        print(f"에러: {result['error']}")

    print("\n" + "=" * 80)
    print("답변:")
    print("=" * 80)
    print(result["answer"])
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test())
