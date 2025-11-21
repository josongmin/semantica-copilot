"""Intent Router Node - Pydantic AI + TOON 기반 Intent 분류 및 실행 계획 생성"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, cast

from pydantic_ai import Agent

from semantica_copilot.agent.intent import ExecutionPlan
from semantica_copilot.agent.state import AgentState
from semantica_copilot.utils.toon import encode_to_toon

logger = logging.getLogger(__name__)

# 프롬프트 로드
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "intent_router.md"
with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    ROUTER_SYSTEM_PROMPT = f.read()


# Pydantic AI Agent 생성
def _create_router_agent() -> Agent[None, ExecutionPlan]:
    """Intent Router Agent 생성"""
    model_name = os.getenv("LLM_MODEL", "openai:gpt-4-turbo-preview")

    # Pydantic AI는 "provider:model" 형식 필요
    # LiteLLM 형식(command-r-plus)을 Pydantic AI 형식으로 변환
    if ":" not in model_name:
        # provider가 없으면 모델명으로 추론
        if "gpt" in model_name.lower():
            model_name = f"openai:{model_name}"
        elif "claude" in model_name.lower():
            model_name = f"anthropic:{model_name}"
        elif "command" in model_name.lower():
            model_name = f"cohere:{model_name}"
        else:
            # 기본값
            logger.warning(f"Unknown model format: {model_name}, using openai prefix")
            model_name = f"openai:{model_name}"

    # API 키 환경변수 매핑 (LiteLLM → Pydantic AI)
    # Pydantic AI는 다른 환경변수명을 사용하므로 매핑 필요
    if "cohere" in model_name and not os.getenv("CO_API_KEY"):
        cohere_key = os.getenv("COHERE_API_KEY")
        if cohere_key:
            os.environ["CO_API_KEY"] = cohere_key
            logger.info("Mapped COHERE_API_KEY → CO_API_KEY for Pydantic AI")

    if "anthropic" in model_name and not os.getenv("ANTHROPIC_API_KEY"):
        # Anthropic은 동일한 환경변수명 사용
        pass

    logger.info(f"Pydantic AI model: {model_name}")

    # Pydantic AI: 제네릭 타입으로 구조화된 출력 지정
    agent = Agent[None, ExecutionPlan](  # type: ignore[misc]
        model_name,
        system_prompt=ROUTER_SYSTEM_PROMPT,
    )

    return agent


async def intent_router_node(state: AgentState) -> Dict[str, Any]:
    """
    Intent Router Node (Pydantic AI)
    유저 질의를 분석하여:
    1. Intent 분류
    2. 실행 계획 생성 (순차적 endpoint 호출 계획)
    """
    logger.info("\n[Intent Router] 시작")
    logger.info(f"사용자 질의: {state.query}")
    if state.location_ctx:
        logger.info(f"위치 컨텍스트: {state.location_ctx}")

    try:
        # LLM 사용 여부 확인
        use_llm = os.getenv("USE_LLM", "false").lower() == "true"

        if not use_llm:
            # 템플릿 모드: 기본 code_question intent
            from semantica_copilot.agent.intent import CodeIntent, EndpointType, PlanStep

            logger.info("\n[템플릿 모드] LLM 비활성화")
            logger.info("기본 Intent: code_question")
            logger.info("기본 Plan: search -> chunks")

            execution_plan = ExecutionPlan(
                intent=CodeIntent.CODE_QUESTION,
                reason="템플릿 모드 (LLM 비활성화)",
                plan=[
                    PlanStep(
                        step=1,
                        endpoint=EndpointType.SEARCH,
                        params={
                            "query": state.query,
                            "k": 10,
                            "location_ctx": state.location_ctx,
                        },
                        description="코드 검색",
                    ),
                    PlanStep(
                        step=2,
                        endpoint=EndpointType.CHUNKS,
                        params={
                            "chunk_ids": ["${candidates[0:3].chunk_id}"],
                            "include_source": True,
                        },
                        description="청크 로드",
                    ),
                ],
            )
        else:
            # Pydantic AI + TOON 모드: 구조화된 출력 + 토큰 최적화
            logger.info("\n[Pydantic AI + TOON 모드] Agent 호출 중...")

            # 유저 입력 구성
            user_input: Dict[str, Any] = {
                "query": state.query,
            }
            if state.repo_ids:
                user_input["repo_ids"] = state.repo_ids
            if state.location_ctx:
                user_input["location_ctx"] = state.location_ctx

            # TOON 포맷으로 변환
            try:
                toon_input = encode_to_toon(user_input)
                logger.info(
                    f"TOON 변환 성공: JSON {len(json.dumps(user_input))} chars -> TOON {len(toon_input)} chars"
                )

                user_prompt = f"""다음 질의를 분석하여 Intent를 분류하고 실행 계획을 JSON으로 반환하세요.

