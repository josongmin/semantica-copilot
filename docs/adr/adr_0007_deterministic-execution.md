# ADR 0007 – Deterministic Execution (중간 질문 없음)

## Context

인터랙티브 에이전트는 reproducibility가 떨어지고 테스트가 불가능하다.

Copilot은 재실행 시 동일한 계획을 반복해야 한다.

## Decision

LangGraph 기반으로 deterministic node execution을 채택하며 "중간에 되묻기"를 금지한다.

모든 결정은 Planner 단계에서 확정된다.

## Alternatives

### 대화형 self-correcting loop
- 실행 경로 불확실, 브레이크포인트 설정 불가

## Consequences

Copilot은 테스트 가능한 안정된 워크플로우를 가지며, CI에서 자동 검증 가능.
