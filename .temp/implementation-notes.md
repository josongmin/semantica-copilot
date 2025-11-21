# 구현 시 주의사항

## 1. RetrievedContext 최적화

### 문제: 매번 set() 생성
```python
# 현재 (매번 O(n) 변환)
if key in set(self.dedupe_keys):
    return False
```

### 해결 1: 내부 캐시 유지 (권장)
```python
from pydantic import BaseModel, Field, PrivateAttr
from typing import List, Set

class RetrievedContext(BaseModel):
    results: List[SearchResult] = Field(default_factory=list)
    dedupe_keys: List[str] = Field(default_factory=list)

    # Pydantic private attr (직렬화 안됨)
    _dedupe_set: Set[str] = PrivateAttr(default_factory=set)

    def add_result(self, result: SearchResult) -> bool:
        """O(1) 중복 체크"""
        key = f"{result.repo_id}:{result.file_path}:{result.line_start}"
        if key in self._dedupe_set:
            return False

        self._dedupe_set.add(key)
        self.dedupe_keys.append(key)  # JSON 직렬화용
        self.results.append(result)
        return True

    def model_post_init(self, __context):
        """역직렬화 시 _dedupe_set 복원"""
        self._dedupe_set = set(self.dedupe_keys)
```

**장점**:
- O(1) 중복 체크
- JSON 직렬화 안전 (dedupe_keys는 list로 유지)
- LangGraph 체크포인트 호환

### 해결 2: 프로퍼티 캐싱 (간단)
```python
from functools import cached_property

class RetrievedContext(BaseModel):
    results: List[SearchResult] = Field(default_factory=list)
    dedupe_keys: List[str] = Field(default_factory=list)

    @cached_property
    def _dedupe_set(self) -> Set[str]:
        return set(self.dedupe_keys)

    def add_result(self, result: SearchResult) -> bool:
        key = f"{result.repo_id}:{result.file_path}:{result.line_start}"
        if key in self._dedupe_set:
            return False

        # 캐시 무효화 필요
        if hasattr(self, '_dedupe_set'):
            delattr(self, '_dedupe_set')

        self.dedupe_keys.append(key)
        self.results.append(result)
        return True
```

**선택**: 해결 1 (PrivateAttr) 추천

## 2. EnoughContext Heuristic 수정

### 현재 (잘못됨)
```python
if state.accumulated_context.results and \
   state.accumulated_context.results[0].score > 0.9:
    return True
```

**문제**: results가 점수순 정렬 보장 안됨

### 수정 (올바름)
```python
def check_enough_context_heuristic(state: AgentState) -> bool:
    """휴리스틱 기반 종료 조건"""
    # 1. 최대 스텝 도달
    if state.search_steps >= state.max_search_steps:
        return True

    # 2. 에러 발생
    if state.error:
        return True

    # 3. 결과 없음
    if not state.accumulated_context.results:
        return False

    # 4. 최상위 점수 체크 (정렬된 결과)
    top_results = state.accumulated_context.get_top_k(5)
    if top_results and top_results[0].score > 0.9:
        return True

    # 5. 충분한 컨텍스트 양
    if len(state.accumulated_context.results) >= 50:
        return True

    # 6. 평균 점수가 높음
    avg_score = sum(r.score for r in top_results[:10]) / min(10, len(top_results))
    if avg_score > 0.75 and len(state.accumulated_context.results) >= 20:
        return True

    return False
```

## 3. CodeGraphClient - Intent 연결

### CodeGraphClient에 추가
```python
class CodeGraphClient:
    """semantica-codegraph 통합 클라이언트"""

    async def search_with_intent(
        self,
        intent: CodeSearchIntent,
        repo_ids: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """
        Intent 기반 검색 (노드에서 직접 사용)

        Intent의 entities, keywords, strategy 등을
        실제 검색 파라미터로 변환
        """
        # Query 구성
        query_parts = []
        if intent.entities:
            query_parts.extend(intent.entities)
        if intent.keywords:
            query_parts.extend(intent.keywords)

        query = " ".join(query_parts) if query_parts else ""

        # 전략별 파라미터 매핑
        search_params = {
            "query": query,
            "repo_ids": repo_ids,
            "limit": intent.limit,
        }

        # Strategy 적용
        if intent.strategy == "graph":
            # 그래프 검색 강조
            search_params["weights"] = {
                "lexical": 0.1,
                "semantic": 0.2,
                "graph": 0.6,
                "fuzzy": 0.1
            }
        elif intent.strategy == "semantic":
            search_params["weights"] = {
                "lexical": 0.1,
                "semantic": 0.8,
                "graph": 0.1,
                "fuzzy": 0.0
            }
        # hybrid는 기본값 사용

        # Graph 옵션
        if intent.graph_depth > 1:
            search_params["graph_depth"] = intent.graph_depth
        if intent.edge_types:
            search_params["edge_types"] = intent.edge_types

        return await self.search_code(**search_params)

    async def search_code(
        self,
        query: str,
        repo_ids: Optional[List[str]] = None,
        limit: int = 20,
        weights: Optional[Dict[str, float]] = None,
        graph_depth: int = 1,
        edge_types: Optional[List[str]] = None,
        **kwargs
    ) -> List[SearchResult]:
        """하이브리드 검색 (파라미터 확장)"""
        if self.backend == BackendType.HTTP:
            return await self._search_http(
                query, repo_ids, limit, weights, graph_depth, edge_types, **kwargs
            )
        # ... 다른 백엔드
```

