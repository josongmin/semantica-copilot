# ADR 0008 – CLI/TUI(Textual) 인터페이스 채택

## Context

Web/Electron 기반 GUI는 개발 리소스가 크고, 에이전트 로그·검색 결과·diff 표시가 어려움.

## Decision

TUI(Textual)를 Copilot의 기본 인터페이스로 채택한다.

- 검색창
- 커맨드 팔레트
- diff 뷰
- planner 로그
- agent run history

## Alternatives

### 데스크탑 앱
- 개발난이도와 유지보수 비용 증가

### Web 기반 IDE
- 개발난이도와 유지보수 비용 증가

## Consequences

가벼운 개발 환경에서 빠르게 Copilot을 사용할 수 있게 됨.
