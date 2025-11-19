"""Agent State 정의"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SearchStrategy(str, Enum):
    """검색 전략"""

    HYBRID = "hybrid"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    GRAPH = "graph"


class SearchResult(BaseModel):
    """검색 결과"""

    repo_id: str
    chunk_id: str
    file_path: str
    line_start: int
    line_end: int
    text: str
    score: float
    scores: Dict[str, Any]  # lexical, semantic, graph, fuzzy (nested dict 허용)


class RetrievedContext(BaseModel):
    """
    검색 결과 누적 컨테이너

    Note:
    - dedupe_keys는 list로 관리 (LangGraph 체크포인트 직렬화 안전)
    - 내부적으로 set()으로 캐스팅하여 중복 체크
    - MVP: 매번 set() 생성해도 성능 이슈 없음
    """

    results: List[SearchResult] = Field(default_factory=list)
    dedupe_keys: List[str] = Field(default_factory=list)

    @property
    def _dedupe_set(self) -> set:
        """중복 체크용 set (매번 생성, 추후 최적화 가능)"""
        return set(self.dedupe_keys)

    def add_result(self, result: SearchResult) -> bool:
        """
        결과 추가 (중복 제거)

        Returns:
            True if added, False if duplicate
        """
        key = f"{result.repo_id}:{result.file_path}:{result.line_start}"
        if key in self._dedupe_set:
            return False
        self.dedupe_keys.append(key)
        self.results.append(result)
        return True

    def get_top_k(self, k: int) -> List[SearchResult]:
        """상위 k개 결과 (점수순 정렬)"""
        return sorted(self.results, key=lambda x: x.score, reverse=True)[:k]


class CodeSearchIntent(BaseModel):
    """검색 의도"""

    entities: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    graph_depth: int = 1
    limit: int = 20
    step: int = 0
    strategy: SearchStrategy = SearchStrategy.HYBRID
    edge_types: Optional[List[str]] = None  # "calls", "defines" 등


class AgentState(BaseModel):
    """
    LangGraph State (JSON 직렬화 안전)

    Note:
    - enough_context 필드 제거: routing에서 직접 판단
    - 상태 변경은 노드, 판단은 routing이 책임
    """

    # 입력
    query: str
    repo_ids: Optional[List[str]] = None

    # 계획
    plan: Optional[Dict] = None

    # 검색
    search_intents: List[CodeSearchIntent] = Field(default_factory=list)
    accumulated_context: RetrievedContext = Field(default_factory=RetrievedContext)

    # 제어
    search_steps: int = 0
    max_search_steps: int = 3

    # 출력
    answer: Optional[str] = None

    # 에러 핸들링
    error: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)
