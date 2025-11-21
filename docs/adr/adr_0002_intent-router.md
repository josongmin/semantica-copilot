# ADR 0002 – Intent Router 설계

## Context

모든 요청이 전체 에이전트 플래너로 전달되면 비효율적이며 비용 증가.

요청의 목적을 빠르게 분류해야 한다.

## Decision

Intent Router는 경량 모델을 사용해 다음 intent로 분류한다.

- search
- read
- modify
- create
- explain
- refactor
- test 작성
- multi-step planning

## Alternatives

### 모든 요청을 플래너(Large Model)로 전달
- 비효율적, 비용 증가

### 규칙 기반 intent 분류
- 정확도·속도 모두 떨어짐

## Consequences

Copilot의 처리량 증가, 빠른 반응 시간 확보.
