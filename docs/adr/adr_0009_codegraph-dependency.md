# ADR 0009 – Copilot의 Codegraph 의존성 공식화

## Context

LLM 코드 편집은 Codegraph 인덱스 없이는 구조적 정보를 얻을 수 없다.

## Decision

Copilot의 모든 core 기능은 Codegraph 인덱스를 필수로 사용한다.

Copilot 단독 모드는 지원하지 않는다.

## Alternatives

### Codegraph 없이 Copilot 단독 사용
- 검색 실패, hallucination 다수 발생

## Consequences

Copilot 품질은 항상 일정하게 유지되고, Codegraph 업데이트는 Copilot에 즉시 반영됨.
