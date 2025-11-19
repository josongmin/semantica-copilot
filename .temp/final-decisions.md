# 최종 설계 결정사항

## 1. RetrievedContext 최적화

### 결정: @property 패턴 사용

```python
class RetrievedContext(BaseModel):
    results: List[SearchResult] = Field(default_factory=list)
    dedupe_keys: List[str] = Field(default_factory=list)
    
    @property
    def _dedupe_set(self) -> set:
        """중복 체크용 (매번 생성)"""
        return set(self.dedupe_keys)
    
    def add_result(self, result: SearchResult) -> bool:
        key = f"{result.repo_id}:{result.file_path}:{result.line_start}"
        if key in self._dedupe_set:
            return False
        self.dedupe_keys.append(key)
        self.results.append(result)
        return True
```

**이유**:
- MVP에서는 성능 이슈 없음
- 코드 단순 유지
- 병목 발견 시 PrivateAttr로 전환 용이

## 2. EnoughContext 판단 위치

### 결정: routing 함수에서만 판단 (A안)

```python
# ❌ 노드에서 state.enough_context 세팅하지 않음
def enough_context_node(state: AgentState) -> AgentState:
    # 이 노드는 실제로 불필요 (제거 고려)
    return state

# ✅ routing에서만 판단
def route_enough_context(state: AgentState) -> str:
    if state.error:
        return "finish"
    if state.search_steps >= state.max_search_steps:
        return "finish"
    if check_enough_context_heuristic(state):
        return "finish"
    return "continue"
```

**A안 vs B안**:
- **A안 (채택)**: enough_context 필드 삭제, routing이 직접 판단
  - 일관성: 판단 로직 한 곳
  - 단순함: 불필요한 상태 제거
  - 명확함: routing 함수가 단일 진실 공급원
  
- B안 (비추): 노드에서 state.enough_context 세팅, routing이 신뢰
  - 상태와 판단 로직 분산
  - 불일치 가능성

**State 수정 (최종)**:
```python
class AgentState(BaseModel):
    # enough_context: bool = False  # 제거됨 ✅
    # routing 함수가 heuristic 직접 호출
```

## 3. SearchStrategy Enum

### 결정: str Enum으로 타입 안정성 강화

```python
from enum import Enum

class SearchStrategy(str, Enum):
    """검색 전략"""
    HYBRID = "hybrid"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    GRAPH = "graph"

class CodeSearchIntent(BaseModel):
    strategy: SearchStrategy = SearchStrategy.HYBRID
```

**이유**:
- 타입 안정성: IDE 자동완성, 오타 방지
- 검증: Pydantic이 자동 검증
- 직렬화: str Enum은 JSON 호환

**⚠️ 중요: HTTP 전송 시 .value 변환 필수**:
```python
# ❌ 직접 전송하면 직렬화 에러
json={"strategy": intent.strategy}

# ✅ .value로 변환
json={"strategy": intent.strategy.value}

# 또는 search_with_intent에서 자동 변환
async def search_with_intent(self, intent, repo_ids):
    return await self.search_code(
        strategy=intent.strategy.value,  # ⚠️ 필수
        ...
    )
```

## 4. search_with_intent 메서드

### 결정: CodeGraphClient에 추가 필수

```python
class CodeGraphClient:
    async def search_with_intent(
        self,
        intent: CodeSearchIntent,
        repo_ids: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """Intent → 검색 파라미터 변환"""
        query = " ".join(intent.keywords or intent.entities)
        
        # Strategy → weights 매핑 (Enum 사용)
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

**노드 단순화**:
```python
async def run_search_node(state: AgentState) -> AgentState:
    intent = state.search_intents[-1]
    results = await client.search_with_intent(intent, state.repo_ids)
    
    for r in results:
        state.accumulated_context.add_result(r)
    
    state.search_steps += 1
    return state
```

**이유**:
- Intent의 strategy/graph_depth가 실제 검색에 반영
- LLM이 짠 intent가 즉시 활용
- 노드 코드 극단적 단순화

## 5. httpx.AsyncClient 재사용

### 결정: __init__에서 생성, 재사용

```python
class CodeGraphClient:
    def __init__(self, backend: BackendType = BackendType.HTTP, base_url: str = "..."):
        if backend == BackendType.HTTP:
            import httpx
            self.client = httpx.AsyncClient(base_url=base_url)
    
    async def aclose(self):
        """종료 시 호출"""
        if hasattr(self, 'client') and isinstance(self.client, httpx.AsyncClient):
            await self.client.aclose()
