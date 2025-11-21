# ADR 0006 – Diff Generator 설계

## Context

Cursor/GPT 캔버스가 전체 파일을 재작성하는 주요 이유는 부분 위치 인식이 없는 구조 때문임.

Copilot은 Codegraph가 제공하는 위치정보 기반으로 diff만 생성해야 한다.

## Decision

Diff Generator는 다음 전략을 따른다.

- Codegraph AST 위치정보 기반으로 블록 범위 지정
- 해당 블록만 변경하는 unified diff 생성
- 전체 파일 재작성은 금지
- Git-safe patch 기준 준수

## Alternatives

### full-file regeneration
- 충돌 위험 증가

### GPT의 자유형식 코드 출력
- 충돌 위험 증가

## Consequences

안전한 대규모 리팩터링 가능.
