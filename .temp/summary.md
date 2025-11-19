# 최종 설계 요약

## 핵심 결정사항

### 1. State 설계

**✅ 채택된 설계**:
```python
from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class SearchStrategy(str, Enum):
    """검색 전략 (타입 안전)"""
    HYBRID = "hybrid"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    GRAPH = "graph"

class CodeSearchIntent(BaseModel):
    entities: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    strategy: SearchStrategy = SearchStrategy.HYBRID  # Enum!
    graph_depth: int = 1
    limit: int = 20
    edge_types: Optional[List[str]] = None

class RetrievedContext(BaseModel):
    results: List[SearchResult] = Field(default_factory=list)
    dedupe_keys: List[str] = Field(default_factory=list)
    
    @property
    def _dedupe_set(self) -> set:
        """MVP: 매번 생성으로 충분"""
        return set(self.dedupe_keys)
    
    def add_result(self, result: SearchResult) -> bool:
        key = f"{result.repo_id}:{result.file_path}:{result.line_start}"
        if key in self._dedupe_set:
            return False
        self.dedupe_keys.append(key)
        self.results.append(result)
        return True
    
    def get_top_k(self, k: int) -> List[SearchResult]:
        return sorted(self.results, key=lambda x: x.score, reverse=True)[:k]

class AgentState(BaseModel):
    """LangGraph State"""
    query: str
    repo_ids: Optional[List[str]] = None
    plan: Optional[Dict] = None
    search_intents: List[CodeSearchIntent] = Field(default_factory=list)
    accumulated_context: RetrievedContext = Field(default_factory=RetrievedContext)
    search_steps: int = 0
    max_search_steps: int = 3
    answer: Optional[str] = None
    error: Optional[str] = None
    
    # enough_context 필드 제거됨 ✅
```

**변경사항**:
1. ✅ `SearchStrategy` Enum 추가 (타입 안전성)
2. ✅ `enough_context` 필드 제거 (routing이 직접 판단)
3. ✅ `@property`로 `_dedupe_set` (MVP 충분)
4. ✅ Enum 직렬화: `.value` 변환 (HTTP 전송 시)

### 2. Tools 설계

**✅ search_with_intent 추가**:
```python
class CodeGraphClient:
    async def search_with_intent(
        self,
        intent: CodeSearchIntent,
        repo_ids: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """Intent → 검색 파라미터 변환"""
        query = " ".join(intent.keywords or intent.entities)
        
        # Strategy → weights 매핑
        weights = None
        if intent.strategy == SearchStrategy.GRAPH:
            weights = {"lexical": 0.1, "semantic": 0.2, "graph": 0.6, "fuzzy": 0.1}
        elif intent.strategy == SearchStrategy.SEMANTIC:
            weights = {"lexical": 0.1, "semantic": 0.8, "graph": 0.1, "fuzzy": 0.0}
        
        return await self.search_code(
            query=query,
            repo_ids=repo_ids,
            limit=intent.limit,
            weights=weights,
            graph_depth=intent.graph_depth,
            edge_types=intent.edge_types,
        )
```

### 3. Routing 설계

**✅ routing에서만 판단 (A안)**:
```python
def route_enough_context(state: AgentState) -> str:
    """
    종료 조건 판단 (단일 진실 공급원)
    
    Note: state.enough_context 필드 사용하지 않음
    """
    if state.error:
        return "finish"
    
    if state.search_steps >= state.max_search_steps:
        return "finish"
    
    if check_enough_context_heuristic(state):
        return "finish"
    
    return "continue"

def check_enough_context_heuristic(state: AgentState) -> bool:
    """휴리스틱 판단"""
    if len(state.accumulated_context.results) >= 50:
        return True
    
    # get_top_k 사용 (안전)
    top1 = state.accumulated_context.get_top_k(1)
    if top1 and top1[0].score > 0.9:
        return True
    
    return False
```

### 4. 노드 설계

