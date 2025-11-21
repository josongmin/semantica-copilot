# 사용 예시

## CLI 사용법

### 기본 검색
```bash
python -m semantica_copilot.cli.main "HybridRetriever" semantica-codegraph
```

### 출력 예시
```
2025-11-19 12:00:00 - __main__ - INFO - Query: HybridRetriever
2025-11-19 12:00:00 - __main__ - INFO - Repo IDs: ['semantica-codegraph']
2025-11-19 12:00:00 - __main__ - INFO - Search intent: strategy=hybrid, limit=10
2025-11-19 12:00:00 - __main__ - INFO - Searching...
2025-11-19 12:00:00 - __main__ - INFO - Found 5 results

================================================================================
검색 결과: 5개

[1] src/search/adapters/retriever/hybrid_retriever.py:15
Score: 0.950
Scores: {'lexical': 0.85, 'semantic': 0.90, 'graph': 0.88, 'fuzzy': 0.72}
Preview:
class HybridRetriever:
    """하이브리드 검색"""
    ...
================================================================================
```

## FastAPI 사용법

### 서버 실행
```bash
# Terminal 1: codegraph
cd ../semantica-codegraph
python -m apps.api.main

# Terminal 2: copilot
cd semantica-copilot
python -m semantica_copilot.apps.server.main
# http://localhost:8001
```

### API 호출

**curl**:
```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "HybridRetriever는 어떻게 동작하나?",
    "repo_ids": ["semantica-codegraph"]
  }'
```

**httpie**:
```bash
pip install httpie

http POST localhost:8001/chat \
  query="UserService 클래스 설명" \
  repo_ids:='["repo1"]'
```

**Python**:
```python
import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/chat",
            json={
                "query": "HybridRetriever",
                "repo_ids": ["semantica-codegraph"]
            }
        )
        data = response.json()
        print(data["answer"])

asyncio.run(test())
```

### 응답 형식

```json
{
  "answer": "# HybridRetriever 검색 결과\n\n총 15개 결과 (상위 5개 표시)\n\n## 1. src/search/adapters/retriever/hybrid_retriever.py:15\n**Score**: 0.950\n...",
  "search_steps": 2,
  "total_results": 15,
  "error": null
}
```

## Phase별 동작 차이

### Phase 0: 함수 체인
```python
# 단순 함수 호출
result = await simple_agent(query, repo_ids)
```
- 검색 1회
- 템플릿 답변

### Phase 1: LangGraph 기본
```
intent_plan → run_search → generate → END
```
- 검색 1회
- LangGraph 사용

### Phase 2: Search Loop
```
intent_plan → search_plan ←───┐
                 ↓             │
             run_search        │
                 ↓             │
             aggregate ────────┘
                 ↓
             generate → END
```
- 검색 2회 (Step 0: Hybrid, Step 1: Graph)
- 조건부 루프
- 단계별 전략

## 검색 전략별 예시

### Hybrid Search (Step 0)
```python
intent = CodeSearchIntent(
    entities=["UserService"],
    strategy=SearchStrategy.HYBRID,
    limit=20
)
```
→ Lexical + Semantic + Graph + Fuzzy 조합

### Graph Search (Step 1)
```python
intent = CodeSearchIntent(
    keywords=["caller", "usage"],
    strategy=SearchStrategy.GRAPH,
    graph_depth=2,
    edge_types=["calls", "uses"],
    limit=10
)
```
→ 관계 기반 확장

### Semantic Search (Step 2)
```python
intent = CodeSearchIntent(
    keywords=["type", "interface"],
    strategy=SearchStrategy.SEMANTIC,
    limit=10
)
```
→ 의미론적 유사도 기반

## 트러블슈팅

### codegraph 연결 실패
```bash
# codegraph 실행 확인
curl http://localhost:8000/health

# 또는 레포 목록 확인
curl http://localhost:8000/repositories
```

### text 필드 비어있음
```python
# semantica-codegraph/apps/mcp_server/service.py 수정
chunk = self.chunk_store.get_chunk(repo_id, candidate.chunk_id)
result["text"] = chunk.text if chunk else ""
```

### 검색 결과 없음
```bash
# 레포 인덱싱 확인
cd ../semantica-codegraph
python -m apps.cli.main index /path/to/repo --repo-id repo1
```

## 다음 단계

Phase 3에서는:
- LLM 기반 search_plan (동적 intent 생성)
- LLM 기반 generate_answer (정교한 설명)
- Memory 통합 (대화 이력)
- Streaming 응답 (SSE)
