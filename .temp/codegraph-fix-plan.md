# CodeGraph API 수정 작업 계획

## 현재 상황 분석

### 문제 확인
- codegraph가 8000 포트에서 실행 중
- 하지만 `/api/repos/`, `/api/search/` 엔드포인트가 404
- OpenAPI에는 `/api/chat`만 존재
- 실제 API routes는 정의되어 있지만 등록 안됨

### 원인 추정
1. 다른 서버가 실행 중 (MCP 서버?)
2. 또는 API routes가 제대로 import 안됨

## 작업 계획

### Phase 1: 현재 상태 확인 (5분)
1. ✅ 실행 중인 서버 확인
2. ✅ apps/api/main.py 확인
3. ✅ routes 파일 확인

### Phase 2: API 엔드포인트 구현 (30분)

#### 2-1. repos.py 수정
```python
# semantica-codegraph/apps/api/routes/repos.py

@router.get("/", response_model=list[RepoResponse])
async def list_repositories():
    """저장소 목록 조회"""
    try:
        repos = bootstrap.repo_store.list_all()
        return [RepoResponse(...) for repo in repos]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 2-2. search.py 수정 (text 필드 추가)
```python
# semantica-codegraph/apps/api/routes/search.py

class SearchResult(BaseModel):
    chunk_id: str
    file_path: str
    span: list[int]
    score: float
    features: dict
    text: str  # ✅ 추가

@router.post("/", response_model=SearchResponse)
async def search_code(request: SearchRequest):
    # 검색 실행
    candidates = retriever.retrieve(...)
    
    # 결과 변환 (text 포함)
    results = []
    for c in candidates:
        # ✅ chunk_store에서 text 가져오기
        chunk = bootstrap.chunk_store.get_chunk(request.repo_id, c.chunk_id)
        
        results.append(
            SearchResult(
                chunk_id=c.chunk_id,
                file_path=c.file_path,
                span=list(c.span),
                score=c.features.get("total_score", 0.0),
                features=c.features,
                text=chunk.text if chunk else ""  # ✅ 추가
            )
        )
    
    return SearchResponse(...)
```

### Phase 3: 연동 테스트 (10분)

```bash
# 1. codegraph 재시작
cd semantica-codegraph
python -m apps.api.main

# 2. 연동 테스트
cd semantica-copilot
python tests/integration_test.py
```

### Phase 4: 결과 검증 (5분)
- [ ] /api/repos/ 동작
- [ ] /api/search/ 동작
- [ ] text 필드 포함
- [ ] copilot 정상 동작

## 상세 작업 내역

### 1. repos.py 확인 및 수정

**파일**: `semantica-codegraph/apps/api/routes/repos.py`

**작업**:
- `list_repositories()` 함수 확인
- `bootstrap.repo_store.list_all()` 호출 확인
- 에러 핸들링 추가

### 2. search.py 수정 (text 추가)

**파일**: `semantica-codegraph/apps/api/routes/search.py`

**작업**:
- `SearchResult` 모델에 `text: str` 필드 추가
- `search_code()` 핸들러에서:
  ```python
  for c in candidates:
      chunk = bootstrap.chunk_store.get_chunk(request.repo_id, c.chunk_id)
      results.append(SearchResult(
          ...,
          text=chunk.text if chunk else ""
      ))
  ```

### 3. main.py 확인

**파일**: `semantica-codegraph/apps/api/main.py`

**확인**:
- router 등록 확인
- `app.include_router(repos.router, prefix="/api/repos")`
- `app.include_router(search.router, prefix="/api/search")`

## 예상 결과

### 수정 전
```bash
curl http://localhost:8000/api/repos/
# 404 Not Found
```

### 수정 후
```bash
curl http://localhost:8000/api/repos/
# [{"repo_id": "...", "name": "...", ...}]

curl -X POST http://localhost:8000/api/search/ \
  -d '{"query": "test", "repo_id": "repo1", "k": 5}'
# {"results": [{"text": "actual code...", ...}]}
```

## 타임라인

- Phase 1: 5분 (확인)
- Phase 2: 30분 (구현)
- Phase 3: 10분 (테스트)
- Phase 4: 5분 (검증)

**총 예상 시간**: 50분

## 다음 단계

1. codegraph API 수정
2. 연동 테스트 실행
3. text 필드 동작 확인
4. copilot E2E 테스트
5. Phase 3 진행

