"""Plan Executor Node - 실행 계획을 순차적으로 실행"""

import logging
import os
import re
from typing import Any, Dict, List

from semantica_copilot.agent.intent import EndpointType
from semantica_copilot.agent.state import AgentState, ExecutionResult, RetrievedChunk
from semantica_copilot.tools.codegraph import CodeGraphAPI

logger = logging.getLogger(__name__)


class VariableResolver:
    """Variable Substitution 처리"""

    def __init__(self, state: AgentState, execution_context: Dict[str, Any]):
        self.state = state
        self.context = execution_context

    def resolve(self, value: Any) -> Any:
        """값에서 ${} 변수를 실제 값으로 치환"""
        if isinstance(value, str):
            return self._resolve_string(value)
        elif isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        elif isinstance(value, list):
            # 리스트 항목을 resolve하되, nested list를 flatten
            result = []
            for item in value:
                resolved = self.resolve(item)
                # 단일 변수가 리스트를 반환하면 flatten
                if isinstance(resolved, list):
                    result.extend(resolved)
                else:
                    result.append(resolved)
            return result
        else:
            return value

    def _resolve_string(self, value: str) -> Any:
        """문자열에서 ${} 패턴 찾아서 치환"""
        # ${...} 패턴 찾기
        pattern = r"\$\{([^}]+)\}"
        matches = re.findall(pattern, value)

        if not matches:
            return value

        # 단일 변수 참조인 경우 (예: "${candidates[0].chunk_id}")
        if len(matches) == 1 and value == f"${{{matches[0]}}}":
            return self._evaluate(matches[0])

        # 문자열 내 변수 치환 (예: "test ${query}")
        result = value
        for match in matches:
            resolved = self._evaluate(match)
            result = result.replace(f"${{{match}}}", str(resolved))
        return result

    def _evaluate(self, expression: str) -> Any:
        """표현식 평가"""
        # 기본 변수
        if expression == "query":
            return self.state.query
        elif expression == "location_ctx":
            return self.state.location_ctx
        elif expression == "repo_ids":
            return self.state.repo_ids

        # 컨텍스트 변수 (이전 단계 결과)
        # 예: candidates[0].chunk_id, candidates[0:3].chunk_id
        if "candidates" in expression:
            return self._evaluate_candidates(expression)
        elif "neighbors" in expression:
            return self._evaluate_neighbors(expression)
        elif "chunks" in expression:
            return self._evaluate_chunks(expression)
        elif "best_candidate" in expression:
            return self._evaluate_best_candidate(expression)

        # 평가 실패
        logger.warning(f"Cannot evaluate expression: {expression}")
        return None

    def _evaluate_candidates(self, expression: str) -> Any:
        """candidates 관련 표현식 평가"""
        candidates = self.context.get("candidates", [])
        if not candidates:
            return []

        # candidates[0].chunk_id
        match = re.match(r"candidates\[(\d+)\]\.(\w+)", expression)
        if match:
            idx = int(match.group(1))
            field = match.group(2)
            if idx < len(candidates):
                return candidates[idx].get(field)
            return None

        # candidates[0:3].chunk_id
        match = re.match(r"candidates\[(\d+):(\d+)\]\.(\w+)", expression)
        if match:
            start = int(match.group(1))
            end = int(match.group(2))
            field = match.group(3)
            return [c.get(field) for c in candidates[start:end] if c.get(field)]

        return []

    def _evaluate_neighbors(self, expression: str) -> Any:
        """neighbors 관련 표현식 평가"""
        neighbors = self.context.get("neighbors", [])
        if not neighbors:
            return []

        # neighbors[0:5].chunk_id
        match = re.match(r"neighbors\[(\d+):(\d+)\]\.(\w+)", expression)
        if match:
            start = int(match.group(1))
            end = int(match.group(2))
            field = match.group(3)
            # neighbors는 GraphNeighbor인데 chunk_id가 없을 수 있음
            # node_id로부터 chunk를 찾아야 함
            result = []
            for n in neighbors[start:end]:
                if field == "chunk_id":
                    # node_id로부터 chunk_id를 찾아야 하지만, 일단 node_id 반환
                    # 실제로는 API 호출로 chunk를 찾아야 함
                    result.append(n.get("node_id"))
                else:
                    result.append(n.get(field))
            return result

        return []

    def _evaluate_chunks(self, expression: str) -> Any:
        """chunks 관련 표현식 평가"""
        chunks = self.context.get("chunks", [])
        if not chunks:
            return []

        # chunks[0:5].chunk_id
        match = re.match(r"chunks\[(\d+):(\d+)\]\.(\w+)", expression)
        if match:
            start = int(match.group(1))
            end = int(match.group(2))
            field = match.group(3)
            return [c.get(field) for c in chunks[start:end] if c.get(field)]

        return []

    def _evaluate_best_candidate(self, expression: str) -> Any:
        """best_candidate 관련 표현식 평가"""
        candidates = self.context.get("candidates", [])
        if not candidates:
            return None

        # best_candidate.node_id
        match = re.match(r"best_candidate\.(\w+)", expression)
        if match:
            field = match.group(1)
            # 첫 번째 후보가 best (이미 점수순 정렬되어 있다고 가정)
            return candidates[0].get(field)

        return None


