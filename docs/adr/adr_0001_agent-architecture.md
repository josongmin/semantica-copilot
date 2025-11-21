# ADR 0001 – Copilot 전체 아키텍처 정의

## Context

LLM은 코드베이스 전 범위를 직접 다룰 수 없으며, Codegraph 인덱스를 통해 검색·대상 파일 선택·레퍼런스 찾기 등을 수행해야 한다.

Copilot은 Codegraph를 활용해 Plan → Search → Diff → Apply 루프를 수행하는 에이전트 계층임.

## Decision

Copilot 아키텍처를 다음 4계층으로 정의한다.

1. Intent Router
2. Planner (High-level → Search Plan → Diff Plan)
3. Executor (Search/Read/Write Tool 호출)
4. Diff Generator + Patch Applier

## Alternatives

### 단일 GPT 호출 기반 코드 생성
- 정확도, 재현성 부족

### 코파일럿형 상호작용 기반 loop
- 정확도, 재현성 부족

### GitHub Copilot 스타일 자동완성 중심 구조
- 정확도, 재현성 부족

## Consequences

Copilot은 reproducible agent 패턴을 가지며 모든 코드 수정은 계획 기반으로 진행됨.
