"""FastAPI 서버"""

import logging
from typing import List, Optional

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
    repo_ids: Optional[List[str]] = None


class ChatResponse(BaseModel):
    """채팅 응답"""

    answer: str
    search_steps: int
    total_results: int
    error: Optional[str] = None


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "Semantica Copilot",
        "version": "0.1.0",
        "phase": "1 (LangGraph 기본)",
    }


@app.get("/health")
async def health():
    """헬스 체크"""
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    채팅 엔드포인트

    Phase 1: LangGraph 기본 플로우
    - intent_plan → run_search → generate_answer
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
        final_state = await graph.ainvoke(initial_state)

        # 응답 생성
        response = ChatResponse(
            answer=final_state.get("answer", "답변 생성 실패"),
            search_steps=final_state.get("search_steps", 0),
            total_results=len(final_state.get("accumulated_context", {}).get("results", [])),
            error=final_state.get("error"),
        )

        logger.info(
            f"Chat response: steps={response.search_steps}, results={response.total_results}"
        )

        return response

    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