**✅ run_search_node (최종)**:
```python
async def run_search_node(state: AgentState) -> AgentState:
    """검색 실행 (깔끔)"""
    if not state.search_intents:
        state.error = "No search intent"
        return state
    
    intent = state.search_intents[-1]
    
    try:
        # search_with_intent 사용
        results = await client.search_with_intent(intent, state.repo_ids)
        
        # 중복 제거하며 추가
        for r in results:
            state.accumulated_context.add_result(r)
        
        state.search_steps += 1
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        state.error = str(e)
    
    return state
```

## 구현 전략

### Phase 0: 함수 체인 PoC (2-3일) ⭐ 추천

```python
# 목표: codegraph 연동 먼저 검증
async def simple_agent(query: str, repo_ids: List[str]) -> str:
    intent = CodeSearchIntent(
        entities=[query],
        strategy=SearchStrategy.HYBRID,
        limit=10
    )
    
    client = CodeGraphClient(backend=BackendType.HTTP)
    results = await client.search_with_intent(intent, repo_ids)
    
    context = "\n".join([r.text for r in results[:5]])
    return f"결과:\n{context}"

# CLI 테스트
python -m semantica_copilot.cli query "UserService"
```

**검증 항목**:
- [ ] codegraph API 연결
- [ ] SearchResult.text 필드 확인
- [ ] 검색 품질 체크
- [ ] strategy 차이 확인

### Phase 1: LangGraph 기본 (3-4일)

```python
graph = StateGraph(AgentState)
graph.add_node("plan", intent_plan_node)      # 고정
graph.add_node("search", run_search_node)
graph.add_node("answer", generate_answer_node)

graph.set_entry_point("plan")
graph.add_edge("plan", "search")
graph.add_edge("search", "answer")
graph.add_edge("answer", END)
```

### Phase 2: Search Loop (1주)

```python
graph.add_node("search_plan", search_plan_node)  # 패턴 기반
graph.add_node("aggregate", aggregate_context_node)
graph.add_conditional_edges("aggregate", route_enough_context)
```

## 체크리스트

**State**:
- [x] SearchStrategy Enum 추가
- [x] enough_context 필드 제거
- [x] @property로 _dedupe_set
- [x] get_top_k 사용

**Tools**:
- [x] search_with_intent 메서드 설계
- [ ] httpx.AsyncClient aclose() 구현
- [ ] codegraph text 필드 확인

**Routing**:
- [x] routing에서만 판단 (A안)
- [x] check_enough_context_heuristic 설계

**구현**:
- [ ] pyproject.toml
- [ ] 디렉토리 구조
- [ ] Phase 0 (함수 체인)
- [ ] codegraph 연동 테스트

## 아키텍처 최종 평가

| 항목 | 상태 | 비고 |
|------|------|------|
| **구조 설계** | ⭐⭐⭐⭐⭐ | 프로덕션 레벨 |
| **State 설계** | ⭐⭐⭐⭐⭐ | Enum, 필드 정리 완료 |
| **Tools 설계** | ⭐⭐⭐⭐⭐ | search_with_intent 추가 |
| **Routing 설계** | ⭐⭐⭐⭐⭐ | 일관성, 단순성 확보 |
| **Phase 계획** | ⭐⭐⭐⭐⭐ | Phase 0 → 1 → 2 명확 |

## 미세 튜닝 완료 사항

1. ✅ RetrievedContext: @property로 충분 (MVP)
2. ✅ AgentState: enough_context 제거 (A안)
3. ✅ SearchStrategy: Enum으로 타입 안전성
4. ✅ CodeGraphClient: search_with_intent 추가
5. ✅ httpx.AsyncClient: 재사용 구조 확인
6. ✅ LangGraph: 플로우 정석 패턴
7. ✅ Phase: 0 (PoC) → 1 (LangGraph) → 2 (Loop)

## 다음 액션

**바로 시작 가능**: ✅

1. pyproject.toml 생성
2. 디렉토리 구조 생성
3. Phase 0 구현 (함수 체인)
4. codegraph 연동 테스트

---

**설계 완료. 구현 시작 준비 완료.**