async def plan_executor_node(state: AgentState) -> Dict[str, Any]:
    """
    Plan Executor Node

    ExecutionPlan의 각 단계를 순차적으로 실행하고 결과를 누적
    """
    logger.info("\n[Plan Executor] 시작")

    if not state.execution_plan:
        logger.error("[Plan Executor] 실행 계획이 없습니다")
        return {"error": "No execution plan"}

    # Codegraph API 클라이언트
    codegraph_url = os.getenv("CODEGRAPH_BASE_URL", "http://localhost:8000")
    api = CodeGraphAPI(base_url=codegraph_url)

    # 실행 컨텍스트 (이전 단계 결과 누적)
    execution_context: Dict[str, Any] = {
        "candidates": [],
        "neighbors": [],
        "chunks": [],
    }

    execution_results: List[ExecutionResult] = []
    accumulated_chunks: List[RetrievedChunk] = []

    try:
        for plan_step in state.execution_plan.plan:
            logger.info(f"\n[Step {plan_step.step}] {plan_step.endpoint.value}")
            if plan_step.description:
                logger.info(f"목적: {plan_step.description}")

            # Variable Substitution
            resolver = VariableResolver(state, execution_context)
            resolved_params = resolver.resolve(plan_step.params)

            logger.info(f"변수 치환 전: {plan_step.params}")
            logger.info(f"변수 치환 후: {resolved_params}")

            # Endpoint 호출
            logger.info("API 호출 중...")
            result = await _execute_endpoint(
                api=api,
                endpoint=plan_step.endpoint,
                params=resolved_params,
                repo_ids=state.repo_ids,
            )

            if not result["success"]:
                logger.error(f"[실패] {result.get('error')}")
                execution_results.append(
                    ExecutionResult(
                        step=plan_step.step,
                        endpoint=plan_step.endpoint.value,
                        success=False,
                        error=result.get("error"),
                    )
                )
                continue

            # 결과 저장
            execution_results.append(
                ExecutionResult(
                    step=plan_step.step,
                    endpoint=plan_step.endpoint.value,
                    success=True,
                    data=result["data"],
                )
            )

            # 컨텍스트 업데이트
            _update_context(execution_context, plan_step.endpoint, result["data"])

            # 청크 누적
            chunks = _extract_chunks(result["data"])
            accumulated_chunks.extend(chunks)

            # 스킵 여부 확인
            if result.get("skipped"):
                logger.info("[스킵됨] 필수 파라미터 없음")
            else:
                logger.info("[성공]")
            logger.info(f"이번 단계 청크: {len(chunks)}개")
            logger.info(f"누적 청크: {len(accumulated_chunks)}개")

        logger.info("\n[Plan Executor] 완료")
        logger.info(f"총 실행 단계: {len(execution_results)}")
        logger.info(f"최종 청크 수: {len(accumulated_chunks)}\n")

        return {
            "execution_results": execution_results,
            "accumulated_chunks": accumulated_chunks,
        }

    except Exception as e:
        logger.error(f"\n[Plan Executor] 실패: {e}", exc_info=True)
        return {"error": f"Plan execution failed: {str(e)}"}


