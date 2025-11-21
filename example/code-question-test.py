#!/usr/bin/env python
"""
간단한 E2E 테스트 스크립트

사용법:
  python code-question-test.py [옵션] [검색어]

옵션:
  --llm     LLM 모드 (GPT-4 사용, OPENAI_API_KEY 필요)
  --toon    TOON 형식 결과 출력

예시:
  python code-question-test.py "이거 뭐하는 프로젝트야"
  python code-question-test.py --llm "UserService 클래스 어디 있어?"
  python code-question-test.py --llm --toon "authenticate 함수가 뭐 하는 거야?"
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from semantica_copilot.agent.graph import get_graph
from semantica_copilot.agent.state import AgentState
from semantica_copilot.utils.toon import encode_to_toon, get_token_stats

# 로그 디렉토리 생성
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 타임스탬프로 로그 파일명 생성
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOG_DIR / f"test_{TIMESTAMP}.log"
JSON_LOG_FILE = LOG_DIR / f"test_{TIMESTAMP}.jsonl"

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# JSON 로그 파일 핸들러
json_log_file = open(JSON_LOG_FILE, "w", encoding="utf-8")


def log_json(event_type: str, data: Dict[str, Any], timestamp: Optional[float] = None):
    """구조화된 JSON 로그 기록"""
    if timestamp is None:
        timestamp = time.time()

    log_entry = {
        "timestamp": timestamp,
        "datetime": datetime.fromtimestamp(timestamp).isoformat(),
        "event_type": event_type,
        "data": data,
    }
    json_log_file.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
    json_log_file.flush()


# .env 파일 로드
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # 상위 디렉토리에서도 찾기
    load_dotenv(Path(__file__).parent.parent / ".env")

# Help 메시지
if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)

# Codegraph API URL 확인
codegraph_url = os.getenv("CODEGRAPH_BASE_URL", "http://localhost:8000")
print(f"Codegraph API URL: {codegraph_url}")

# Command-line arguments 파싱
USE_LLM = "--llm" in sys.argv
USE_TOON = "--toon" in sys.argv

# Query 추출 (--llm, --toon 제외한 첫 번째 인자)
QUERY = "이거 뭐하는 프로젝트야"  # 기본값
for arg in sys.argv[1:]:
    if not arg.startswith("--"):
        QUERY = arg
        break

print(f"Query: {QUERY}")

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


async def test() -> None:
    """간단한 E2E 테스트"""

    total_start = time.time()

    logger.info(f"로그 파일: {LOG_FILE}")
    logger.info(f"JSON 로그 파일: {JSON_LOG_FILE}")

    # State 생성
    state: AgentState = AgentState(query=QUERY, repo_ids=["semantica-codegraph"])

    # 초기 설정 로깅
    log_json(
        "test_start",
        {
            "query": QUERY,
            "repo_ids": state.repo_ids,
            "use_llm": USE_LLM,
            "use_toon": USE_TOON,
            "codegraph_url": codegraph_url,
        },
        total_start,
    )

    print("\n" + "=" * 80)
    print(f"Query: {state.query}")
    print(f"Repo: {state.repo_ids}")
    print(f"로그 파일: {LOG_FILE}")
    print("=" * 80)

    # 그래프 초기화 시간 측정
    init_start = time.time()
    logger.info("그래프 초기화 중...")
    graph = get_graph()
    init_time = time.time() - init_start
    logger.info(f"그래프 초기화 완료: {init_time:.3f}초")

    # 그래프 실행 시간 측정 (스트리밍으로 각 노드별 시간 추적)
    exec_start = time.time()
    logger.info("그래프 실행 시작 (intent_plan_node부터 자동 실행)")

    node_times = {}  # 노드별 누적 실행 시간
    node_start_times = {}  # 노드별 시작 시간
    node_execution_count = {}  # 노드별 실행 횟수
    result = None

    # 스트리밍으로 실행하여 각 노드별 시간 추적
    result = None
    node_inputs = {}  # 노드별 입력 파라미터 저장

    async for event in graph.astream(state):
        current_time = time.time()
        for node_name, node_output in event.items():
            # LangGraph는 각 노드 실행 시마다 이벤트 발생
            if node_name not in node_start_times:
                # 첫 실행: 시작 시간 기록
                node_start_times[node_name] = current_time
                node_execution_count[node_name] = 1

                # 노드 입력 파라미터 로깅
                input_data = {}
                if isinstance(state, dict):
                    input_data = {k: v for k, v in state.items() if not k.startswith("_")}
                elif hasattr(state, "__dict__"):
                    input_data = {
                        k: str(v)
                        if not isinstance(v, (str, int, float, bool, list, dict, type(None)))
                        else v
                        for k, v in state.__dict__.items()
                        if not k.startswith("_")
                    }

                node_inputs[node_name] = input_data

                log_json(
                    "node_start",
                    {
                        "node_name": node_name,
                        "input_state": input_data,
                    },
                    current_time,
                )

                logger.info(f"  → {node_name} 시작")
            else:
                # 이전 실행 완료: 경과 시간 계산 및 누적
                elapsed = current_time - node_start_times[node_name]
                if node_name not in node_times:
                    node_times[node_name] = elapsed
                else:
                    node_times[node_name] += elapsed
                node_execution_count[node_name] = node_execution_count.get(node_name, 0) + 1

                # 노드 출력 파라미터 로깅
                output_data = {}
                if isinstance(node_output, dict):
                    output_data = {
                        k: str(v)
                        if not isinstance(v, (str, int, float, bool, list, dict, type(None)))
                        else v
                        for k, v in node_output.items()
                        if not k.startswith("_")
                    }
                elif hasattr(node_output, "__dict__"):
                    output_data = {
                        k: str(v)
                        if not isinstance(v, (str, int, float, bool, list, dict, type(None)))
                        else v
                        for k, v in node_output.__dict__.items()
                        if not k.startswith("_")
                    }

                log_json(
                    "node_complete",
                    {
                        "node_name": node_name,
                        "elapsed_seconds": elapsed,
                        "cumulative_seconds": node_times[node_name],
                        "execution_count": node_execution_count[node_name],
                        "input_state": node_inputs.get(node_name, {}),
                        "output_state": output_data,
                    },
                    current_time,
                )

                logger.info(
                    f"  ✅ {node_name} 완료: {elapsed:.3f}초 (누적: {node_times[node_name]:.3f}초, 실행 횟수: {node_execution_count[node_name]})"
                )
                # 다음 실행을 위한 시작 시간 업데이트
                node_start_times[node_name] = current_time

            # 최종 state 저장 및 업데이트 (state 병합)
            if isinstance(node_output, dict):
                if result is None:
                    result = node_output
                else:
                    # state 병합 (LangGraph는 partial updates를 반환)
                    result.update(node_output)

    exec_time = time.time() - exec_start

    # result가 없으면 최종 state 가져오기
    if result is None:
        logger.warning("최종 state를 가져오기 위해 ainvoke 호출")
        invoke_start = time.time()
        result = await graph.ainvoke(state)
        invoke_time = time.time() - invoke_start
        log_json(
            "graph_invoke",
            {
                "elapsed_seconds": invoke_time,
            },
            time.time(),
        )

    # execution_results 상세 로깅 (API 호출 정보)
    execution_results = result.get("execution_results", [])
    for er in execution_results:
        er_data = {
            "step": er.step if hasattr(er, "step") else None,
            "endpoint": er.endpoint if hasattr(er, "endpoint") else None,
            "success": er.success if hasattr(er, "success") else None,
            "error": er.error if hasattr(er, "error") else None,
        }

        # API 응답 데이터 로깅 (요약)
        if hasattr(er, "data") and er.data:
            data_summary: dict = {}
            if isinstance(er.data, dict):
                # 응답 구조 요약
                if "candidates" in er.data:
                    candidates_count: int = len(er.data["candidates"])
                    data_summary["candidates_count"] = candidates_count
                    if er.data["candidates"]:
                        data_summary["first_candidate"] = {
                            "chunk_id": er.data["candidates"][0].get("chunk_id", ""),
                            "file_path": er.data["candidates"][0].get("file_path", ""),
                            "symbol_name": er.data["candidates"][0].get("symbol_name", ""),
                        }
                if "chunks" in er.data:
                    data_summary["chunks_count"] = len(er.data["chunks"])
                if "neighbors" in er.data:
                    data_summary["neighbors_count"] = len(er.data["neighbors"])
                response_keys: list = list(er.data.keys())
                data_summary["response_keys"] = response_keys
            er_data["response_summary"] = data_summary

        log_json("api_call", er_data, time.time())

    # 최종 결과 로깅
    final_result_data = {
        "execution_steps": len(execution_results),
        "total_chunks": len(result.get("accumulated_chunks", [])),
        "answer_length": len(result.get("answer", "")),
        "has_error": bool(result.get("error")),
    }

    log_json(
        "graph_complete",
        {
            "execution_time_seconds": exec_time,
            "result_summary": final_result_data,
            "node_times": dict(node_times),
            "node_execution_counts": node_execution_count,
        },
        time.time(),
    )

    logger.info(
        f"✅ 그래프 실행 완료: {len(result.get('execution_results', []))}단계, {len(result.get('accumulated_chunks', []))}개 청크"
    )
    logger.info(f"⏱️  그래프 실행 시간: {exec_time:.3f}초")

    # 결과 출력
    total_time = time.time() - total_start
    print("=" * 80)
    print("결과:")
    print("=" * 80)
    print(f"실행 단계: {len(result.get('execution_results', []))}")
    print(f"총 청크: {len(result.get('accumulated_chunks', []))}")
    print(f"답변 길이: {len(result.get('answer', ''))} chars")

    print("\n" + "-" * 80)
    print("⏱️  시간 측정:")
    print("-" * 80)
    print(f"  그래프 초기화: {init_time:.3f}초")
    print(f"  그래프 실행: {exec_time:.3f}초")
    if node_times:
        print("\n  노드별 실행 시간:")
        for node_name, elapsed in sorted(
            node_times.items(), key=lambda x: x[1] if isinstance(x[1], float) else 0, reverse=True
        ):
            if isinstance(elapsed, float):
                count = node_execution_count.get(node_name, 1)
                avg_time = elapsed / count if count > 0 else elapsed
                print(
                    f"    - {node_name}: {elapsed:.3f}초 (평균: {avg_time:.3f}초, 실행 횟수: {count})"
                )
    print(f"  총 소요 시간: {total_time:.3f}초")
    print("-" * 80)

    # 최종 요약 로깅
    log_json(
        "test_complete",
        {
            "total_time_seconds": total_time,
            "init_time_seconds": init_time,
            "exec_time_seconds": exec_time,
            "node_times": dict(node_times),
            "node_execution_counts": node_execution_count,
            "execution_steps": len(result.get("execution_results", [])),
            "total_chunks": len(result.get("accumulated_chunks", [])),
            "answer_length": len(result.get("answer", "")),
        },
        time.time(),
    )

    if result.get("error"):
        log_json(
            "error",
            {
                "error_message": str(result["error"]),
            },
            time.time(),
        )
        print(f"에러: {result['error']}")

    print("\n" + "=" * 80)
    print("답변:")
    print("=" * 80)
    answer = result.get("answer", "")
    if answer:
        print(answer)
    else:
        print("(답변이 생성되지 않았습니다)")
    print("=" * 80)

    # TOON 형식으로 결과 출력 (선택)
    if USE_TOON:
        print("\n" + "=" * 80)
        print("TOON 형식 결과:")
        print("=" * 80)
        chunks = result.get("accumulated_chunks", [])

        result_data = {
            "query": result.get("query", ""),
            "execution_steps": len(result.get("execution_results", [])),
            "total_chunks": len(chunks),
            "chunks": [
                {
                    "chunk_id": c.chunk_id if hasattr(c, "chunk_id") else c.get("chunk_id", ""),
                    "file_path": c.file_path if hasattr(c, "file_path") else c.get("file_path", ""),
                    "line_start": c.line_start
                    if hasattr(c, "line_start")
                    else c.get("line_start", 0),
                    "line_end": c.line_end if hasattr(c, "line_end") else c.get("line_end", 0),
                    "score": c.score if hasattr(c, "score") else c.get("score", 0),
                }
                for c in chunks[:5]
            ],
        }
        toon_output = encode_to_toon(result_data)
        print(toon_output)
        stats = get_token_stats(result_data)
        print(
            f"\n토큰 통계: JSON {stats['json_tokens']} → TOON {stats['toon_tokens']} (절약: {stats['saved_percent']}%)"
        )
        print("=" * 80)

    # 로그 파일 닫기
    json_log_file.close()
    logger.info(f"로그 저장 완료: {LOG_FILE}, {JSON_LOG_FILE}")


if __name__ == "__main__":
    try:
        asyncio.run(test())
    except Exception as e:
        log_json(
            "test_error",
            {
                "error": str(e),
                "error_type": type(e).__name__,
            },
            time.time(),
        )
        json_log_file.close()
        raise
