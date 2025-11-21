# 빠른 테스트 가이드

## 🚀 1분 테스트 (제일 빠름)

### 템플릿 모드 (지금 바로)
```bash
cd /Users/songmin/Documents/code-jo/semantica/semantica-copilot

# 간단한 E2E 테스트
python test_simple.py
```

**예상 결과**:
```
📝 템플릿 모드
================================================================================
Query: HybridRetriever는 무엇인가?
Repo: ['semantica-codegraph']
================================================================================

실행 중...

================================================================================
결과:
================================================================================
검색 단계: 2
총 결과: 15
답변 길이: 2199 chars

================================================================================
답변:
================================================================================
# HybridRetriever는 무엇인가? 검색 결과

총 15개 결과 (상위 5개 표시)

## 1. src/search/adapters/retriever/hybrid_retriever.py:18
...
```

### LLM 모드 (API Key 있으면)
```bash
# .env 파일에 API Key 설정 후
python test_simple.py --llm
```

## ⚡ 3분 테스트 (전체 확인)

### 1. 유닛 테스트 (30초)
```bash
pytest tests/ -v
# 13 passed 확인
```

### 2. 연동 테스트 (1분)
```bash
python tests/integration_test.py
# 5단계 성공 확인
```

### 3. FastAPI 테스트 (1분)
```bash
# Terminal 1: 서버 실행
python -m semantica_copilot.apps.server.main

# Terminal 2: API 호출
curl -X POST http://localhost:8001/chat \
  -d '{"query": "HybridRetriever", "repo_ids": ["semantica-codegraph"]}' \
  | jq -r '.answer' | head -30
```

## 📋 체크리스트

### 기본 동작 (LLM 없이)
- [ ] `pytest tests/ -v` → 13 passed
- [ ] `python tests/integration_test.py` → 5단계 성공
- [ ] `python test_simple.py` → 답변 생성
- [ ] FastAPI `/chat` → 200 OK

### LLM 동작 (API Key 있으면)
- [ ] `.env` 파일 생성 (USE_LLM=true)
- [ ] `python test_simple.py --llm` → LLM 답변
- [ ] 답변에 "요약", "상세 설명" 섹션 확인

## 💡 추천 테스트 순서

**1단계**: `python test_simple.py` (30초)
→ 기본 동작 확인

**2단계**: `python tests/integration_test.py` (1분)
→ 전체 연동 확인

**3단계**: FastAPI 서버 + curl (1분)
→ API 동작 확인

**4단계 (선택)**: `.env` + `python test_simple.py --llm`
→ LLM 모드 확인

## 🎯 예상 출력

### test_simple.py (템플릿 모드)
```
📝 템플릿 모드
================================================================================
검색 단계: 2
총 결과: 15
답변 길이: 2199 chars

# HybridRetriever는 무엇인가? 검색 결과
...
```

### test_simple.py (LLM 모드)
```
🤖 LLM 모드
================================================================================
검색 단계: 2
총 결과: 15
답변 길이: ~2500 chars

### 요약
HybridRetriever는 4가지 검색을 통합...

### 상세 설명
...
```

## ⚠️ 주의사항

### codegraph 실행 필수
```bash
# Terminal 1에서 실행 중이어야 함
cd /Users/songmin/Documents/code-jo/semantica/semantica-codegraph
python -m apps.api.main
# http://localhost:8000
```

### OPENAI_API_KEY (LLM 모드만)
```bash
# 없으면 자동으로 템플릿 모드로 폴백
# 로그에 "falling back to template" 메시지
```

---

**지금 바로 테스트**:
```bash
cd /Users/songmin/Documents/code-jo/semantica/semantica-copilot
python test_simple.py
```
