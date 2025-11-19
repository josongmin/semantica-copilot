# Semantica Copilot 아키텍처 제안

## 1. 전체 구조

```
semantica-copilot/
├── src/
│   ├── agent/                 # LangGraph 에이전트
│   │   ├── state.py          # State 정의
│   │   ├── graph.py          # 그래프 구성
│   │   ├── nodes/            # 노드별 로직
│   │   │   ├── intent_plan.py
│   │   │   ├── search_plan.py
│   │   │   ├── run_search.py
│   │   │   ├── aggregate_context.py
│   │   │   ├── enough_context.py
│   │   │   └── generate_answer.py
│   │   └── routing.py        # 조건부 엣지 로직
│   ├── tools/                # 외부 도구
│   │   └── codegraph.py      # semantica-codegraph 클라이언트
│   ├── prompts/              # 프롬프트 템플릿
│   │   ├── intent_plan.md
│   │   ├── search_plan.md
│   │   ├── enough_context.md
│   │   └── code_explain.md
│   ├── llm/                  # LLM 추상화
│   │   └── provider.py       # LiteLLM 래퍼
│   ├── memory/               # 대화 메모리
│   │   └── in_memory.py
│   └── schemas/              # I/O 스키마
│       └── io.py
├── apps/
│   └── server/
│       └── main.py           # FastAPI 서버
└── tests/
    ├── test_agent_flow.py
    └── test_tools.py
```

## 2. State 스키마

### 핵심 개선사항
1. **원본 결과 보존**: SearchResult로 codegraph 응답 전체 보존
2. **중복 제거 최적화**: list 기반 dedupe_keys (JSON 직렬화 안전)
3. **에러 핸들링**: error 필드 추가
4. **검색 이력**: search_intents 리스트로 누적
5. **Pydantic 안전성**: mutable default 방지 (Field + default_factory)

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class SearchResult(BaseModel):
    repo_id: str
    chunk_id: str
    file_path: str
    line_start: int
    line_end: int
    text: str
    score: float
    scores: Dict[str, float]  # 상세 점수

