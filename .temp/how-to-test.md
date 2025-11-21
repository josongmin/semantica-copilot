# 테스트 방법

## 1. 기본 테스트 (LLM 없이) - 지금 바로 가능

### 1-1. 유닛 테스트
```bash
cd /Users/songmin/Documents/code-jo/semantica/semantica-copilot
python -m pytest tests/ -v
# 13 passed ✅
```

### 1-2. 연동 테스트
```bash
# Terminal 1: codegraph (이미 실행 중)
# http://localhost:8000

# Terminal 2: 연동 테스트
cd /Users/songmin/Documents/code-jo/semantica/semantica-copilot
python tests/integration_test.py
# 5단계 모두 성공 ✅
```

### 1-3. CLI 테스트 (템플릿 모드)
```bash
python -m semantica_copilot.cli.main "HybridRetriever" semantica-codegraph
```

### 1-4. FastAPI 테스트 (템플릿 모드)
```bash
# Terminal 3: copilot 서버 실행
python -m semantica_copilot.apps.server.main
# http://localhost:8001

# Terminal 4: API 호출
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "HybridRetriever는 어떻게 동작하나?",
    "repo_ids": ["semantica-codegraph"]
  }' | python -m json.tool
```

## 2. LLM 테스트 (OPENAI_API_KEY 필요)

### 2-1. .env 파일 생성
```bash
cd /Users/songmin/Documents/code-jo/semantica/semantica-copilot

cat > .env << 'EOF'
USE_LLM=true
OPENAI_API_KEY=sk-proj-your-actual-key-here
LLM_MODEL=gpt-4-turbo-preview
LLM_TEMPERATURE=0.1
CODEGRAPH_BASE_URL=http://localhost:8000
EOF
```

### 2-2. 서버 재시작 (LLM 모드)
```bash
# .env 로드됨
python -m semantica_copilot.apps.server.main
```

### 2-3. LLM 답변 테스트
```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "HybridRetriever는 어떻게 동작하나?",
    "repo_ids": ["semantica-codegraph"]
  }' | python -m json.tool
```

**기대 결과** (LLM 모드):
```json
{
  "answer": "### 요약\nHybridRetriever는 Lexical, Semantic, Graph, Fuzzy 4가지 검색을 통합하여...\n\n### 상세 설명\n1. 병렬 검색: 4가지 방식을 동시에 실행\n...",
  "search_steps": 2,
  "total_results": 15
}
```

## 3. 실제 쿼리 테스트 (추천)

### 3-1. 간단한 쿼리
```bash
curl -X POST http://localhost:8001/chat \
  -d '{"query": "class", "repo_ids": ["semantica-codegraph"]}' \
  | jq -r '.answer' | head -50
```

### 3-2. 구체적인 질문
```bash
curl -X POST http://localhost:8001/chat \
  -d '{"query": "HybridRetriever의 retrieve 메서드", "repo_ids": ["semantica-codegraph"]}' \
  | jq -r '.answer'
```

### 3-3. 관계 질문
```bash
curl -X POST http://localhost:8001/chat \
  -d '{"query": "Bootstrap에서 HybridRetriever는 어떻게 생성되나?", "repo_ids": ["semantica-codegraph"]}' \
  | jq -r '.answer'
```

## 4. 상세 디버깅 테스트

### 4-1. 로깅 레벨 변경
```bash
# 환경변수 설정
export LOG_LEVEL=DEBUG

# 서버 실행
python -m semantica_copilot.apps.server.main
```

### 4-2. 단계별 확인
```bash
# 1. 저장소 목록
curl http://localhost:8000/api/repos/ | jq 'length'

# 2. 검색 API 직접 호출
curl -X POST http://localhost:8000/api/search/ \
  -d '{"query": "class", "repo_id": "semantica-codegraph", "k": 5}' \
  | jq '.total'

# 3. copilot API 호출
curl -X POST http://localhost:8001/chat \
  -d '{"query": "class", "repo_ids": ["semantica-codegraph"]}' \
  | jq '{steps: .search_steps, results: .total_results, answer_len: (.answer | length)}'
```

