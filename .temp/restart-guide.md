# CodeGraph 재시작 가이드

## 현재 상황
- 8000 포트에 프로세스(PID 28185) 실행 중
- text 필드 추가 수정 완료
- 재시작 필요

## 재시작 방법

### Option 1: 수동 재시작 (권장)

**사용자가 직접**:
1. 현재 실행 중인 터미널에서 `Ctrl+C`로 종료
2. 다시 실행:
   ```bash
   cd /Users/songmin/Documents/code-jo/semantica/semantica-codegraph
   python -m apps.api.main
   ```

### Option 2: 강제 종료 후 재시작

```bash
# 프로세스 종료
kill 28185

# 또는
pkill -f "apps.api.main"

# 재시작
cd /Users/songmin/Documents/code-jo/semantica/semantica-codegraph
python -m apps.api.main
```

## 재시작 후 확인

```bash
# 1. 서버 실행 확인
curl http://localhost:8000/
# {"status": "ok", "service": "semantica-codegraph"}

# 2. repos API
curl http://localhost:8000/api/repos/
# [...repositories...]

# 3. search API (text 필드 포함 확인)
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "class",
    "repo_id": "semantica-codegraph",
    "k": 3
  }' | python -m json.tool
```

## 연동 테스트 실행

codegraph 재시작 후:

```bash
cd /Users/songmin/Documents/code-jo/semantica/semantica-copilot
python tests/integration_test.py
```

## 기대 결과

```
✅ codegraph 실행 중
✅ 저장소 1개
✅ 검색 성공: 5개 결과
  text 필드: True ✅
✅ CodeGraphClient 검색 성공
  text: 150 chars ✅
✅ 그래프 실행 완료
```