```

**이유**:
- httpx.AsyncClient는 연결 풀링, 재사용 전제
- __init__에서 생성이 정석
- 종료 훅은 DI/컨테이너에서 관리

**FastAPI 통합**:
```python
# app startup/shutdown
@app.on_event("startup")
async def startup():
    app.state.client = CodeGraphClient(backend=BackendType.HTTP)

@app.on_event("shutdown")
async def shutdown():
    await app.state.client.aclose()
```

## 6. get_top_k 사용

### 결정: results 직접 참조 금지

```python
# ❌ 위험: 정렬 보장 없음
if state.accumulated_context.results[0].score > 0.9:
    return True

# ✅ 안전: 정렬 보장
top1 = state.accumulated_context.get_top_k(1)
if top1 and top1[0].score > 0.9:
    return True
```

**이유**:
- results는 추가 순서대로 저장 (정렬 안됨)
- get_top_k는 명시적 정렬
- 코드 의도 명확

## 7. Phase 0: 함수 체인 PoC (추천)

### 결정: LangGraph 전에 함수 체인으로 먼저 검증

```python
# Phase 0 (2-3일): PoC
async def simple_agent(query: str, repo_ids: List[str]) -> str:
    # 1. 고정 intent
    intent = CodeSearchIntent(
        entities=[query],
        strategy=SearchStrategy.HYBRID,
        limit=10
    )
    
    # 2. 검색
    client = CodeGraphClient(backend=BackendType.HTTP)
    results = await client.search_with_intent(intent, repo_ids)
    
    # 3. 단순 답변
    context = "\n".join([r.text for r in results[:5]])
    answer = f"검색 결과:\n{context}"
    
    return answer

# CLI 테스트
if __name__ == "__main__":
    result = asyncio.run(simple_agent("UserService", ["repo1"]))
    print(result)
```

**이유**:
- codegraph 쿼리/점수/맥락 먼저 검증
- LangGraph 복잡도 배제, 디버깅 쉬움
- 멘탈 부담 감소
- 검증 후 LangGraph로 마이그레이션

**검증 항목**:
- [ ] codegraph API 연결
- [ ] text 필드 존재 확인
- [ ] 검색 결과 품질 체크
- [ ] strategy별 차이 확인

## 8. 프롬프트 전략 (단계적)

### Phase 1: 고정 패턴

```python
# intent_plan: 고정 반환
state.plan = {
    "task": "code_explanation",
    "max_search_steps": 2,
    "strategy": "hybrid"
}

# search_plan: 단계별 고정 패턴
if step == 0:
    # 심볼 찾기
    intent = CodeSearchIntent(
        entities=[state.query],
        strategy="hybrid",
        limit=20
    )
elif step == 1:
    # 관계 확장
    intent = CodeSearchIntent(
        keywords=["caller", "usage"],
        strategy="graph",
        graph_depth=2,
        limit=10
    )
```

**이유**:
- 빠른 검증
- 디버깅 용이
- "어디서 맥락 부족한지" 눈으로 확인

### Phase 2: 단순 LLM

```python
# intent_plan: task, max_steps만 LLM
prompt = f"작업 유형과 검색 단계 수 결정: {query}"
response = llm.invoke(prompt)
state.plan = parse_json(response)

# search_plan: 단순 entity 추출
prompt = f"다음 쿼리에서 검색할 심볼명: {query}"
entities = llm.invoke(prompt)
intent = CodeSearchIntent(entities=entities, strategy="hybrid")
```

### Phase 3: 정교한 LLM

```python
# search_plan: 이전 결과 기반
prompt = f"""
Query: {query}
이미 수집: {len(results)}개
상위 파일: {top_files}

다음 검색 전략:
- entities: ?
- strategy: ?
- edge_types: ?
"""
```

**진행 순서**: Phase 1 → 2 → 3 (점진적)

## 6. 백엔드 추상화

### 결정: 현재 설계 유지

```python
class BackendType(Enum):
    HTTP = "http"
    MCP = "mcp"
    DIRECT = "direct"