class RetrievedContext(BaseModel):
    """
    검색 결과 누적 컨테이너
    
    Note: 
    - dedupe_keys는 list로 관리 (LangGraph 체크포인트 직렬화 안전)
    - 내부적으로 set()으로 캐스팅하여 중복 체크
    - MVP: 매번 set() 생성해도 성능 이슈 없음
    - 최적화 필요시: @property로 캐싱
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

class SearchStrategy(str, Enum):
    """검색 전략"""
    HYBRID = "hybrid"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    GRAPH = "graph"

class CodeSearchIntent(BaseModel):
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
    
    class Config:
        arbitrary_types_allowed = True
```

## 3. 에이전트 플로우

### 노드별 역할

#### IntentPlanNode (LLM)
- **입력**: query
- **출력**: plan, max_search_steps
- **역할**: 작업 분석 및 검색 전략 수립

```python
plan = {
    "task": "code_explanation",
    "needs_search": True,
    "max_search_steps": 3,
    "targets": ["function", "usage", "types"],
    "strategy": "hybrid"
}
```

#### SearchPlanNode (LLM)
- **입력**: query, plan, accumulated_context, search_steps
- **출력**: search_intent
- **역할**: 현재 컨텍스트 기반 다음 검색 생성

```python
# Step 0: 초기 검색
intent = CodeSearchIntent(
    entities=["function_name"],
    keywords=["async", "database"],
    strategy="hybrid",
    limit=20
)

# Step 1: 관계 확장
intent = CodeSearchIntent(
    entities=["caller_function"],
    edge_types=["calls", "uses"],
    graph_depth=2,
    limit=10
)
```

#### RunSearchNode (Tool)
- **입력**: search_intent
- **출력**: new_results
- **역할**: codegraph 호출 및 결과 수집

#### AggregateContextNode (Logic)
- **입력**: accumulated_context, new_results
- **출력**: accumulated_context (업데이트)
- **역할**: 
  - 중복 제거 (file_path:line_start)
  - 점수순 정렬
  - 상위 k개 유지

#### EnoughContextNode (LLM/Heuristic)
- **입력**: query, accumulated_context, plan
- **출력**: state (enough_context 필드는 세팅하지 않음)
- **역할**: 종료 조건 판단 (routing 함수에서만 사용)

```python
# Heuristic 버전 (권장: MVP)
def check_enough_context_heuristic(state: AgentState) -> bool:
    """
    휴리스틱 기반 종료 조건
    
    Note: state.enough_context를 세팅하지 않고,
    routing 함수에서만 이 결과 사용
    """
    # 1. 최대 스텝 도달
    if state.search_steps >= state.max_search_steps:
        return True
    
    # 2. 충분한 결과 수
    if len(state.accumulated_context.results) >= 50:
        return True
    
    # 3. 최상위 결과 점수 (안전하게 get_top_k 사용)
    top_results = state.accumulated_context.get_top_k(1)
    if top_results and top_results[0].score > 0.9:
        return True
    
    return False

# LLM 버전 (Phase 3: 더 정교함)
def check_enough_context_llm(state: AgentState) -> bool:
    prompt = build_enough_context_prompt(state)
    response = llm.invoke(prompt)
    return "YES" in response.upper()
```

#### GenerateAnswerNode (LLM)
- **입력**: query, accumulated_context, plan
- **출력**: answer
- **역할**: 최종 답변 생성

## 4. Tools 설계

### 설계 원칙

**핵심**: LangGraph 노드는 추상화된 도메인 결과만 본다
- HTTP / MCP / Direct Import 모두 `CodeGraphClient` 내부에 숨김
- 노드는 `List[SearchResult]` 같은 도메인 모델만 알면 됨
- 연동 방식 변경 시 agent 코드는 그대로 유지

```python
# src/agent/tools/codegraph.py

from typing import List, Optional, Dict
from enum import Enum
from ..state import CodeSearchIntent, SearchResult

class BackendType(Enum):
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
            import httpx
            self.client = httpx.AsyncClient(base_url=self.base_url)
        elif self.backend == BackendType.MCP:
            from mcp import ClientSession
            self.client = ClientSession()
        elif self.backend == BackendType.DIRECT:
            from src.core.bootstrap import Bootstrap
            self.bootstrap = Bootstrap.from_env()
    
    async def search_code(
        self,
        query: str,
        repo_ids: Optional[List[str]] = None,
        limit: int = 20,
        **kwargs
    ) -> List[SearchResult]:
        """
        하이브리드 검색
        
        Returns:
            도메인 모델 (SearchResult 리스트)
        """
        if self.backend == BackendType.HTTP:
            return await self._search_http(query, repo_ids, limit, **kwargs)
        elif self.backend == BackendType.MCP:
            return await self._search_mcp(query, repo_ids, limit, **kwargs)
        elif self.backend == BackendType.DIRECT:
            return await self._search_direct(query, repo_ids, limit, **kwargs)
    
    async def _search_http(self, query: str, repo_ids, limit, strategy, weights, graph_depth, edge_types, **kwargs):
        """
        HTTP API 호출
        
        Note: 모든 파라미터는 이미 JSON 직렬화 가능한 타입
        (Enum → str 변환 완료)
        """
        response = await self.client.post(
            "/search",
            json={
                "query": query,
                "repo_ids": repo_ids,
                "limit": limit,
                "strategy": strategy,  # ✅ str (이미 .value 변환됨)
                "weights": weights,
                "graph_depth": graph_depth,
                "edge_types": edge_types,
                **kwargs
            }
        )
        data = response.json()
        return [SearchResult(**item) for item in data["results"]]
    
    async def _search_mcp(self, query: str, repo_ids, limit, **kwargs):
        """MCP tool 호출"""
        result = await self.client.call_tool(
            "search_code",
            arguments={
                "query": query,
                "repo_ids": repo_ids,
                "limit": limit,
                **kwargs
            }
        )
        return [SearchResult(**item) for item in result]
    
    async def _search_direct(self, query: str, repo_ids, limit, **kwargs):
        """직접 라이브러리 호출"""
        candidates = self.bootstrap.hybrid_retriever.retrieve(
            repo_id=repo_ids[0] if repo_ids else None,
            query=query,
            k=limit
        )
        return [
            SearchResult(
                repo_id=c.repo_id,
                chunk_id=c.chunk_id,
                file_path=c.file_path,
                line_start=c.span[0],
                line_end=c.span[2],
                text="",  # chunk store에서 가져와야 함
                score=c.features.get("total_score", 0.0),
                scores={
                    "lexical": c.features.get("lexical_score", 0.0),
                    "semantic": c.features.get("semantic_score", 0.0),
                    "graph": c.features.get("graph_score", 0.0),
                    "fuzzy": c.features.get("fuzzy_score", 0.0),
                }
            )
            for c in candidates
        ]
    
    async def find_definition(
        self,
        symbol_name: str,
        repo_ids: Optional[List[str]] = None,
        kind: Optional[str] = None,
    ) -> List[Dict]:
        """심볼 정의 찾기"""
        # 동일한 패턴으로 백엔드별 구현
        ...
    
    async def explore_graph(
        self,
        repo_id: str,
        node_id: str,
        direction: str = "both",
        edge_types: Optional[List[str]] = None,
        depth: int = 1,
    ) -> Dict:
        """그래프 탐색"""
        ...
    
    async def get_context(
        self,
        repo_id: str,
        file_path: str,
        line: int,
        max_tokens: int = 4000,
    ) -> Dict:
        """컨텍스트 패킹"""
        ...
```

### 노드에서 사용 예시

```python
# src/agent/nodes/run_search.py

from ..state import AgentState
from ..tools.codegraph import CodeGraphClient

# 전역 또는 DI로 주입
client = CodeGraphClient(backend=BackendType.HTTP)

async def run_search_node(state: AgentState) -> AgentState:
    """검색 실행 노드"""
    intent = state.search_intents[-1]
    
    # 추상화된 인터페이스만 사용
    results = await client.search_code(
        query=intent.entities[0] if intent.entities else "",
        repo_ids=state.repo_ids,
        limit=intent.limit
    )
    
    # 도메인 모델로 업데이트
    state.accumulated_context.results.extend(results)
    state.search_steps += 1
    
    return state
```

### 연동 옵션 비교

| 방식 | 장점 | 단점 | 사용 시나리오 |
|------|------|------|---------------|
| **HTTP** | 독립 배포, 언어 무관 | 네트워크 오버헤드 | 프로덕션 (마이크로서비스) |
| **MCP** | 표준 프로토콜, IDE 통합 | 복잡도 증가 | Claude Desktop 연동 |
| **Direct** | 빠름, 간단 | 같은 환경 필요 | 로컬 개발, 테스트 |

## 5. LangGraph 구성

```python
from langgraph.graph import StateGraph, END
from .nodes import (
    intent_plan_node,
    search_plan_node,
    run_search_node,
    aggregate_context_node,
    enough_context_node,
    generate_answer_node,
)
from .routing import route_enough_context

def build_agent_graph():
    """에이전트 그래프 구성"""
    graph = StateGraph(AgentState)
    
    # 노드 추가
    graph.add_node("intent_plan", intent_plan_node)
    graph.add_node("search_plan", search_plan_node)
    graph.add_node("run_search", run_search_node)
    graph.add_node("aggregate", aggregate_context_node)
    graph.add_node("check_enough", enough_context_node)
    graph.add_node("generate", generate_answer_node)
    
    # 엣지 설정 (순차)
    graph.set_entry_point("intent_plan")
    graph.add_edge("intent_plan", "search_plan")
    graph.add_edge("search_plan", "run_search")
    graph.add_edge("run_search", "aggregate")
    graph.add_edge("aggregate", "check_enough")  # ⚠️ 중요: 누락하지 말 것
    
    # 조건부 엣지 (루프 or 종료)
    graph.add_conditional_edges(
        "check_enough",
        route_enough_context,
        {
            "continue": "search_plan",  # 더 검색
            "finish": "generate"        # 답변 생성
        }
    )
    
    graph.add_edge("generate", END)
    
    return graph.compile()


# routing.py
def route_enough_context(state: AgentState) -> str:
    """
    종료 조건 라우팅
    
    Note: state.enough_context는 사용하지 않음
    heuristic 함수로 직접 판단
    """
    # 1. 에러 발생 시 종료
    if state.error:
        return "finish"
    
    # 2. 최대 스텝 도달
    if state.search_steps >= state.max_search_steps:
        return "finish"
    
    # 3. 휴리스틱 체크
    if check_enough_context_heuristic(state):
        return "finish"
    
    return "continue"


# 일관성 원칙:
# - state.enough_context 필드는 사용하지 않음 (제거 고려)
# - routing 함수에서만 종료 조건 판단
# - 노드는 상태만 업데이트, 판단은 routing에 위임
```

### 플로우 다이어그램

```
intent_plan
    ↓
search_plan  ←─────────┐
    ↓                  │
run_search             │
    ↓                  │
aggregate              │
    ↓                  │
check_enough          │
    ├─ continue ──────┘
    └─ finish
        ↓
    generate
        ↓
       END
```

## 6. 프롬프트 전략

### Intent Plan

#### Phase 1: 단순 버전 (고정 Plan)
```python
# LLM 없이 고정된 plan 반환
def intent_plan_node(state: AgentState) -> AgentState:
    state.plan = {
        "task": "code_explanation",
        "max_search_steps": 2,
        "targets": ["definition", "usage"],
        "strategy": "hybrid"
    }
    state.max_search_steps = 2
    return state
```

#### Phase 2: LLM 기반 (동적 Plan)
```markdown
사용자 질문: {query}

다음을 분석하시오:
1. 작업 유형: code_explanation
2. 필요한 검색 단계: 2-3
3. 검색 목표: 심볼 정의, 호출 관계, 타입 정보

JSON으로 응답:
{
  "task": "code_explanation",
  "max_search_steps": 2,
  "targets": ["definition", "callers"],
  "strategy": "hybrid"
}
```

**단계적 접근**:
- Phase 1: 고정 plan (빠른 검증)
- Phase 2: 단순 LLM (task, max_steps만)
- Phase 3: 정교한 분석 (targets, strategy까지)

### Search Plan

#### Phase 1: 패턴 기반 (고정 전략)
```python
def search_plan_node(state: AgentState) -> AgentState:
    """
    단계별 고정 패턴
    
    Step 0: 심볼/파일 찾기 (hybrid)
    Step 1: 호출 관계 확장 (graph)
    """
    step = state.search_steps
    
    if step == 0:
        # 초기 검색: 심볼 찾기
        intent = CodeSearchIntent(
            entities=[state.query],  # 쿼리를 그대로 entity로
            keywords=[],
            strategy="hybrid",
            limit=20
        )
    elif step == 1:
        # 확장 검색: 관계 탐색
        intent = CodeSearchIntent(
            entities=[],
            keywords=["caller", "usage"],
            strategy="graph",
            graph_depth=2,
            edge_types=["calls", "uses"],
            limit=10
        )
    
    state.search_intents.append(intent)
    return state
```

#### Phase 2: LLM 기반 (동적 전략)
```markdown
질문: {query}
현재 단계: {search_steps}/{max_search_steps}

이미 수집한 결과: {len(accumulated_context.results)}개

다음 검색 의도:
- Step 0: 심볼 정의 찾기 (entities에 심볼명, hybrid)
- Step 1: 호출 관계 확장 (graph, edge_types: calls)
- Step 2: 타입 정보 수집 (semantic, keywords: type)

JSON으로 응답:
{
  "entities": ["UserService"],
  "keywords": [],
  "strategy": "hybrid",
  "graph_depth": 1,
  "limit": 20
}
```

**단계적 접근**:
- Phase 1: 고정 패턴 (step 0 = hybrid, step 1 = graph)
- Phase 2: LLM으로 동적 생성
- Phase 3: 이전 결과 기반 adaptive search

## 7. 확장 포인트

### 7.1 Multi-Repo 지원
- `repo_ids` 필드로 여러 저장소 동시 검색
- 결과 병합 시 repo_id 기준 그룹화

### 7.2 Advanced Search Strategies

**Note**: SearchStrategy는 위에서 이미 정의됨 (중복 방지)

```python
# ✅ 이미 정의된 SearchStrategy 사용
# class SearchStrategy(str, Enum):
#     HYBRID = "hybrid"
#     LEXICAL = "lexical"
#     SEMANTIC = "semantic"
#     GRAPH = "graph"

# 사용 예시
intent = CodeSearchIntent(
    entities=["UserService"],
    strategy=SearchStrategy.GRAPH,  # Enum 사용
    graph_depth=2
)
```

### 7.3 Memory 통합
```python
class ConversationMemory:
    """대화 이력 관리"""
    
    def add_turn(self, query: str, answer: str, context: RetrievedContext):
        """턴 저장"""
        
    def get_relevant_history(self, query: str, k: int = 3) -> List[dict]:
        """관련 이전 대화 검색"""
```

### 7.4 Streaming 응답
```python
async def stream_answer(state: AgentState):
    """실시간 답변 스트리밍"""
    async for chunk in llm.astream(prompt):
        yield chunk
```

## 8. 다음 단계

### Phase 1: MVP (1주)
**목표**: 단순 플로우로 빠른 검증

```python
# 최소 노드 구성
1. intent_plan: 고정된 plan 반환 (LLM 없이)
2. run_search: 단일 검색 (intent 하드코딩)
3. generate_answer: 간단한 템플릿 기반 답변

# 플로우
intent_plan → run_search → generate_answer
```

**구현 항목**:
1. State, Tools (HTTP 백엔드), 최소 Nodes
2. LangGraph 기본 구성
3. FastAPI `/chat` 엔드포인트
4. 수동 테스트

### Phase 2: Search Loop (1주)
**목표**: 반복 검색으로 컨텍스트 누적

```python
# 전체 노드 구성
intent_plan → search_plan → run_search → aggregate → check_enough
                  ↑_____________________________________________|
```

**구현 항목**:
1. search_plan 노드 (LLM 기반 동적 intent 생성)
2. aggregate_context 노드 (dedupe + top-k)
3. enough_context 노드 (heuristic 버전)
4. 조건부 루프 라우팅
5. 프롬프트 템플릿 (intent_plan.md, search_plan.md)

### Phase 3: 고도화 (2주)
**목표**: 프로덕션 레벨 기능

**구현 항목**:
1. Memory 통합 (대화 이력)
2. Multi-repo 지원
3. Streaming 응답 (SSE)
4. LLM 기반 enough_context
5. 벤치마크 스크립트
6. 평가 메트릭 (precision, recall, graph_coverage)
