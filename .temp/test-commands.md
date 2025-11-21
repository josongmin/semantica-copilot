# 연동 테스트 실행 가이드

## codegraph 수정 완료

### ✅ 수정된 파일
- `semantica-codegraph/apps/api/routes/search.py`
  - SearchResult에 `text: str` 필드 추가
  - search_code 핸들러에서 chunk_store.get_chunk()로 text 가져오기

## 실행 방법

### 1. codegraph API 서버 실행 (별도 터미널)

```bash
cd /Users/songmin/Documents/code-jo/semantica/semantica-codegraph
python -m apps.api.main
```

**확인**:
- 서버가 http://localhost:8000 에서 실행됨
- "Application startup complete" 메시지 확인

### 2. API 엔드포인트 테스트

```bash
# 터미널 2에서

# 루트 확인
curl http://localhost:8000/
# {"status": "ok", "service": "semantica-codegraph"}

# 저장소 목록
curl http://localhost:8000/api/repos/
# [{"repo_id": "...", ...}]

# 검색 API (저장소가 있는 경우)
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "class",
    "repo_id": "semantica-codegraph",
    "k": 5
  }'
```

### 3. copilot 연동 테스트

```bash
cd /Users/songmin/Documents/code-jo/semantica/semantica-copilot
python tests/integration_test.py
```

**기대 결과**:
```
✅ codegraph 실행 중
✅ 저장소 1개
✅ 검색 성공: 5개 결과
  text 필드: True ✅
✅ CodeGraphClient 검색 성공
  text: 123 chars ✅
✅ 그래프 실행 완료
```

## 만약 저장소가 없다면

### 인덱싱 필요

```bash
cd /Users/songmin/Documents/code-jo/semantica/semantica-codegraph

# semantica-codegraph 자체를 인덱싱
python -m apps.cli.main index . --repo-id semantica-codegraph --name "Semantica Codegraph"
```

## 트러블슈팅

### 404 Not Found 계속 발생

원인: 다른 서버가 8000 포트 사용 중

```bash
# 8000 포트 사용 프로세스 확인
lsof -ti:8000

# 또는 강제 종료 후 재실행
pkill -f "apps.api.main"
cd /Users/songmin/Documents/code-jo/semantica/semantica-codegraph
python -m apps.api.main
```

### router가 등록 안됨

```bash
# main.py 확인
grep -A 3 "include_router" apps/api/main.py
```
