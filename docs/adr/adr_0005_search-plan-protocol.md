# ADR 0005 – Search Plan Protocol

## Context

LLM이 Codegraph 검색 API를 효과적으로 활용하기 위해서는 명확히 정의된 검색 프로토콜이 필요하다.

## Decision

Search plan은 다음 정보를 포함한다.

- target symbol / keyword
- 검색 유형 (symbol-search, vector-search, route-search 등)
- 반환해야 할 필요한 context 범위
- 후보 순위를 결정하는 기준

## Alternatives

### search를 free-form prompt로 GPT에 위임
- 불안정하고 재현 불가

## Consequences

LLM이 Codegraph를 정확한 방식으로 호출하게 되며 reproducible 계획이 보장됨.