# 에이전트는 backend-agnostic
results = await client.search_with_intent(intent, repo_ids)
```

**체크리스트**:
- [ ] HTTP: /search API 스펙과 SearchResult 매핑 확인
- [ ] DIRECT: text 필드 채우기 (chunk_store 연동)
- [ ] MCP: 추후 구현

## 7. SearchResult.text 채우기

### 결정: codegraph API 수정

```python
# semantica-codegraph/apps/mcp_server/service.py
chunk = self.chunk_store.get_chunk(repo_id, candidate.chunk_id)
text = chunk.text if chunk else ""

result = {
    "repo_id": candidate.repo_id,
    "chunk_id": candidate.chunk_id,
    "file_path": candidate.file_path,
    "line_start": candidate.span[0],
    "line_end": candidate.span[2],
    "text": text,  # 추가
    "score": candidate.features.get("total_score", 0.0),
    "scores": {...}
}
```

**이유**:
- copilot은 그냥 받기만 하면 됨
- N+1 문제 없음
- 단일 책임 원칙 (codegraph가 완전한 데이터 제공)

**확인 사항**:
- [ ] 현재 codegraph API가 text 반환하는지 확인
- [ ] 안하면 수정

## 8. 에러 핸들링 플로우

### 결정: 3단계 처리

```python
# 1. run_search_node: 에러 캐치 & 세팅
try:
    results = await client.search_with_intent(intent, repo_ids)
except Exception as e:
    logger.error(f"Search failed: {e}")
    state.error = str(e)
    return state

# 2. route_enough_context: 에러 시 종료
if state.error:
    return "finish"

# 3. generate_answer_node: 에러 응답
if state.error:
    state.answer = f"검색 중 오류 발생: {state.error}"
    return state
```

**일관성**:
- 노드: 세팅만
- Routing: 판단만
- Generate: 응답만

## 9. 구현 우선순위 (최종)

### Phase 0: 함수 체인 (2-3일)

```python
# 목표: codegraph 연동 검증
async def simple_agent(query: str, repo_ids: List[str]) -> str:
    # 1. Intent 생성
    intent = CodeSearchIntent(entities=[query], limit=10)
    
    # 2. 검색
    results = await client.search_with_intent(intent, repo_ids)
    
    # 3. 답변
    return f"결과 {len(results)}개:\n{results[0].text}"

# CLI 테스트
python -m semantica_copilot.cli query "UserService"
```

### Phase 1: LangGraph 기본 (3-4일)

```python
# 목표: 최소 플로우 동작
graph = StateGraph(AgentState)
graph.add_node("plan", intent_plan_node)      # 고정 plan
graph.add_node("search", run_search_node)     # 단일 검색
graph.add_node("answer", generate_answer_node) # 템플릿

graph.set_entry_point("plan")
graph.add_edge("plan", "search")
graph.add_edge("search", "answer")
graph.add_edge("answer", END)
```

### Phase 2: Search Loop (1주)

```python
# 목표: 반복 검색
graph.add_node("search_plan", search_plan_node)  # 패턴 기반
graph.add_node("aggregate", aggregate_context_node)
graph.add_conditional_edges("aggregate", route_enough_context)
```

## 10. 체크리스트 (구현 전)

- [ ] 패키지명 `semantica_copilot` (언더스코어)
- [ ] 절대 import 사용
- [ ] @property로 _dedupe_set
- [ ] get_top_k로 점수 체크
- [ ] search_with_intent 구현
- [ ] routing에서만 종료 판단
- [ ] 에러 핸들링 3단계
- [ ] codegraph text 필드 확인
- [ ] Phase 0부터 시작
- [ ] 프롬프트는 Phase 1에서 고정

## 11. 최종 의견

**아키텍처**: ⭐⭐⭐⭐⭐ 프로덕션 레벨

**전략**: 단계적 구현
- Phase 0: 함수 체인 검증
- Phase 1: LangGraph 기본
- Phase 2: Search Loop

**핵심 원칙**:
1. 단순함 우선 (MVP)
2. 점진적 복잡도 증가
3. 일관된 책임 분리
4. 백엔드 독립성

**바로 시작 가능**: ✅

