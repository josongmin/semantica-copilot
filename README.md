# Semantica Copilot

LangGraph 기반 코드 이해 에이전트

## 개요

semantica-codegraph의 고도화된 하이브리드 검색을 활용하여,
동적 검색 전략과 반복적 컨텍스트 수집으로 정확한 코드 이해를 제공합니다.

## 특징

- **동적 검색 전략**: LLM이 단계별 검색 계획 수립
- **반복 검색**: 다단계 검색으로 컨텍스트 누적
- **하이브리드 검색**: Lexical + Semantic + Graph + Fuzzy + Fusion
- **그래프 활용**: 코드 관계 기반 확장

## 아키텍처

- **State**: Pydantic 기반 타입 안전 State
- **Tools**: semantica-codegraph 통합 클라이언트
- **Agent**: LangGraph 기반 multi-step retrieval

## 설치

```bash
cd semantica-copilot
pip install -e .
```

## 사용법

### CLI (Phase 0)

```bash
python -m semantica_copilot.cli query "UserService는 뭐하는 클래스?"
```

### FastAPI (Phase 1)

```bash
uvicorn semantica_copilot.apps.server.main:app --reload
```

## 개발

```bash
# 의존성 설치
pip install -e ".[dev]"

# 테스트
pytest

# 포맷팅
black src/ tests/
ruff src/ tests/
```

## 프로젝트 구조

```
src/semantica_copilot/
├── agent/           # LangGraph 에이전트
│   ├── state.py    # State 정의
│   ├── graph.py    # 그래프 구성
│   └── nodes/      # 노드 구현
├── tools/          # 외부 도구
│   └── codegraph.py
├── prompts/        # 프롬프트 템플릿
└── apps/           # 애플리케이션
    └── server/     # FastAPI 서버
```

## 문서

- `docs/architecture-proposal.md`: 전체 아키텍처
- `docs/final-decisions.md`: 최종 설계 결정
- `docs/common-pitfalls.md`: 흔한 실수 방지
