"""Generate Answer 노드"""

import logging
import os

from semantica_copilot.agent.state import AgentState

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

    # Phase 3: LLM 기반 답변
    if USE_LLM:
        try:
            from semantica_copilot.agent.prompts.templates import build_code_explain_prompt
            from semantica_copilot.llm.provider import get_llm

            llm = get_llm()
            prompt = build_code_explain_prompt(state)

            # LLM 호출
            answer = await llm.ainvoke(prompt)
            state.answer = answer
            logger.info(f"LLM answer generated: {len(answer)} chars")
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
        lexical = result.scores.get('lexical') or 0
        semantic = result.scores.get('semantic') or 0
        graph = result.scores.get('graph') or 0
        fuzzy = result.scores.get('fuzzy') or 0
        
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
