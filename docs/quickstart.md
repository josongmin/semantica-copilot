# Quick Start Guide

## Phase 0: 함수 체인 검증

### 1. 설치

```bash
cd semantica-copilot
pip install -e .
```

### 2. semantica-codegraph 실행 (필수)

별도 터미널에서:

```bash
cd ../semantica-codegraph
python -m apps.api.main
# http://localhost:8000 에서 실행됨
```

### 3. CLI 테스트

```bash
# 기본 사용
python -m semantica_copilot.cli.main "UserService" repo1

# 실제 예시 (semantica-codegraph 레포 검색)
python -m semantica_copilot.cli.main "HybridRetriever" semantica-codegraph
```

### 4. 검증 항목

- [ ] codegraph API 연결 확인
- [ ] SearchResult.text 필드 확인
- [ ] 검색 결과 품질 확인
- [ ] strategy별 차이 확인

## 예상 출력

```
2025-01-01 12:00:00 - __main__ - INFO - Query: HybridRetriever
2025-01-01 12:00:00 - __main__ - INFO - Repo IDs: ['semantica-codegraph']
2025-01-01 12:00:00 - __main__ - INFO - Search intent: strategy=hybrid, limit=10
2025-01-01 12:00:00 - __main__ - INFO - Searching...
2025-01-01 12:00:00 - __main__ - INFO - Found 5 results

================================================================================
검색 결과: 5개

[1] src/search/adapters/retriever/hybrid_retriever.py:15
Score: 0.950
Scores: {'lexical': 0.85, 'semantic': 0.90, 'graph': 0.88, 'fuzzy': 0.72}
Preview:
class HybridRetriever:
    """하이브리드 검색"""
    def __init__(self, ...):
        ...
================================================================================
```

## 다음 단계

### text 필드 확인

만약 `⚠️ text 필드 비어있음` 메시지가 나오면:

```python
# semantica-codegraph/apps/mcp_server/service.py 수정
chunk = self.chunk_store.get_chunk(repo_id, candidate.chunk_id)
result = {
    ...,
    "text": chunk.text if chunk else "",  # ✅ 추가
}
```

### Phase 1로 진행

```bash
# LangGraph 노드 구현
src/semantica_copilot/agent/nodes/
├── intent_plan.py
├── search_plan.py
├── run_search.py
├── aggregate_context.py
└── generate_answer.py
```

## 트러블슈팅

### 1. ModuleNotFoundError

```bash
pip install -e .
```

### 2. Connection refused

```bash
# codegraph가 실행 중인지 확인
curl http://localhost:8000/health
```

### 3. Enum 직렬화 에러

→ 코드에 이미 `.value` 변환 적용됨

### 4. 검색 결과 없음

```bash
# 레포가 인덱싱되어 있는지 확인
curl http://localhost:8000/repositories
```

