# ADR 0004 – Tool Selection 전략

## Context

Planner가 만든 계획을 실행하려면 검색·읽기·쓰기·diff 적용 등 다양한 도구가 필요함.

## Decision

Copilot 도구는 다음과 같이 구성한다.

- Codegraph Hybrid Search
- Codegraph Chunk Reader
- File fetcher
- Patch applier
- LLM diff generator (여기서는 generator 호출)

Planner는 tool 목록 중 필요 도구만 선택하여 실행함.

## Alternatives

### 단일 search/open API
- 안정성 없고 품질 낮음

### 도구 없이 GPT로 파일 path 추측
- 안정성 없고 품질 낮음

## Consequences

각 단계가 명확히 분리된 deterministic한 workflow 구성.