async def _execute_endpoint(
    api: CodeGraphAPI,
    endpoint: EndpointType,
    params: Dict[str, Any],
    repo_ids: List[str] | None,
) -> Dict[str, Any]:
    """Endpoint 호출"""
    try:
        # repo_id 설정
        if not params.get("repo_id") and repo_ids:
            params["repo_id"] = repo_ids[0]

        # Endpoint별 처리
        if endpoint == EndpointType.SEARCH:
            result = await api.hybrid_search(
                query=params["query"],
                repo_id=params.get("repo_id"),
                k=params.get("k", 10),
                location_ctx=params.get("location_ctx"),
            )
            return {"success": True, "data": result}

        elif endpoint == EndpointType.CHUNKS:
            chunk_ids = params.get("chunk_ids", [])
            if not chunk_ids:
                return {"success": True, "data": {"chunks": []}}

            result = await api.fetch_chunks(
                chunk_ids=chunk_ids,
                include_source=params.get("include_source", True),
                include_neighbors=params.get("include_neighbors", False),
            )
            return {"success": True, "data": result}

        elif endpoint == EndpointType.GRAPH:
            node_id = params.get("node_id")
            chunk_id = params.get("chunk_id")

            # Validation: node_id 또는 chunk_id 중 하나는 필수
            if not node_id and not chunk_id:
                logger.info("[GRAPH] node_id와 chunk_id가 모두 없음, 스킵")
                return {
                    "success": True,
                    "data": {"neighbors": []},
                    "skipped": True,
                }

            result = await api.expand_graph(
                node_id=node_id,
                chunk_id=chunk_id,
                max_depth=params.get("max_depth", 1),
                k=params.get("k", 10),
                edge_types=params.get("edge_types"),
            )
            return {"success": True, "data": result}

        elif endpoint == EndpointType.SYMBOLS:
            result = await api.search_symbols(
                symbol_query=params["symbol_query"],
                k=params.get("k", 10),
            )
            return {"success": True, "data": result}

        elif endpoint == EndpointType.EXPLAIN:
            result = await api.explain_candidate(
                candidate_id=params["candidate_id"],
                chunk_id=params.get("chunk_id"),
                repo_id=params.get("repo_id"),
            )
            return {"success": True, "data": result}

        else:
            return {"success": False, "error": f"Unknown endpoint: {endpoint}"}

    except Exception as e:
        logger.error(f"Endpoint call failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


def _update_context(context: Dict[str, Any], endpoint: EndpointType, data: Dict[str, Any]):
    """실행 컨텍스트 업데이트"""
    if endpoint == EndpointType.SEARCH:
        # candidates 저장
        candidates = data.get("candidates", [])
        context["candidates"] = [
            {
                "chunk_id": c.get("chunk_id"),
                "node_id": c.get("node_id"),
                "file_path": c.get("file_path"),
                "span": c.get("span"),
                "score": c.get("final_score", 0),
            }
            for c in candidates
        ]

    elif endpoint == EndpointType.GRAPH:
        # neighbors 저장
        neighbors = data.get("neighbors", [])
        context["neighbors"] = [
            {
                "node_id": n.get("node_id"),
                "file_path": n.get("file_path"),
                "span": n.get("span"),
                "depth": n.get("depth"),
            }
            for n in neighbors
        ]

    elif endpoint == EndpointType.CHUNKS:
        # chunks 저장
        chunks = data.get("chunks", [])
        context["chunks"] = [
            {
                "chunk_id": c.get("chunk_id"),
                "file_path": c.get("file_path"),
                "span": c.get("span"),
                "content": c.get("content"),
            }
            for c in chunks
        ]

    elif endpoint == EndpointType.SYMBOLS:
        # symbols도 candidates로 저장
        candidates = data.get("candidates", [])
        context["candidates"] = [
            {
                "chunk_id": None,  # symbols는 chunk_id가 없을 수 있음
                "node_id": None,
                "file_path": c.get("file_path"),
                "span": c.get("span"),
                "score": c.get("match_score", 0),
            }
            for c in candidates
        ]


def _extract_chunks(data: Dict[str, Any]) -> List[RetrievedChunk]:
    """API 응답에서 RetrievedChunk 추출"""
    chunks = []

    # /hybrid/chunks 응답
    if "chunks" in data:
        for c in data["chunks"]:
            chunks.append(
                RetrievedChunk(
                    chunk_id=c.get("chunk_id", ""),
                    file_path=c.get("file_path", ""),
                    line_start=c.get("span", [0, 0])[0],
                    line_end=c.get("span", [0, 0])[1],
                    text=c.get("content", ""),
                    score=1.0,  # chunks는 이미 선택된 것이므로 1.0
                    metadata=c.get("metadata", {}),
                )
            )

    # /hybrid/search 응답
    elif "candidates" in data:
        for c in data["candidates"]:
            chunks.append(
                RetrievedChunk(
                    chunk_id=c.get("chunk_id", ""),
                    file_path=c.get("file_path", ""),
                    line_start=c.get("span", [0, 0])[0],
                    line_end=c.get("span", [0, 0])[1],
                    text=c.get("snippet", ""),  # snippet만 있음
                    score=c.get("final_score", 0),
                    metadata={"scores": c.get("scores", {})},
                )
            )

    return chunks
