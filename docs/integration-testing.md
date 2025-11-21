# 연동 테스트 가이드

## 준비사항

### 1. codegraph API 실행

```bash
cd ../semantica-codegraph
python -m apps.api.main
# http://localhost:8000 에서 실행됨
```

### 2. 저장소 인덱싱 (필수)

최소 1개 이상의 저장소가 인덱싱되어 있어야 합니다:

```bash
cd ../semantica-codegraph
python -m apps.cli.main index /path/to/repo --repo-id test-repo
```

## 연동 테스트 실행

### 자동 스크립트

```bash
cd semantica-copilot
./scripts/run_integration_test.sh
```

### 수동 실행

```bash
cd semantica-copilot
python tests/integration_test.py
```

## 테스트 내용

### 1. codegraph API 연결 확인
- GET http://localhost:8000/

### 2. 저장소 목록 조회
- GET http://localhost:8000/api/repos/

### 3. 검색 API 직접 호출
- POST http://localhost:8000/hybrid/search
- 요청 형식 확인
- 응답 형식 확인
- **text 필드 확인** (현재 없음)

### 4. CodeGraphClient 테스트
- search_with_intent 호출
- 응답 변환 (span → line_start/line_end)
- 응답 변환 (features → scores)

### 5. Agent 그래프 테스트
- 전체 플로우 실행
- 2단계 검색 확인
- 답변 생성 확인

## 예상 출력

```
🚀 🚀 🚀 ... Semantica Copilot - 연동 테스트

================================================================================
1. codegraph API 연결 테스트
================================================================================
✅ codegraph 실행 중: {'status': 'ok', 'service': 'semantica-codegraph'}

================================================================================
2. 저장소 목록 조회
================================================================================
✅ 저장소 1개:
  - semantica-codegraph: Semantica Codegraph (245 nodes)

================================================================================
3. 검색 API 직접 테스트
================================================================================
테스트 repo: semantica-codegraph
✅ 검색 성공: 5개 결과

첫 번째 결과:
  chunk_id: chunk-abc123
  file_path: src/search/adapters/retriever/hybrid_retriever.py
  span: [15, 0, 45, 1]
  score: 0.85
  features: ['lexical_score', 'semantic_score', 'graph_score', 'fuzzy_score', 'total_score']
  text 필드: False ❌

================================================================================
4. CodeGraphClient 테스트
================================================================================
테스트 repo: semantica-codegraph
✅ CodeGraphClient 검색 성공: 5개 결과

첫 번째 결과:
  repo_id: semantica-codegraph
  file_path: src/search/adapters/retriever/hybrid_retriever.py
  line_start: 15
  line_end: 45
  score: 0.850
  text: 0 chars ⚠️ 빈 문자열

================================================================================
5. Agent 그래프 테스트
================================================================================
테스트 repo: semantica-codegraph
그래프 실행 중...
✅ 그래프 실행 완료:
  search_steps: 2
  total_results: 10
  answer: 1234 chars

답변 미리보기:
# class 검색 결과

총 10개 결과 (상위 5개 표시)

## 1. src/search/adapters/retriever/hybrid_retriever.py:15
**Score**: 0.850
...

✅ ✅ ✅ ... 연동 테스트 완료!
```

## 알려진 이슈

### text 필드 없음

codegraph API 응답에 text 필드가 포함되지 않습니다.

**현재 상태**:
- copilot은 text를 빈 문자열로 처리
- 답변에서 "_⚠️ 코드 내용 없음_" 표시

**해결 방법**:

#### Option 1: codegraph API 수정
```python
# semantica-codegraph/apps/api/routes/search.py

# 검색 결과 생성 시
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
```

#### Option 2: copilot에서 추가 호출
```python
# CodeGraphClient에 메서드 추가
async def get_chunk_text(self, repo_id: str, chunk_id: str) -> str:
    # chunk store API 호출 (구현 필요)
    ...
```

**권장**: Option 1 (codegraph API 수정)

## 트러블슈팅

### codegraph 연결 실패
```bash
# codegraph 실행 확인
curl http://localhost:8000/

# 없으면 실행
cd ../semantica-codegraph
python -m apps.api.main
```

### 저장소 없음
```bash
# 인덱싱
cd ../semantica-codegraph
python -m apps.cli.main index /path/to/repo --repo-id test-repo
```

### API 스펙 불일치
- copilot이 codegraph API 스펙에 맞게 어댑터 구현됨
- text 필드만 제외하고 모두 변환됨

## 다음 단계

연동 테스트 완료 후:
1. text 필드 추가 (codegraph 수정 or copilot 확장)
2. 실제 쿼리로 품질 확인
3. Phase 3 진행
