"""FastAPI 서버"""

import logging
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from semantica_copilot.agent.graph import get_graph
from semantica_copilot.agent.state import AgentState

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# FastAPI 앱
app = FastAPI(
    title="Semantica Copilot",
    description="LangGraph 기반 코드 이해 에이전트",
    version="0.1.0",
)


# Request/Response 스키마
class ChatRequest(BaseModel):
    """채팅 요청"""

    query: str
    repo_ids: Optional[list[str]] = None


class ChatResponse(BaseModel):
    """채팅 응답 (Intent-based Router)"""

    answer: str
    execution_steps: int  # 실행된 단계 수
    total_chunks: int  # 수집된 청크 수
    intent: Optional[str] = None  # 분류된 Intent
    error: Optional[str] = None


@app.get("/")
async def root() -> dict[str, str]:
    """루트 엔드포인트"""
    return {
        "service": "Semantica Copilot",
        "version": "0.2.0",
        "architecture": "Intent-based Router",
        "description": "LangGraph 기반 코드 이해 에이전트 (Intent Router + Plan Executor)",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """헬스 체크"""
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    채팅 엔드포인트

    Intent-based Router Architecture:
    - intent_router → plan_executor → answer_generator
    """
    logger.info(f"Chat request: query={request.query}, repos={request.repo_ids}")

    try:
        # 초기 state 생성
        initial_state = AgentState(
            query=request.query,
            repo_ids=request.repo_ids,
        )

        # 그래프 실행
        graph = get_graph()
        final_state: dict[str, Any] = await graph.ainvoke(initial_state)

        # Intent 추출
        intent_str = None
        if execution_plan := final_state.get("execution_plan"):
            intent_str = execution_plan.intent.value if hasattr(execution_plan, "intent") else None

        # 응답 생성
        response = ChatResponse(
            answer=final_state.get("answer", "답변 생성 실패"),
            execution_steps=len(final_state.get("execution_results", [])),
            total_chunks=len(final_state.get("accumulated_chunks", [])),
            intent=intent_str,
            error=final_state.get("error"),
        )

        logger.info(
            f"Chat response: intent={response.intent}, steps={response.execution_steps}, chunks={response.total_chunks}"
        )

        return response

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
