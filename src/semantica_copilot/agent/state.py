"""Agent State 정의"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from semantica_copilot.agent.intent import ExecutionPlan


class ExecutionResult(BaseModel):
    """Endpoint 실행 결과"""

    step: int
    endpoint: str
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class RetrievedChunk(BaseModel):
    """검색된 청크"""

    chunk_id: str
    file_path: str
    line_start: int
    line_end: int
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    """
    LangGraph State (Intent-based Router Architecture)

    플로우:
    1. intent_router: query → ExecutionPlan
    2. plan_executor: ExecutionPlan → execution_results
    3. generate_answer: execution_results → answer
    """

    # 입력
    query: str
    repo_ids: Optional[list[str]] = None
    location_ctx: Optional[dict[str, Any]] = None  # 현재 위치 컨텍스트

    # Intent & Plan
    execution_plan: Optional[ExecutionPlan] = None

    # 실행 결과
    execution_results: list[ExecutionResult] = Field(default_factory=list)
    accumulated_chunks: list[RetrievedChunk] = Field(default_factory=list)

    # 출력
    answer: Optional[str] = None

    # 에러 핸들링
    error: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