## 5. Python 스크립트로 테스트

### test_simple.py
```python
import asyncio
import os

# LLM 모드로 설정
os.environ["USE_LLM"] = "true"
os.environ["OPENAI_API_KEY"] = "sk-..."  # 실제 키

from semantica_copilot.agent.state import AgentState
from semantica_copilot.agent.graph import get_graph

async def test():
    state = AgentState(
        query="HybridRetriever는 무엇인가?",
        repo_ids=["semantica-codegraph"]
    )

    graph = get_graph()
    result = await graph.ainvoke(state)

    print("=" * 80)
    print("답변:")
    print("=" * 80)
    print(result["answer"])
    print("=" * 80)
    print(f"검색 단계: {result['search_steps']}")
    print(f"총 결과: {len(result['accumulated_context'].results)}")

asyncio.run(test())
```

실행:
```bash
python test_simple.py
```

## 6. 빠른 테스트 체크리스트

### ✅ 기본 동작 (LLM 없이)
```bash
# 1. 유닛 테스트
pytest tests/ -v
# 13 passed 확인

# 2. 연동 테스트
python tests/integration_test.py
# 5단계 성공 확인

# 3. FastAPI 서버
python -m semantica_copilot.apps.server.main &
curl http://localhost:8001/health
curl -X POST http://localhost:8001/chat \
  -d '{"query": "test", "repo_ids": ["semantica-codegraph"]}'
```

### ✅ LLM 모드 (API Key 필요)
```bash
# 1. .env 생성
cat > .env << EOF
USE_LLM=true
OPENAI_API_KEY=sk-your-key
EOF

# 2. 서버 재시작
python -m semantica_copilot.apps.server.main

# 3. LLM 답변 확인
curl -X POST http://localhost:8001/chat \
  -d '{"query": "HybridRetriever 설명", "repo_ids": ["semantica-codegraph"]}' \
  | jq -r '.answer' | head -30
```

## 7. 예상 결과

### 템플릿 모드 (Phase 2)
```
# HybridRetriever 검색 결과

총 15개 결과 (상위 5개 표시)

## 1. src/search/adapters/retriever/hybrid_retriever.py:18
**Score**: 0.950
**Scores**: Lexical=0.85, Semantic=0.90, ...

```class HybridRetriever:
    ...
```
```

### LLM 모드 (Phase 3)
```
### 요약
HybridRetriever는 4가지 검색 방식을 통합한 하이브리드 검색 시스템으로,
Lexical, Semantic, Graph, Fuzzy 검색을 병렬 실행하여
정확도와 완전성을 모두 확보합니다.

### 상세 설명
1. **병렬 검색**: ThreadPoolExecutor로 4가지 검색 동시 실행
   - Lexical: BM25 기반 키워드
   - Semantic: 벡터 유사도
   - Graph: 관계 기반 확장
   - Fuzzy: 심볼명 매칭

2. **Fusion 전략**:
   - WeightedFusion, RRF, CombSum 조합
   - 각 검색 결과의 점수를 통합

...
```

## 트러블슈팅

### codegraph 연결 실패
```bash
curl http://localhost:8000/
# 안되면 재시작
cd /Users/songmin/Documents/code-jo/semantica/semantica-codegraph
python -m apps.api.main
```

### LLM 에러
```bash
# API Key 확인
echo $OPENAI_API_KEY

# .env 파일 확인
cat .env

# 로그 확인
# "LLM generation failed" 메시지 확인
# 폴백으로 템플릿 답변 생성됨
```

### 검색 결과 없음
```bash
# 저장소 인덱싱 확인
curl http://localhost:8000/api/repos/ | jq 'map(select(.total_nodes > 0))'
```

---

**지금 바로 테스트 가능합니다!**

가장 빠른 방법:
```bash
# Terminal에서
cd /Users/songmin/Documents/code-jo/semantica/semantica-copilot
python tests/integration_test.py
```
