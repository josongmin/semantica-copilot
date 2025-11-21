"""Generate Answer 노드 (TOON 최적화)"""

import logging
import os

from semantica_copilot.agent.state import AgentState
from semantica_copilot.utils.toon import encode_to_toon

logger = logging.getLogger(__name__)

# Phase 3: LLM 사용 여부 (환경변수)
USE_LLM = os.getenv("USE_LLM", "false").lower() == "true"


async def generate_answer_node(state: AgentState) -> AgentState:
    """
    Generate Answer 노드

    Phase 2: 템플릿 기반 (기본)
    Phase 3: LLM 기반 (USE_LLM=true)
    """
    logger.info(f"generate_answer_node: Generating answer (LLM={USE_LLM})...")

    # 에러 처리
    if state.error:
        state.answer = f"검색 중 오류가 발생했습니다: {state.error}"
        logger.error(f"Returning error answer: {state.error}")
        return state

    # 결과 없음
    if not state.accumulated_context.results:
        state.answer = "검색 결과가 없습니다."
        logger.warning("No results found")
        return state

    # Phase 3: LLM 기반 답변 (OpenAI + TOON 포맷)
    if USE_LLM:
        try:
            from semantica_copilot.llm.provider import LLMProvider

            # OpenAI 전용 LLM 사용 (최종 답변 생성용)
            openai_model = os.getenv("ANSWER_LLM_MODEL", "gpt-4o-mini")
            llm = LLMProvider(
                model=openai_model,
                temperature=0.3,
                max_tokens=2000,
            )
            logger.info(f"OpenAI 모델 사용: {openai_model}")

            # 검색 결과를 TOON 포맷으로 변환
            top_results = state.accumulated_context.get_top_k(5)
            results_data = []
            for result in top_results:
                results_data.append(
                    {
                        "file": result.file_path,
                        "lines": f"{result.line_start}-{result.line_end}",
                        "score": round(result.score, 3),
                        "code": result.text[:1000] if result.text else "",  # 길이 제한
                    }
                )

            context_data = {
                "query": state.query,
                "results": results_data,
            }

            # TOON 포맷으로 변환
            try:
                toon_context = encode_to_toon(context_data)
                logger.info(f"TOON 변환 성공: 결과 {len(results_data)}개")

                prompt = f"""다음 코드 검색 결과를 바탕으로 질문에 답변하세요.

```toon
{toon_context}
```

답변 지침:
1. 코드 컨텍스트에 기반한 정확한 답변
2. 관련 파일/함수/클래스 명시
3. 한국어로 답변"""
            except Exception as e:
                logger.warning(f"TOON 변환 실패: {e}")
                # 폴백: 간단한 포맷
                prompt = f"""질문: {state.query}

검색 결과: {len(top_results)}개

답변해주세요 (한국어)."""

            # OpenAI LLM 호출
            response = await llm.ainvoke(prompt)
            answer = response.content if hasattr(response, "content") else str(response)
            state.answer = answer
            logger.info(f"OpenAI 답변 생성 완료: {len(answer)} chars")
            return state

        except Exception as e:
            logger.error(f"LLM generation failed: {e}, falling back to template")
            # 템플릿으로 폴백

    # 템플릿 기반 답변 생성
    top_results = state.accumulated_context.get_top_k(5)

    answer_parts = [
        f"# {state.query} 검색 결과",
        f"\n총 {len(state.accumulated_context.results)}개 결과 (상위 5개 표시)\n",
    ]

    for i, result in enumerate(top_results, 1):
        answer_parts.append(f"\n## {i}. {result.file_path}:{result.line_start}")
        answer_parts.append(f"**Score**: {result.score:.3f}")

        # scores 값이 None일 수 있으므로 처리
        lexical = result.scores.get("lexical") or 0
        semantic = result.scores.get("semantic") or 0
        graph = result.scores.get("graph") or 0
        fuzzy = result.scores.get("fuzzy") or 0

        answer_parts.append(
            f"**Scores**: Lexical={lexical:.2f}, "
            f"Semantic={semantic:.2f}, "
            f"Graph={graph:.2f}, "
            f"Fuzzy={fuzzy:.2f}"
        )

        if result.text:
            preview = result.text[:300]
            if len(result.text) > 300:
                preview += "..."
            answer_parts.append(f"\n```\n{preview}\n```")
        else:
            answer_parts.append("\n_⚠️ 코드 내용 없음 (codegraph text 필드 확인 필요)_")

    answer_parts.append(f"\n---\n검색 단계: {state.search_steps}회")

    state.answer = "\n".join(answer_parts)

    logger.info(f"Answer generated: {len(state.answer)} chars")

    return state