### RunSearchNode에서 사용
```python
async def run_search_node(state: AgentState) -> AgentState:
    """검색 실행 노드"""
    if not state.search_intents:
        state.error = "No search intent"
        return state

    intent = state.search_intents[-1]

    try:
        # Intent를 직접 전달
        results = await client.search_with_intent(
            intent=intent,
            repo_ids=state.repo_ids
        )

        # 결과 누적 (중복 제거)
        added_count = 0
        for result in results:
            if state.accumulated_context.add_result(result):
                added_count += 1

        logger.info(
            f"Step {state.search_steps}: Added {added_count}/{len(results)} results"
        )

        state.search_steps += 1

    except Exception as e:
        logger.error(f"Search failed: {e}")
        state.error = str(e)

    return state
```

## 4. Import 전략

### 패키지 구조
```
semantica-copilot/
├── pyproject.toml  # name = "semantica-copilot"
└── src/
    └── semantica_copilot/  # 패키지 루트 (언더스코어!)
        ├── __init__.py
        ├── agent/
        │   ├── __init__.py
        │   ├── state.py
        │   ├── graph.py
        │   ├── nodes/
        │   └── routing.py
        └── tools/
            ├── __init__.py
            └── codegraph.py
```

**주의**: 패키지명은 `semantica_copilot` (언더스코어)

### 절대 Import 원칙
```python
# ✅ 좋음: 절대 import
from semantica_copilot.agent.state import AgentState, CodeSearchIntent
from semantica_copilot.tools.codegraph import CodeGraphClient, BackendType

# ❌ 나쁨: 상대 import
from ..state import AgentState
from ...tools.codegraph import CodeGraphClient
```

### pyproject.toml 설정
```toml
[project]
name = "semantica-copilot"
version = "0.1.0"

[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-data]
"semantica_copilot" = ["prompts/*.md"]
```

## 5. 추가 제안

### 5.1 SearchIntent 빌더 패턴
```python
# src/agent/nodes/search_plan.py

class SearchIntentBuilder:
    """LLM 응답 → CodeSearchIntent 변환"""

    @staticmethod
    def from_llm_response(response: dict, step: int) -> CodeSearchIntent:
        """LLM JSON 응답을 Intent로 변환"""
        return CodeSearchIntent(
            entities=response.get("entities", []),
            keywords=response.get("keywords", []),
            strategy=response.get("strategy", "hybrid"),
            graph_depth=response.get("graph_depth", 1),
            edge_types=response.get("edge_types"),
            limit=response.get("limit", 20),
            step=step
        )

async def search_plan_node(state: AgentState) -> AgentState:
    """검색 계획 노드"""
    prompt = build_search_plan_prompt(state)
    response = await llm.ainvoke(prompt)

    # JSON 파싱
    intent_data = parse_json_response(response.content)

    # Intent 생성
    intent = SearchIntentBuilder.from_llm_response(
        intent_data,
        step=state.search_steps
    )

    state.search_intents.append(intent)
    return state
```

### 5.2 에러 복구 전략
```python
# src/agent/routing.py

def route_enough_context(state: AgentState) -> str:
    """종료 조건 판단 + 에러 복구"""

    # 에러 발생 시
    if state.error:
        # 재시도 가능한 에러인지 체크
        if "timeout" in state.error.lower() and state.search_steps < 2:
            state.error = None  # 에러 클리어
            return "continue"  # 재시도
        return "finish"  # 복구 불가능

    # 정상 종료 조건
    if state.enough_context:
        return "finish"

    if state.search_steps >= state.max_search_steps:
        return "finish"

    return "continue"
```

