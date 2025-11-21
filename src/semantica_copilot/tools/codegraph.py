"""semantica-codegraph 통합 클라이언트"""

import logging
from enum import Enum
from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ===== OLD ARCHITECTURE (Deprecated) =====
# Backward compatibility를 위해 남겨둠


class SearchStrategy(str, Enum):
    """검색 전략 (Deprecated)"""

    HYBRID = "hybrid"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    GRAPH = "graph"


class SearchResult(BaseModel):
    """검색 결과 (Deprecated)"""

    repo_id: str
    chunk_id: str
    file_path: str
    line_start: int
    line_end: int
    text: str
    score: float
    scores: dict[str, Any]


class CodeSearchIntent(BaseModel):
    """검색 의도 (Deprecated)"""

    entities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    graph_depth: int = 1
    limit: int = 20
    step: int = 0
    strategy: SearchStrategy = SearchStrategy.HYBRID
    edge_types: Optional[list[str]] = None


class BackendType(Enum):
    """백엔드 타입"""

    HTTP = "http"
    MCP = "mcp"
    DIRECT = "direct"


class CodeGraphClient:
    """
    semantica-codegraph 통합 클라이언트

    연동 방식을 추상화하여 에이전트 코드와 분리
    """

    def __init__(
        self,
        backend: BackendType = BackendType.HTTP,
        base_url: str = "http://localhost:8000",
    ):
        self.backend = backend
        self.base_url = base_url
        self._init_backend()

    def _init_backend(self):
        """백엔드 초기화"""
        if self.backend == BackendType.HTTP:
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
            )
        elif self.backend == BackendType.MCP:
            raise NotImplementedError("MCP backend not implemented yet")
        elif self.backend == BackendType.DIRECT:
            raise NotImplementedError("DIRECT backend not implemented yet")

    async def aclose(self):
        """종료 시 호출"""
        if hasattr(self, "client") and isinstance(self.client, httpx.AsyncClient):
            await self.client.aclose()

    async def search_with_intent(
        self,
        intent: CodeSearchIntent,
        repo_ids: Optional[list[str]] = None,
    ) -> list[SearchResult]:
        """
        Intent 기반 검색

        Intent의 entities, keywords, strategy 등을
        실제 검색 파라미터로 변환

        Note: Enum은 자동으로 .value 변환
        """
        # Query 구성
        query_parts = []
        if intent.entities:
            query_parts.extend(intent.entities)
        if intent.keywords:
            query_parts.extend(intent.keywords)

        query = " ".join(query_parts) if query_parts else ""

        if not query:
            logger.warning("Empty query in search_with_intent")
            return []

        # 전략별 파라미터 매핑
        search_params: dict = {
            "query": query,
            "repo_ids": repo_ids,
            "limit": intent.limit,
        }

        # Strategy 적용 (Enum 비교)
        if intent.strategy == SearchStrategy.GRAPH:
            # 그래프 검색 강조
            search_params["weights"] = {
                "lexical": 0.1,
                "semantic": 0.2,
                "graph": 0.6,
                "fuzzy": 0.1,
            }
        elif intent.strategy == SearchStrategy.SEMANTIC:
            search_params["weights"] = {
                "lexical": 0.1,
                "semantic": 0.8,
                "graph": 0.1,
                "fuzzy": 0.0,
            }
        # HYBRID는 기본값 사용

        # Graph 옵션
        if intent.graph_depth > 1:
            search_params["graph_depth"] = intent.graph_depth
        if intent.edge_types:
            search_params["edge_types"] = intent.edge_types

        # ⚠️ 중요: Enum을 .value로 변환하여 전달
        search_params["strategy"] = intent.strategy.value

        return await self.search_code(**search_params)

    async def search_code(
        self,
        query: str,
        repo_ids: Optional[list[str]] = None,
        limit: int = 20,
        strategy: str = "hybrid",  # ⚠️ str로 받음 (Enum.value)
        weights: Optional[dict[str, float]] = None,
        graph_depth: int = 1,
        edge_types: Optional[list[str]] = None,
        **kwargs,
    ) -> list[SearchResult]:
        """
        하이브리드 검색 (파라미터 확장)

        Args:
            strategy: 검색 전략 문자열 ("hybrid", "graph", "semantic")
                      ⚠️ Enum이 아닌 str로 받음 (HTTP 직렬화 안전)
        """
        if self.backend == BackendType.HTTP:
            return await self._search_http(
                query, repo_ids, limit, strategy, weights, graph_depth, edge_types, **kwargs
            )
        else:
            raise NotImplementedError(f"Backend {self.backend} not implemented")

    async def _search_http(
        self,
        query: str,
        repo_ids: Optional[list[str]],
        limit: int,
        strategy: str,
        weights: Optional[dict[str, float]],
        graph_depth: int,
        edge_types: Optional[list[str]],
        **kwargs,
    ) -> list[SearchResult]:
        """
        HTTP API 호출

        Note: 새로운 /hybrid/search API 사용
        - 경로: POST /hybrid/search
        - location_ctx에 repo_id 포함 (여러 repo면 반복 호출)
        - k (limit 대신)
        - 응답: candidates → SearchResult 변환
        - span → line_start/line_end 변환
        - scores → scores 변환
        - snippet은 text로 사용 (전체 내용은 /hybrid/chunks로)
        """
        if not repo_ids:
            logger.warning("No repo_ids provided")
            return []

        all_results = []

        # 각 repo에 대해 반복 검색
        for repo_id in repo_ids:
            try:
                # 새로운 /hybrid/search API 사용
                payload = {
                    "query": query,
                    "k": limit,
                    "location_ctx": {
                        "repo_id": repo_id,
                        "file_path": "",
                        "line": 0,
                        "column": 0,
                    },
                }

                # weights가 있으면 추가
                if weights:
                    payload["backend_hints"] = [
                        backend for backend, enabled in weights.items() if enabled > 0
                    ]

                response = await self.client.post(
                    "/hybrid/search",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                # 응답 변환 (hybrid API → copilot 형식)
                for candidate in data.get("candidates", []):
                    # scores는 dict 형태로 전달됨
                    candidate_scores = candidate.get("scores", {})
                    result = SearchResult(
                        repo_id=repo_id,
                        chunk_id=candidate["chunk_id"],
                        file_path=candidate["file_path"],
                        line_start=candidate["span"][0],  # span → line_start
                        line_end=candidate["span"][2],  # span → line_end
                        text=candidate.get("snippet", ""),  # snippet을 text로 사용
                        score=candidate["final_score"],
                        scores={
                            "lexical": candidate_scores.get("lexical"),
                            "semantic": candidate_scores.get("semantic"),
                            "graph": candidate_scores.get("graph"),
                            "fuzzy": candidate_scores.get("fuzzy"),
                        },
                    )
                    all_results.append(result)

                logger.info(
                    f"Retrieved {len(data.get('candidates', []))} candidates from {repo_id}"
                )

            except httpx.HTTPError as e:
                logger.error(f"HTTP error for repo {repo_id}: {e}")
                # 다른 repo는 계속 시도
                continue
            except Exception as e:
                logger.error(f"Error for repo {repo_id}: {e}")
                continue

        return all_results


class CodeGraphAPI:
    """
    Intent-based Router Architecture용 Codegraph API 클라이언트

    Hybrid API endpoints를 직접 호출:
    - /hybrid/search
    - /hybrid/chunks
    - /hybrid/graph
    - /hybrid/symbols
    - /hybrid/explain
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=30.0,
        )

    async def aclose(self):
        """종료 시 호출"""
        await self.client.aclose()

    async def hybrid_search(
        self,
        query: str,
        repo_id: Optional[str] = None,
        k: int = 10,
        location_ctx: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """/hybrid/search 호출"""
        payload: dict[str, Any] = {
            "query": query,
            "k": k,
        }

        # location_ctx 설정 및 보정
        if location_ctx:
            # API 스펙에 맞게 보정 (누락된 필드 채우기)
            normalized_ctx = {
                "repo_id": location_ctx.get("repo_id", repo_id or ""),
                "file_path": location_ctx.get("file_path", ""),
                "line": location_ctx.get("line", 0),
                "column": location_ctx.get("column", 0),
            }
            # symbol_name은 optional
            if "symbol_name" in location_ctx:
                normalized_ctx["symbol_name"] = location_ctx["symbol_name"]

            payload["location_ctx"] = normalized_ctx
        elif repo_id:
            payload["location_ctx"] = {
                "repo_id": repo_id,
                "file_path": "",
                "line": 0,
                "column": 0,
            }

        try:
            response = await self.client.post("/hybrid/search", json=payload)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"hybrid_search failed: {e}")
            raise

    async def fetch_chunks(
        self,
        chunk_ids: list[str],
        include_source: bool = True,
        include_neighbors: bool = False,
    ) -> dict[str, Any]:
        """/hybrid/chunks 호출"""
        payload = {
            "chunk_ids": chunk_ids,
            "include_source": include_source,
            "include_neighbors": include_neighbors,
        }

        try:
            response = await self.client.post("/hybrid/chunks", json=payload)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"fetch_chunks failed: {e}")
            raise

    async def expand_graph(
        self,
        node_id: Optional[str] = None,
        chunk_id: Optional[str] = None,
        max_depth: int = 1,
        k: int = 10,
        edge_types: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """/hybrid/graph 호출"""
        payload: dict[str, Any] = {
            "max_depth": max_depth,
            "k": k,
        }

        if node_id:
            payload["node_id"] = node_id
        if chunk_id:
            payload["chunk_id"] = chunk_id
        if edge_types:
            payload["edge_types"] = edge_types

        try:
            response = await self.client.post("/hybrid/graph", json=payload)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"expand_graph failed: {e}")
            raise

    async def search_symbols(
        self,
        symbol_query: str,
        k: int = 10,
    ) -> dict[str, Any]:
        """/hybrid/symbols 호출"""
        payload = {
            "symbol_query": symbol_query,
            "k": k,
        }

        try:
            response = await self.client.post("/hybrid/symbols", json=payload)
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"search_symbols failed: {e}")
            raise

    async def explain_candidate(
        self,
        candidate_id: str,
        chunk_id: Optional[str] = None,
        repo_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """/hybrid/explain/{candidate_id} 호출"""
        params = {}
        if chunk_id:
            params["chunk_id"] = chunk_id
        if repo_id:
            params["repo_id"] = repo_id

        try:
            response = await self.client.get(
                f"/hybrid/explain/{candidate_id}",
                params=params,
            )
            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]
        except Exception as e:
            logger.error(f"explain_candidate failed: {e}")
            raise
