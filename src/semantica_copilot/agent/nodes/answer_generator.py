"""Answer Generator Node - 최종 답변 생성 (TOON 최적화)"""

import logging
import os
from typing import Any, Dict

from semantica_copilot.agent.state import AgentState
from semantica_copilot.utils.toon import encode_to_toon

logger = logging.getLogger(__name__)


def _build_answer_messages(state: AgentState) -> list:
    """답변 생성 메시지 구성 (TOON 포맷)"""
    # 컨텍스트 데이터 구성
    chunks_data = []
    for chunk in state.accumulated_chunks:
        chunks_data.append(
            {
                "file": chunk.file_path,
                "lines": f"{chunk.line_start}-{chunk.line_end}",
                "score": round(chunk.score, 3),
                "code": chunk.text,
            }
        )

    context_data = {
        "query": state.query,
        "chunks": chunks_data,
    }

    # TOON 포맷으로 변환 (토큰 절약)
    try:
        toon_context = encode_to_toon(context_data)
        logger.info(f"TOON 변환 성공: 청크 {len(chunks_data)}개를 {len(toon_context)} chars로 압축")

        context_block = f"""```toon
{toon_context}
```"""
    except Exception as e:
        logger.warning(f"TOON 변환 실패, 일반 포맷 사용: {e}")
        # TOON 실패 시 간단한 포맷 사용
        context_parts = []
        for chunk in state.accumulated_chunks:
            context_parts.append(
                f"""파일: {chunk.file_path} (라인 {chunk.line_start}-{chunk.line_end})
점수: {chunk.score:.3f}

```
{chunk.text}
```"""
            )
        context_block = "\n---\n".join(context_parts)

    system_prompt = """You are a code analysis expert.

Answer the user's question based on the provided code context.

**Answer Guidelines**:
1. Specify exact file paths and line ranges (e.g., `main.py:146-158`)
2. Group results by category or role (e.g., "Health Check Endpoints", "Repository API")
3. Quote actual code snippets in code blocks
4. Include router registration and import information if relevant
5. Structure the answer clearly for easy navigation
6. Answer in Korean
"""

    user_prompt = f"""질문: {state.query}

코드 컨텍스트:
{context_block}

위 코드를 바탕으로 질문에 답변해주세요."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _build_template_answer(state: AgentState) -> str:
    """템플릿 모드 답변 (LLM 없이)"""
    if not state.accumulated_chunks:
        return "검색 결과가 없습니다."

    # 간단한 요약
    chunks = state.accumulated_chunks[:3]
    result = f"질문: {state.query}\n\n검색 결과 {len(state.accumulated_chunks)}개를 찾았습니다.\n\n"

    for i, chunk in enumerate(chunks, 1):
        result += f"{i}. {chunk.file_path} (라인 {chunk.line_start}-{chunk.line_end})\n"
        result += f"   점수: {chunk.score:.3f}\n"
        # 첫 100자만 표시
        preview = chunk.text[:100] if len(chunk.text) > 100 else chunk.text
        result += f"   미리보기: {preview}...\n\n"

    return result


async def answer_generator_node(state: AgentState) -> Dict[str, Any]:
    """
    Answer Generator Node

    실행 결과를 바탕으로 최종 답변 생성
    """
    logger.info("\n[Answer Generator] 시작")
    logger.info(f"수집된 청크: {len(state.accumulated_chunks)}개")

    try:
        # LLM 사용 여부
        use_llm = os.getenv("USE_LLM", "false").lower() == "true"

        if not use_llm:
            # 템플릿 모드
            logger.info("\n[템플릿 모드] 간단한 요약 생성")
            answer = _build_template_answer(state)
        else:
            # LLM 모드 (OpenAI 사용)
            logger.info("\n[LLM 모드] 답변 생성 중... (OpenAI)")

            if not state.accumulated_chunks:
                logger.warning("[경고] 청크가 없어 답변 생성 불가")
                answer = "검색 결과가 없어 답변을 생성할 수 없습니다."
            else:
                # OpenAI LLM 사용 (최종 답변 생성용)
                from semantica_copilot.llm.provider import LLMProvider

                openai_model = os.getenv("ANSWER_LLM_MODEL", "gpt-4o-mini")
                llm = LLMProvider(
                    model=openai_model,
                    temperature=0.3,  # 답변 생성용 온도
                    max_tokens=2000,
                )
                logger.info(f"OpenAI 모델: {openai_model}")

                messages = _build_answer_messages(state)

                logger.info(f"컨텍스트 청크 수: {len(state.accumulated_chunks)}")
                logger.info(f"프롬프트 메시지 수: {len(messages)}")

                response = await llm.ainvoke(messages)
                answer = response.content

                logger.info("[답변 생성 완료]")

        logger.info(f"최종 답변 길이: {len(answer)} chars")
        logger.info("\n[Answer Generator] 완료\n")

        return {"answer": answer}

    except Exception as e:
        logger.error(f"\n[Answer Generator] 실패: {e}", exc_info=True)
        return {"error": f"Answer generation failed: {str(e)}"}