### 5.3 로깅/모니터링
```python
# src/agent/nodes/__init__.py

import logging
from functools import wraps

logger = logging.getLogger(__name__)

def log_node_execution(func):
    """노드 실행 로깅 데코레이터"""
    @wraps(func)
    async def wrapper(state: AgentState) -> AgentState:
        node_name = func.__name__.replace("_node", "")
        logger.info(f"[{node_name}] Step {state.search_steps}: Starting")

        try:
            result = await func(state)
            logger.info(
                f"[{node_name}] Completed. "
                f"Results: {len(result.accumulated_context.results)}"
            )
            return result
        except Exception as e:
            logger.error(f"[{node_name}] Failed: {e}")
            state.error = str(e)
            return state

    return wrapper

@log_node_execution
async def run_search_node(state: AgentState) -> AgentState:
    ...
```

## 6. 테스트 전략

### 6.1 CodeGraphClient Mock
```python
# tests/conftest.py

import pytest
from semantica_copilot.tools.codegraph import CodeGraphClient
from semantica_copilot.agent.state import SearchResult

class MockCodeGraphClient(CodeGraphClient):
    """테스트용 Mock 클라이언트"""

    def __init__(self):
        self.search_calls = []

    async def search_with_intent(self, intent, repo_ids=None):
        self.search_calls.append(intent)

        # 더미 결과 반환
        return [
            SearchResult(
                repo_id="test-repo",
                chunk_id=f"chunk-{i}",
                file_path=f"test_{i}.py",
                line_start=i*10,
                line_end=i*10+5,
                text=f"test code {i}",
                score=0.8 - i*0.1,
                scores={"lexical": 0.5, "semantic": 0.6, "graph": 0.7, "fuzzy": 0.3}
            )
            for i in range(5)
        ]

@pytest.fixture
def mock_client():
    return MockCodeGraphClient()
```

### 6.2 노드 단위 테스트
```python
# tests/agent/test_nodes.py

import pytest
from semantica_copilot.agent.state import AgentState, CodeSearchIntent
from semantica_copilot.agent.nodes.run_search import run_search_node

@pytest.mark.asyncio
async def test_run_search_node(mock_client):
    """검색 노드 테스트"""
    state = AgentState(
        query="test query",
        repo_ids=["test-repo"],
        search_intents=[
            CodeSearchIntent(entities=["test"], limit=10)
        ]
    )

    result = await run_search_node(state)

    assert result.search_steps == 1
    assert len(result.accumulated_context.results) == 5
    assert result.error is None
```

## 7. 최종 의견 및 우선순위

### 완전 동의 (바로 적용)

1. **✅ search_with_intent() 필수**
   ```python
   async def search_with_intent(self, intent: CodeSearchIntent, repo_ids):
       query = " ".join(intent.keywords or intent.entities)
       return await self.search_code(
           query=query, limit=intent.limit,
           strategy=intent.strategy, graph_depth=intent.graph_depth
       )
   ```
   → 노드 코드 단순화, Intent가 실제 검색에 반영

2. **✅ get_top_k() 사용**
   ```python
   top1 = state.accumulated_context.get_top_k(1)
   if top1 and top1[0].score > 0.9:
       return True
   ```
   → 정렬 보장, 안전한 점수 체크

3. **✅ 에러 핸들링 플로우**
   - run_search_node: state.error 세팅
   - route_enough_context: error 있으면 "finish"
   - generate_answer_node: error 응답 템플릿

### MVP 전략 선택 (실용주의)

**Option A: LangGraph 없이 시작 (추천)**
```python
# Phase 0 (2-3일): 함수 체인
def simple_agent(query, repo_ids):
    intent = CodeSearchIntent(entities=[query], limit=10)
    results = await client.search_with_intent(intent, repo_ids)
    answer = generate_simple_answer(query, results)
    return answer

# CLI로 테스트, 디버깅 쉬움
```

**Option B: 바로 LangGraph (설계 검증)**
```python
# Phase 1 (1주): 최소 노드 + LangGraph
graph = StateGraph(AgentState)
graph.add_node("search", run_search_node)
graph.add_node("answer", generate_answer_node)
```

**의견**: Option A 추천
- 이유: 디버깅 시간 80% 절약, codegraph 연동 먼저 검증
- Option B는 Phase 1.5에서 마이그레이션

### RetrievedContext 최적화 전략