입력 (TOON 포맷):
```toon\
{toon_input}
```"""
            except Exception as e:
                logger.warning(f"TOON 변환 실패, JSON 사용: {e}")
                user_prompt = f"""다음 질의를 분석하여 Intent를 분류하고 실행 계획을 JSON으로 반환하세요.

입력:
```json
{json.dumps(user_input, ensure_ascii=False, indent=2)}
```"""

            # Agent 생성 및 실행
            agent = _create_router_agent()

            logger.info(f"System prompt 길이: {len(ROUTER_SYSTEM_PROMPT)} chars")
            logger.info(f"User prompt 길이: {len(user_prompt)} chars")

            # Pydantic AI가 자동으로 ExecutionPlan 반환
            result = await agent.run(user_prompt)

            # AI 응답 로깅 (디버깅)
            logger.info(f"\n[AI 응답 타입] {type(result.response)}")
            logger.info(f"[AI 응답 타입 이름] {type(result.response).__name__}")

            # response의 모든 속성 확인
            response_attrs = [attr for attr in dir(result.response) if not attr.startswith("_")]
            logger.info(f"[AI 응답 속성들] {response_attrs}")

            # 실제 응답 내용 로깅
            logger.info(f"[AI 원본 응답]\n{result.response}")

            # ModelResponse에서 텍스트 추출
            response_obj = result.response

            # ModelResponse.parts[0].content에서 텍스트 추출
            if hasattr(response_obj, "parts") and len(response_obj.parts) > 0:
                text_content = str(response_obj.parts[0].content)  # 문자열로 변환
                logger.info(f"[텍스트 추출] {len(text_content)} chars")

                # JSON 코드 블록 제거
                if text_content.startswith("```json"):
                    text_content = text_content.split("```json")[1].split("```")[0].strip()
                elif text_content.startswith("```"):
                    text_content = text_content.split("```")[1].split("```")[0].strip()

                # JSON 파싱
                try:
                    data = json.loads(text_content)
                    execution_plan = ExecutionPlan(**data)
                    logger.info("[성공] ModelResponse에서 ExecutionPlan 생성")
                except Exception as e:
                    logger.error(f"[실패] JSON 파싱 에러: {e}")
                    logger.error(f"[텍스트] {text_content[:500]}")
                    raise
            elif isinstance(response_obj, ExecutionPlan):
                # 이미 ExecutionPlan 객체인 경우 (미래 버전 대비)
                execution_plan = response_obj
                logger.info("[성공] ExecutionPlan 객체 직접 반환")
            else:
                raise ValueError(f"예상하지 못한 응답 타입: {type(response_obj)}")

            logger.info("\n[Pydantic AI + TOON] 구조화된 출력 성공")

        # Intent 분석 결과 상세 로깅
        logger.info(f"\n[분류 결과] Intent: {execution_plan.intent.value}")
        logger.info(f"선택 이유: {execution_plan.reason}")

        from semantica_copilot.agent.intent import PlanStep

        plan_steps = cast(List[PlanStep], execution_plan.plan)
        logger.info(f"\n[실행 계획] 총 {len(plan_steps)} 단계:")

        for step in plan_steps:
            logger.info(f"  Step {step.step}: {step.endpoint.value}")
            if step.description:
                logger.info(f"    설명: {step.description}")
            params_dict = cast(Dict[str, Any], step.params)
            logger.info(f"    파라미터: {', '.join(params_dict.keys())}")

        logger.info("\n[Intent Router] 완료\n")

        return {"execution_plan": execution_plan}

    except Exception as e:
        logger.error(f"\n[Intent Router] 실패: {e}", exc_info=True)
        return {"error": f"Intent router failed: {str(e)}"}
