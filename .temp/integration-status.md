# 연동 테스트 준비 완료

## 완료된 작업

### ✅ 1. API 스펙 차이 분석
- codegraph: `POST /api/search/`
- copilot 기대: `POST /search`
- → **수정 완료**: `/api/search/` 사용

### ✅ 2. 요청/응답 어댑터 구현
**요청 변환**:
- `repo_ids` (list) → `repo_id` (str) 반복 호출
- `limit` → `k`
- `weights` 그대로

**응답 변환**:
- `repo_id` 추가
- `span[0, 1, 2, 3]` → `line_start`, `line_end`
- `features` → `scores`
- `text` 빈 문자열 (⚠️)

### ✅ 3. 테스트 스크립트 생성
- `tests/integration_test.py` - 5단계 연동 테스트
- `scripts/run_integration_test.sh` - 자동 실행
- `scripts/start_codegraph.sh` - codegraph 실행

### ✅ 4. 문서 작성
- `docs/integration-testing.md` - 테스트 가이드
- `docs/codegraph-api-adapter.md` - API 스펙 변환

## 실행 방법

### 1. codegraph 실행 (필수)
```bash
cd ../semantica-codegraph
python -m apps.api.main
```

### 2. 저장소 인덱싱 확인
```bash
curl http://localhost:8000/api/repos/
# 최소 1개 repo 필요
```

### 3. 연동 테스트 실행
```bash
cd semantica-copilot
python tests/integration_test.py
```

## 테스트 내용

1. ✅ codegraph API 연결
2. ✅ 저장소 목록 조회
3. ✅ 검색 API 직접 호출
4. ✅ CodeGraphClient 테스트
5. ✅ Agent 그래프 실행

## 알려진 이슈

### text 필드 없음

**현재 상태**:
- copilot은 text를 빈 문자열로 처리
- 답변에 "_⚠️ 코드 내용 없음_" 표시
- 파일 경로와 라인만 표시 가능

**해결 방법**:
```python
# semantica-codegraph/apps/api/routes/search.py
chunk = bootstrap.chunk_store.get_chunk(request.repo_id, c.chunk_id)
results.append(
    SearchResult(
        ...,
        text=chunk.text if chunk else ""  # ✅ 추가
    )
)
```

**우선순위**: 높음 (답변 품질에 직접 영향)

### strategy 파라미터 미지원

**현재 상태**:
- copilot이 strategy 보내지만 codegraph는 무시
- 모든 검색이 기본 weights 사용

**해결 방법**:
- codegraph SearchRequest에 strategy 추가
- strategy 기반 weights 자동 조정

**우선순위**: 중간 (Phase 3에서 처리)

## 다음 액션

### 사용자가 할 일
1. codegraph 실행
   ```bash
   cd ../semantica-codegraph
   python -m apps.api.main
   ```

2. 연동 테스트 실행
   ```bash
   cd ../semantica-copilot
   python tests/integration_test.py
   ```

3. 결과 확인
   - text 필드 없음 확인
   - 기본 동작 확인

### 개발자가 할 일

1. **text 필드 추가** (권장)
   - codegraph API 수정
   - SearchResult에 text 필드 추가
   - chunk_store에서 text 가져오기

2. **연동 테스트 재실행**
   - text 포함된 응답 확인
   - 답변 품질 확인

3. **Phase 3 진행**
   - LLM 통합
   - Memory, Streaming