**MVP (지금 그대로)**
```python
if key in set(self.dedupe_keys):  # 매번 O(n) 변환
    return False
```
→ 성능 이슈 없으면 이대로 유지 (단순함 우선)

**최적화 필요시**
```python
@property
def _dedupe_set(self) -> set[str]:
    return set(self.dedupe_keys)
```
→ 매 add_result마다 set 생성 (여전히 O(n))
→ 근본 해결은 PrivateAttr지만, MVP에서는 불필요

**결론**: MVP는 현재대로, 병목 확인 후 최적화

### SearchResult.text 채우기

**현재 문제**
```python
text="",  # TODO: chunk store에서 가져와야 함
```

**해결 방안 (우선순위순)**

1. **codegraph API 수정 (권장)**
   ```python
   # semantica-codegraph의 MCPService.search_code에서
   chunk = self.chunk_store.get_chunk(repo_id, candidate.chunk_id)
   text = chunk.text if chunk else ""
   ```
   → copilot은 그냥 받기만 하면 됨

2. **copilot에서 추가 호출**
   ```python
   results = await client.search_code(...)
   for r in results:
       if not r.text:
           r.text = await client.get_chunk_text(r.repo_id, r.chunk_id)
   ```
   → N+1 문제, 느림

3. **일단 빈 문자열 허용**
   ```python
   text = r.text or f"[{r.file_path}:{r.line_start}-{r.line_end}]"
   ```
   → MVP 임시 방편

**선택**: 1번 (codegraph API 수정)이 정답

### 구현 우선순위

**Phase 0: 함수 체인 검증 (2-3일)**
```
1. CodeGraphClient (HTTP 백엔드만)
2. search_with_intent 메서드
3. 단순 함수 체인 (intent → search → answer)
4. CLI 테스트
```

**Phase 1: LangGraph 마이그레이션 (3-4일)**
```
1. State 정의 (Field + default_factory)
2. 3개 노드 (intent_plan, run_search, generate)
3. 순차 플로우 (루프 없음)
4. FastAPI 엔드포인트
```

**Phase 2: Search Loop (1주)**
```
1. search_plan 노드 + LLM
2. aggregate + check_enough
3. 조건부 루프
4. 프롬프트 튜닝
```

### 놓치기 쉬운 포인트 체크리스트

- [ ] 패키지명 `semantica_copilot` (언더스코어)
- [ ] 절대 import 사용
- [ ] search_with_intent 구현
- [ ] get_top_k로 점수 체크
- [ ] 에러 핸들링 플로우 명확히
- [ ] SearchResult.text 채우기 (codegraph 수정)
- [ ] 로깅 추가 (노드 입출력)

### 추가 조언

**1. CLI 우선 개발**
```bash
# 빠른 테스트
python -m semantica_copilot.cli query "UserService는 뭐하는 클래스?"
```

**2. codegraph API 확인**
```python
# 먼저 수동으로 테스트
import httpx
response = httpx.post("http://localhost:8000/search", json={
    "query": "UserService",
    "repo_ids": ["test-repo"],
    "limit": 5
})
print(response.json())
```

**3. LLM 없이 먼저**
```python
# intent_plan_node (고정 반환)
def intent_plan_node(state):
    state.plan = {"task": "search", "max_steps": 1}
    return state

# search_plan_node (하드코딩)
def search_plan_node(state):
    state.search_intents.append(
        CodeSearchIntent(entities=[state.query], limit=10)
    )
    return state
```

**4. 점진적 LLM 통합**
```python
# Step 1: 템플릿만
answer = f"검색 결과:\n{context}"

# Step 2: 단순 프롬프트
answer = llm.invoke(f"다음 코드를 설명:\n{context}")

# Step 3: 정교한 프롬프트
answer = llm.invoke(prompt_template.format(query=..., context=...))
```

### 최종 결론

**아키텍처: 완성도 95%**
- 구조/플로우/State 설계 전부 프로덕션 레벨
- 지금 바로 구현 시작 가능

**실행 전략: Phase 0 → Phase 1 → Phase 2**
- Phase 0로 codegraph 연동 검증 (디버깅 쉬움)
- Phase 1에서 LangGraph 마이그레이션
- Phase 2에서 Search Loop 완성

**바로 해야 할 것**:
1. ✅ pyproject.toml 생성
2. ✅ 디렉토리 구조 생성
3. ✅ CodeGraphClient 구현 (search_with_intent 포함)
4. ✅ 단순 함수 체인으로 E2E 테스트

**문서 상태**: `docs/architecture.md`로 바로 커밋 가능

---

**지금 구현 시작할까요?**
