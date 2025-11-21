"""Intent Plan 노드 (LLM + TOON 기반)"""

import json
import logging
import os

from semantica_copilot.agent.state import AgentState
from semantica_copilot.utils.toon import encode_to_toon

logger = logging.getLogger(__name__)

# LLM 사용 여부 (환경변수)
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"


async def intent_plan_node(state: AgentState) -> AgentState:
    """
    Intent Plan 노드

    Phase 3: LLM 기반 plan 생성
    Phase 2: 고정된 plan (폴백)
    """
    logger.info(f"intent_plan_node: Planning (LLM={USE_LLM})...")

    # Phase 3: LLM 기반 plan 생성 (TOON 포맷)
    if USE_LLM:
        try:
            from semantica_copilot.llm.provider import get_llm

            llm = get_llm()

            # 입력 데이터를 TOON 포맷으로
            plan_input = {
                "query": state.query,
                "context": {
                    "task_types": [
                        "code_explanation",
                        "architecture_analysis",
                        "bug_investigation",
                    ],
                    "search_steps_range": [1, 2, 3],
                    "targets": ["definition", "usage", "relationships", "dependencies"],
                    "strategy": "hybrid",
                },
            }

            try:
                toon_input = encode_to_toon(plan_input)
                logger.info("TOON 변환 성공")

                prompt = f"""사용자 질문을 분석하여 코드 검색 계획을 생성하세요.

입력 (TOON 포맷):
```toon
{toon_input}
```

다음 JSON 형식으로 응답하세요:
{{
    "task": "code_explanation | architecture_analysis | bug_investigation",
    "max_search_steps": 1-3,
    "targets": ["definition", "usage", "relationships", "dependencies"],
    "strategy": "hybrid",
    "reasoning": "왜 이런 계획을 세웠는지 간단히 설명"
}}

규칙:
- "무엇인가?" 질문 → task: "code_explanation", max_search_steps: 2
- "어떻게 동작?" 질문 → task: "architecture_analysis", max_search_steps: 3
- "왜 에러?" 질문 → task: "bug_investigation", max_search_steps: 2

JSON만 출력하세요 (추가 설명 없이):"""
            except Exception as e:
                logger.warning(f"TOON 변환 실패: {e}")
                prompt = f"""사용자 질문을 분석하여 코드 검색 계획을 생성하세요.

질문: {state.query}

다음 JSON 형식으로 응답하세요:
{{
    "task": "code_explanation | architecture_analysis | bug_investigation",
    "max_search_steps": 1-3,
    "targets": ["definition", "usage", "relationships", "dependencies"],
    "strategy": "hybrid",
    "reasoning": "왜 이런 계획을 세웠는지 간단히 설명"
}}

JSON만 출력하세요:"""

            # LLM 호출
            response = await llm.ainvoke(prompt)

            # JSON 파싱
            try:
                # JSON 블록 추출 (```json ... ``` 형식 지원)
                response_cleaned = response.strip()
                if response_cleaned.startswith("```json"):
                    response_cleaned = response_cleaned.split("```json")[1].split("```")[0].strip()
                elif response_cleaned.startswith("```"):
                    response_cleaned = response_cleaned.split("```")[1].split("```")[0].strip()

                plan = json.loads(response_cleaned)

                # 검증
                if not all(k in plan for k in ["task", "max_search_steps", "targets", "strategy"]):
                    raise ValueError("Missing required fields in plan")

                state.plan = plan
                state.max_search_steps = plan["max_search_steps"]

                logger.info(f"LLM plan created: {plan}")
                logger.info(f"Reasoning: {plan.get('reasoning', 'N/A')}")

                return state

            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to parse LLM response: {e}")
                logger.error(f"Response: {response[:200]}")
                # 템플릿으로 폴백

        except Exception as e:
            logger.error(f"LLM planning failed: {e}, falling back to template")
            # 템플릿으로 폴백

    # 템플릿 기반 plan (폴백)
    state.plan = {
        "task": "code_explanation",
        "max_search_steps": 2,
        "targets": ["definition", "usage", "relationships"],
        "strategy": "hybrid",
        "reasoning": "Template-based plan (LLM disabled or failed)",
    }
    state.max_search_steps = 2

    logger.info(f"Template plan created: {state.plan}")

    return state
