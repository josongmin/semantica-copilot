# ADR 0003 – Planner 구조 (High-Level → Search Plan → Diff Plan)

## Context

LLM이 직접 파일을 고르고 diff를 생성하면 구조적 오류가 발생함.

분리된 계획 단계를 거쳐야 안정적이다.

## Decision

Planner를 세 단계로 분리한다.

1. **High-level plan**: 작업 요약
2. **Search plan**: 어떤 파일·심볼·라인을 찾아야 하는지 정의
3. **Diff plan**: 변경할 블록의 범위를 정의하여 Diff Generator로 전달

## Alternatives

### one-shot diff 생성
- Hallucination 증가

### 전체 파일 재작성
- Hallucination 증가

## Consequences

Claude Code의 안정적 코드 편집 루프를 복제할 수 있게 됨.
