# 연동 테스트 계획

## 발견된 문제

### 1. API 엔드포인트 경로
- copilot 기대: `POST /search`
- codegraph 실제: `POST /api/search/`

### 2. SearchResult 스펙 불일치

**codegraph API 응답**:
```python
{
    "chunk_id": str,
    "file_path": str,
    "span": [start_line, start_col, end_line, end_col],
    "score": float,
    "features": dict
}
```

**copilot 기대**:
```python
{
    "repo_id": str,        # ⚠️ codegraph 응답에 없음
    "chunk_id": str,
    "file_path": str,
    "line_start": int,     # ⚠️ codegraph는 span
    "line_end": int,       # ⚠️ codegraph는 span
    "text": str,           # ⚠️ codegraph 응답에 없음
    "score": float,
    "scores": dict         # ⚠️ codegraph는 features
}
```

### 3. SearchRequest 스펙 불일치

**codegraph API 요청**:
```python
{
    "query": str,
    "repo_id": str,        # ⚠️ 단일 repo_id (copilot은 repo_ids 리스트)
    "k": int,
    "weights": dict
}
```

**copilot이 보내는 형식**:
```python
{
    "query": str,
    "repo_ids": List[str], # ⚠️ 리스트
    "limit": int,          # ⚠️ k가 아닌 limit
    "strategy": str,
    "weights": dict
}
```

## 해결 방안

### Option 1: copilot 어댑터 레이어 추가 (빠름)

```python
# CodeGraphClient._search_http 수정
async def _search_http(self, query, repo_ids, limit, ...):
    # 여러 repo에 대해 반복 호출
    all_results = []
    for repo_id in (repo_ids or []):
        response = await self.client.post(
            "/api/search/",  # ✅ 경로 수정
            json={
                "query": query,
                "repo_id": repo_id,  # ✅ 단일 repo_id
                "k": limit,          # ✅ limit → k
                "weights": weights,
            }
        )
        data = response.json()
        
        # 응답 변환
        for item in data["results"]:
            result = SearchResult(
                repo_id=repo_id,  # ✅ 추가
                chunk_id=item["chunk_id"],
                file_path=item["file_path"],
                line_start=item["span"][0],  # ✅ span → line_start
                line_end=item["span"][2],    # ✅ span → line_end
                text="",  # ⚠️ 나중에 채우기
                score=item["score"],
                scores=item["features"]  # ✅ features → scores
            )
            all_results.append(result)
    
    return all_results
```

### Option 2: codegraph API 수정 (정석)

```python
# semantica-codegraph/apps/api/routes/search.py 수정

class SearchResult(BaseModel):
    repo_id: str           # ✅ 추가
    chunk_id: str
    file_path: str
    line_start: int        # ✅ span 대신
    line_end: int          # ✅ span 대신
    text: str              # ✅ 추가
    score: float
    scores: dict           # ✅ features 대신

# search_code 핸들러에서
chunk = bootstrap.chunk_store.get_chunk(request.repo_id, c.chunk_id)
results.append(
    SearchResult(
        repo_id=request.repo_id,
        chunk_id=c.chunk_id,
        file_path=c.file_path,
        line_start=c.span[0],
        line_end=c.span[2],
        text=chunk.text if chunk else "",  # ✅ text 추가
        score=c.features.get("total_score", 0.0),
        scores=c.features  # ✅ features → scores
    )
)
```

## 결정

**Option 1 채택** (copilot 어댑터)
- 이유: codegraph 수정 없이 빠르게 연동
- copilot이 codegraph API에 맞춤
- text는 일단 빈 문자열로 두고, 나중에 개선

## 수정 작업

1. CodeGraphClient._search_http 수정
   - 경로: `/search` → `/api/search/`
   - repo_ids (list) → repo_id (str) 반복
   - limit → k
   - span → line_start, line_end
   - features → scores

2. 테스트 스크립트 작성
   - 실제 API 호출 확인
   - text 필드 없어도 동작하는지 확인

