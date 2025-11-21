# 흔한 실수 방지 가이드

## 1. Enum 직렬화 (⚠️ 가장 중요)

### 문제
```python
# ❌ 이렇게 하면 직렬화 에러
intent = CodeSearchIntent(strategy=SearchStrategy.HYBRID)
response = await client.post("/search", json={
    "strategy": intent.strategy  # TypeError: Object of type SearchStrategy is not JSON serializable
})
```

### 해결
```python
# ✅ .value로 변환
response = await client.post("/search", json={
    "strategy": intent.strategy.value  # "hybrid" (str)
})

# ✅ 또는 search_with_intent에서 자동 변환
async def search_with_intent(self, intent, repo_ids):
    return await self.search_code(
        strategy=intent.strategy.value,  # ⚠️ 이 한 줄 필수
        ...
    )
```

### 패턴
```python
class CodeGraphClient:
    async def search_code(
        self,
        strategy: str,  # ⚠️ str로 받음 (Enum 아님)
        ...
    ):
        """HTTP 전송용은 항상 str"""
        pass

    async def search_with_intent(
        self,
        intent: CodeSearchIntent,  # Enum 포함 가능
        ...
    ):
        """내부에서 .value 변환"""
        return await self.search_code(
            strategy=intent.strategy.value,  # ✅ 변환
            ...
        )
```

## 2. Enum 중복 정의

### 문제
```python
# ❌ 여러 곳에 정의하면 타입 불일치
# file1.py
class SearchStrategy(str, Enum):
    HYBRID = "hybrid"

# file2.py
class SearchStrategy(Enum):  # 다른 정의!
    HYBRID = "hybrid"
```

### 해결
```python
# ✅ 한 곳에만 정의 (예: state.py)
# src/semantica_copilot/agent/state.py
class SearchStrategy(str, Enum):
    HYBRID = "hybrid"
    LEXICAL = "lexical"
    SEMANTIC = "semantic"
    GRAPH = "graph"

# 다른 파일에서 import
from semantica_copilot.agent.state import SearchStrategy
```

## 3. results 직접 참조

### 문제
```python
# ❌ 정렬 보장 없음
if state.accumulated_context.results[0].score > 0.9:
    return True
```

### 해결
```python
# ✅ get_top_k 사용
top1 = state.accumulated_context.get_top_k(1)
if top1 and top1[0].score > 0.9:
    return True
```

## 4. mutable default

### 문제
```python
# ❌ 모든 인스턴스가 같은 list 공유
class State(BaseModel):
    results: List[SearchResult] = []
```

### 해결
```python
# ✅ Field + default_factory
class State(BaseModel):
    results: List[SearchResult] = Field(default_factory=list)
```

## 5. 상대 import vs 절대 import

### 문제
```python
# ❌ 상대 import (구조 변경 시 깨짐)
from ..state import AgentState
from ...tools.codegraph import CodeGraphClient
```

### 해결
```python
# ✅ 절대 import
from semantica_copilot.agent.state import AgentState
from semantica_copilot.tools.codegraph import CodeGraphClient
```

## 6. httpx.AsyncClient 관리

### 문제
```python
# ❌ 매번 생성 (비효율)
async def search():
    client = httpx.AsyncClient()
    response = await client.post(...)
    # close 안함 → 리소스 누수
```

### 해결
```python
# ✅ 재사용 + 종료 훅
class CodeGraphClient:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url="...")

    async def aclose(self):
        await self.client.aclose()

# FastAPI 통합
@app.on_event("startup")
async def startup():
    app.state.client = CodeGraphClient()

@app.on_event("shutdown")
async def shutdown():
    await app.state.client.aclose()
```

## 7. State 필드 불일치

### 문제
```python
# ❌ 노드에서 세팅, routing에서도 판단 (이중 로직)
def node(state):
    state.enough_context = True
    return state

def routing(state):
    if state.enough_context:  # 노드 결과 신뢰
        return "finish"
    if check_heuristic(state):  # 또 다른 판단
        return "finish"
```

### 해결
```python
# ✅ 한 곳에서만 판단 (routing)
def node(state):
    # 상태만 업데이트
    return state

def routing(state):
    # 판단 로직 한 곳에만
    if check_heuristic(state):
        return "finish"
    return "continue"
```

## 8. Enum 비교

### 문제
```python
# ❌ 문자열로 비교
if intent.strategy == "graph":  # Enum과 str 비교
    ...
```

### 해결
```python
# ✅ Enum으로 비교
if intent.strategy == SearchStrategy.GRAPH:
    ...

# 또는 .value로 변환 후 비교
if intent.strategy.value == "graph":
    ...
```

## 9. codegraph API 스펙 불일치

### 문제
```python
# ❌ copilot이 보내는 형식 ≠ codegraph가 받는 형식
await client.post("/search", json={
    "query": "...",
    "strategy": "graph",  # codegraph는 이 필드 모름
})
```

### 해결
```python
# ✅ 먼저 수동 테스트로 확인
import httpx
client = httpx.AsyncClient()
response = await client.post("http://localhost:8000/search", json={
    "query": "test",
    "repo_ids": ["repo1"],
    "limit": 5
})
print(response.json())  # 실제 응답 확인

# ✅ codegraph API 스펙에 맞춤
# 필요하면 codegraph 수정
```

## 10. text 필드 누락

### 문제
```python
# ❌ SearchResult에 text="" (빈 문자열)
SearchResult(
    ...,
    text="",  # LLM이 설명할 내용 없음
)
```

### 해결
```python
# ✅ codegraph에서 text 채워서 반환
# semantica-codegraph/apps/mcp_server/service.py
chunk = self.chunk_store.get_chunk(repo_id, candidate.chunk_id)
result = {
    ...,
    "text": chunk.text if chunk else "",  # ⚠️ 필수
}
```

## 체크리스트 (구현 전)

- [ ] SearchStrategy는 한 곳에만 정의
- [ ] Enum 전송 시 .value 변환
- [ ] results 대신 get_top_k 사용
- [ ] Field + default_factory
- [ ] 절대 import 사용
- [ ] httpx.AsyncClient 재사용 + aclose
- [ ] routing에서만 판단
- [ ] Enum으로 비교 (문자열 X)
- [ ] codegraph API 스펙 확인
- [ ] SearchResult.text 채우기

## 디버깅 팁

### Enum 직렬화 에러
```
TypeError: Object of type SearchStrategy is not JSON serializable
```
→ `.value` 추가

### 정렬 안된 results
```
results[0].score < results[1].score  # 역순?
```
→ `get_top_k` 사용

### 상대 import 에러
```
ImportError: attempted relative import beyond top-level package
```
→ 절대 import로 변경

### httpx 연결 누수
```
ResourceWarning: unclosed <socket.socket>
```
→ `aclose()` 호출 확인
