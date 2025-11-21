"""Intent 정의 및 Endpoint 매핑 테이블"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CodeIntent(str, Enum):
    """코드 작업 Intent"""

    CODE_QUESTION = "code_question"  # 코드 의미/동작 설명
    SYMBOL_LOOKUP = "symbol_lookup"  # 함수/클래스/심볼 위치 찾기
    NAVIGATION = "navigation"  # 파일/호출 관계 탐색
    REFACTOR = "refactor"  # 리팩터링/리라이팅
    BUG_INVESTIGATION = "bug_investigation"  # 버그/원인 분석
    TEST_DISCOVERY = "test_discovery"  # 테스트 코드 찾기
    CODE_SUMMARY = "code_summary"  # 코드 요약/리뷰


class EndpointType(str, Enum):
    """사용 가능한 Endpoint"""

    SEARCH = "/hybrid/search"  # 하이브리드 검색
    CHUNKS = "/hybrid/chunks"  # 청크 상세 조회
    GRAPH = "/hybrid/graph"  # 그래프 확장
    SYMBOLS = "/hybrid/symbols"  # 심볼 검색
    EXPLAIN = "/hybrid/explain"  # 후보 설명


class PlanStep(BaseModel):
    """실행 계획의 단계"""

    step: int = Field(description="단계 번호 (1부터 시작)")
    endpoint: EndpointType = Field(description="호출할 endpoint")
    params: Dict[str, Any] = Field(description="endpoint 파라미터")
    description: Optional[str] = Field(default=None, description="단계 설명")
    fallback: Optional[Dict[str, str]] = Field(default=None, description="실패 시 fallback 전략")


class ExecutionPlan(BaseModel):
    """LLM이 생성하는 실행 계획"""

    intent: CodeIntent = Field(description="분류된 Intent")
    reason: str = Field(description="Intent 선택 이유")
    plan: List[PlanStep] = Field(description="실행 계획 (순차)")


# Intent → Endpoint 매핑 테이블 (기본 템플릿)
INTENT_ENDPOINT_MAPPING: Dict[CodeIntent, List[Dict[str, Any]]] = {
    CodeIntent.CODE_QUESTION: [
        {
            "endpoint": EndpointType.SEARCH,
            "description": "코드 위치 찾기",
            "params": {
                "query": "${query}",
                "k": 10,
                "location_ctx": "${location_ctx}",
            },
        },
        {
            "endpoint": EndpointType.CHUNKS,
            "description": "전체 코드 로드",
            "params": {
                "chunk_ids": "${candidates[0:3].chunk_id}",
                "include_source": True,
            },
        },
    ],
    CodeIntent.SYMBOL_LOOKUP: [
        {
            "endpoint": EndpointType.SYMBOLS,
            "description": "심볼 검색",
            "params": {
                "symbol_query": "${query}",
                "k": 10,
            },
        },
        {
            "endpoint": EndpointType.CHUNKS,
            "description": "심볼 정의 코드 로드",
            "params": {
                "chunk_ids": "${candidates[0:2].chunk_id}",
                "include_source": True,
            },
        },
    ],
    CodeIntent.NAVIGATION: [
        {
            "endpoint": EndpointType.SEARCH,
            "description": "시작점 찾기",
            "params": {
                "query": "${query}",
                "k": 5,
                "location_ctx": "${location_ctx}",
            },
        },
        {
            "endpoint": EndpointType.GRAPH,
            "description": "호출 관계 확장",
            "params": {
                "node_id": "${candidates[0].node_id}",
                "max_depth": 2,
                "k": 15,
            },
        },
        {
            "endpoint": EndpointType.CHUNKS,
            "description": "연관 코드 로드",
            "params": {
                "chunk_ids": "${candidates[0:5].chunk_id}",
                "include_source": True,
            },
        },
    ],
    CodeIntent.REFACTOR: [
        {
            "endpoint": EndpointType.SEARCH,
            "description": "리팩터링 대상 찾기",
            "params": {
                "query": "${query}",
                "k": 10,
                "location_ctx": "${location_ctx}",
            },
        },
        {
            "endpoint": EndpointType.CHUNKS,
            "description": "대상 코드 로드",
            "params": {
                "chunk_ids": "${candidates[0:2].chunk_id}",
                "include_source": True,
            },
        },
        {
            "endpoint": EndpointType.GRAPH,
            "description": "의존성 확인",
            "params": {
                "node_id": "${best_candidate.node_id}",
                "max_depth": 1,
                "k": 10,
            },
        },
    ],
    CodeIntent.BUG_INVESTIGATION: [
        {
            "endpoint": EndpointType.SEARCH,
            "description": "버그 관련 코드 찾기",
            "params": {
                "query": "${query}",
                "k": 15,
                "location_ctx": "${location_ctx}",
            },
        },
        {
            "endpoint": EndpointType.GRAPH,
            "description": "호출 경로 추적",
            "params": {
                "node_id": "${candidates[0].node_id}",
                "max_depth": 2,
                "k": 20,
                "edge_types": ["calls", "called_by"],
            },
        },
        {
            "endpoint": EndpointType.CHUNKS,
            "description": "관련 코드 로드",
            "params": {
                "chunk_ids": "${candidates[0:10].chunk_id}",
                "include_source": True,
            },
        },
    ],
    CodeIntent.TEST_DISCOVERY: [
        {
            "endpoint": EndpointType.GRAPH,
            "description": "테스트 관계 찾기",
            "params": {
                "node_id": "${node_id}",
                "max_depth": 2,
                "k": 10,
                "edge_types": ["tests", "tested_by"],
            },
        },
        {
            "endpoint": EndpointType.SEARCH,
            "description": "테스트 코드 검색",
            "params": {
                "query": "test ${query}",
                "k": 10,
            },
        },
        {
            "endpoint": EndpointType.CHUNKS,
            "description": "테스트 코드 로드",
            "params": {
                "chunk_ids": "${candidates[0:5].chunk_id}",
                "include_source": True,
            },
        },
    ],
    CodeIntent.CODE_SUMMARY: [
        {
            "endpoint": EndpointType.SEARCH,
            "description": "프로젝트 전반/core 파일 후보 찾기",
            "params": {
                "query": "${query}",
                "k": 20,
                "location_ctx": "${location_ctx}",
            },
        },
        {
            "endpoint": EndpointType.CHUNKS,
            "description": "상위 후보들의 전체 내용 읽기",
            "params": {
                "chunk_ids": "${candidates[0:5].chunk_id}",
                "include_source": True,
                "include_neighbors": True,
            },
        },
        {
            "endpoint": EndpointType.GRAPH,
            "description": "중심성/연관성 확인",
            "params": {
                "node_id": "${candidates[0].node_id}",
                "max_depth": 1,
                "k": 20,
            },
        },
    ],
}


def get_default_plan_template(intent: CodeIntent) -> List[Dict[str, Any]]:
    """Intent에 대한 기본 Plan 템플릿 반환"""
    return INTENT_ENDPOINT_MAPPING.get(intent, [])
