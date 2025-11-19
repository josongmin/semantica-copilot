# CodeGraph API 어댑터

## API 스펙 차이

### codegraph API (실제)

**엔드포인트**: `POST /hybrid/search`

**요청**:
```json
{
  "query": "HybridRetriever",
  "k": 20,
  "location_ctx": {
    "repo_id": "semantica-codegraph",
    "file_path": "",
    "line": 0,
    "column": 0
  },
  "backend_hints": ["lexical", "semantic", "graph", "fuzzy"],
  "session_id": "optional-session-id"
}
```

**응답**:
```json
{
  "query": "HybridRetriever",
  "k": 20,
  "candidates": [
    {
      "candidate_id": "cand-abc123",
      "chunk_id": "chunk-abc123",
      "doc_id": "chunk-abc123",
      "file_path": "src/search/adapters/retriever/hybrid_retriever.py",
      "span": [15, 0, 45, 1],
      "snippet": "class HybridRetriever:...",
      "language": "python",
      "symbol_name": "HybridRetriever",
      "node_id": "node-xyz",
      "final_score": 0.85,
      "scores": {
        "lexical": 0.75,
        "semantic": 0.82,
        "graph": 0.88,
        "fuzzy": 0.65
      },
      "extra_features": {
        "has_span": 1.0,
        "tfidf_score": 0.72
      }
    }
  ]
}
```

### copilot 기대 형식

**SearchResult**:
```python
{
  "repo_id": str,        # ⚠️ 추가 필요
  "chunk_id": str,
  "file_path": str,
  "line_start": int,     # ⚠️ span[0]
  "line_end": int,       # ⚠️ span[2]
  "text": str,           # ⚠️ 없음 (빈 문자열)
  "score": float,
  "scores": dict         # ⚠️ features
}
```

## 변환 로직

CodeGraphClient._search_http에서 구현됨:

```python
# 요청 변환 (새로운 /hybrid/search API)
{
    "query": query,
    "k": limit,
    "location_ctx": {
        "repo_id": repo_id,  # repo_ids 순회
        "file_path": "",
        "line": 0,
        "column": 0
    },
    "backend_hints": ["lexical", "semantic", "graph", "fuzzy"]  # weights 기반
}

# 응답 변환
SearchResult(
    repo_id=repo_id,
    chunk_id=candidate["chunk_id"],
    file_path=candidate["file_path"],
    line_start=candidate["span"][0],   # span → line_start
    line_end=candidate["span"][2],     # span → line_end
    text=candidate.get("snippet", ""),  # ✅ snippet을 text로 사용
    score=candidate["final_score"],
    scores={
        "lexical": candidate["scores"].get("lexical"),
        "semantic": candidate["scores"].get("semantic"),
        "graph": candidate["scores"].get("graph"),
        "fuzzy": candidate["scores"].get("fuzzy")
    }
)
```

## text 필드 해결

### 현재 상태
- `/hybrid/search`는 `snippet` 필드 반환 (요약된 텍스트)
- 전체 내용이 필요하면 `/hybrid/chunks` API 사용
- copilot은 `snippet`을 `text`로 사용

### 전체 내용이 필요한 경우

```python
# CodeGraphClient에 메서드 추가 가능
async def get_chunk_content(self, chunk_id: str) -> str:
    """Chunk 전체 내용 가져오기"""
    response = await self.client.post(
        "/hybrid/chunks",
        json={
            "chunk_ids": [chunk_id],
            "include_source": True
        }
    )
    data = response.json()
    if data["chunks"]:
        return data["chunks"][0]["content"]
    return ""
```

## 새로운 API 기능

### 지원되는 파라미터
- `location_ctx`: 현재 위치 컨텍스트 (선택적)
- `backend_hints`: 활성화할 백엔드 목록
- `session_id`: 세션별 설정 관리
- `intent`: 검색 의도 ("question_answering", "code_exploration" 등)

### 추가 API
- `POST /hybrid/chunks`: 청크 전체 내용 조회
- `POST /hybrid/graph`: 그래프 확장
- `POST /hybrid/symbols`: 심볼 검색
- `GET /hybrid/explain/{candidate_id}`: 후보 설명
- `POST /hybrid/session/preferences`: 세션 설정

