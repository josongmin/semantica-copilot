# Search Plan Prompt

당신은 코드 검색 전략을 수립하는 AI입니다.

## Task
사용자 질문과 현재까지 수집한 컨텍스트를 바탕으로, 다음 검색 의도를 생성하세요.

## Input

### Query
{query}

### Current Step
{search_steps} / {max_search_steps}

### Accumulated Context
이미 수집한 결과: {total_results}개
상위 파일:
{top_files}

## Instructions

1. 현재 단계에 맞는 검색 전략을 선택하세요
2. 검색할 entity나 keyword를 추출하세요
3. 적절한 strategy를 선택하세요

## Search Strategies

- **hybrid**: 첫 검색, 심볼/파일 찾기
- **graph**: 관계 탐색 (호출자/피호출자, 타입 의존성)
- **semantic**: 의미론적 유사 코드
- **lexical**: 정확한 키워드 매칭

## Output Format

JSON으로 응답하세요:

```json
{
  "entities": ["entity1", "entity2"],
  "keywords": ["keyword1", "keyword2"],
  "strategy": "hybrid",
  "graph_depth": 1,
  "edge_types": ["calls", "uses"],
  "limit": 20
}
```

Note: Phase 3+에서 사용 (현재는 패턴 기반)

