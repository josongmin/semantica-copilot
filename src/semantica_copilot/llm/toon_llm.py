"""TOON 포맷을 자동 적용하는 LLM 래퍼"""

import logging
from typing import Any, Optional

from semantica_copilot.llm.prompt_builder import get_prompt_builder
from semantica_copilot.llm.provider import LLMProvider, get_llm
from semantica_copilot.utils.toon import decode_from_toon

logger = logging.getLogger(__name__)


class ToonLLM:
    """
    TOON 포맷을 자동으로 적용하는 LLM 래퍼

    프롬프트 빌더를 사용하여 데이터를 TOON 형식으로 변환하고,
    LLM 호출을 자동화합니다.
    """

    def __init__(self, llm: Optional[LLMProvider] = None):
        """
        Args:
            llm: LLMProvider 인스턴스 (None이면 싱글톤 사용)
        """
        self.llm = llm or get_llm()
        self.prompt_builder = get_prompt_builder()
        logger.info("ToonLLM 초기화 완료")

    async def ainvoke(
        self,
        query: str,
        context_data: Optional[dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        template: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        비동기 LLM 호출 (TOON 포맷 자동 적용)

        Args:
            query: 사용자 질문
            context_data: 컨텍스트 데이터 (TOON으로 변환됨)
            system_prompt: 시스템 프롬프트
            template: 커스텀 프롬프트 템플릿 (선택)
            **kwargs: 추가 템플릿 변수

        Returns:
            LLM 응답 텍스트
        """
        # 프롬프트 빌드
        if template:
            user_prompt = self.prompt_builder.build_prompt(
                template, data=context_data, query=query, **kwargs
            )
        else:
            user_prompt, system_prompt = self.prompt_builder.build_with_context(
                query=query,
                context_data=context_data,
                system_prompt=system_prompt,
                **kwargs,
            )

        # LLM 호출
        logger.info(
            f"LLM 호출: query={query[:50]}..., context_data={'있음' if context_data else '없음'}"
        )
        response = await self.llm.ainvoke(user_prompt, system=system_prompt, **kwargs)
        logger.info(f"LLM 응답: {len(response)} chars")

        return response

    def invoke(
        self,
        query: str,
        context_data: Optional[dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        template: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        동기 LLM 호출 (테스트용)

        Args:
            query: 사용자 질문
            context_data: 컨텍스트 데이터 (TOON으로 변환됨)
            system_prompt: 시스템 프롬프트
            template: 커스텀 프롬프트 템플릿 (선택)
            **kwargs: 추가 템플릿 변수

        Returns:
            LLM 응답 텍스트
        """
        # 프롬프트 빌드
        if template:
            user_prompt = self.prompt_builder.build_prompt(
                template, data=context_data, query=query, **kwargs
            )
        else:
            user_prompt, system_prompt = self.prompt_builder.build_with_context(
                query=query,
                context_data=context_data,
                system_prompt=system_prompt,
                **kwargs,
            )

        # LLM 호출
        logger.info(f"LLM 호출 (동기): query={query[:50]}...")
        response = self.llm.invoke(user_prompt, system=system_prompt, **kwargs)
        logger.info(f"LLM 응답: {len(response)} chars")

        return response

    async def ainvoke_with_toon_response(
        self,
        query: str,
        context_data: Optional[dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        LLM 호출 후 응답을 TOON 형식으로 파싱

        Args:
            query: 사용자 질문
            context_data: 컨텍스트 데이터
            system_prompt: 시스템 프롬프트
            **kwargs: 추가 파라미터

        Returns:
            파싱된 응답 딕셔너리
        """
        response = await self.ainvoke(query, context_data, system_prompt, **kwargs)

        # TOON 형식 파싱 시도
        try:
            # 응답에서 TOON 블록 추출
            if "```toon" in response:
                toon_start = response.find("```toon") + 7
                toon_end = response.find("```", toon_start)
                if toon_end > toon_start:
                    toon_str = response[toon_start:toon_end].strip()
                    parsed = decode_from_toon(toon_str)
                    logger.info("TOON 응답 파싱 성공")
                    return parsed
        except Exception as e:
            logger.warning(f"TOON 파싱 실패: {e}")

        # 파싱 실패 시 원본 텍스트 반환
        return {"response": response}


# 전역 인스턴스
_toon_llm: Optional[ToonLLM] = None


def get_toon_llm() -> ToonLLM:
    """ToonLLM 싱글톤"""
    global _toon_llm
    if _toon_llm is None:
        _toon_llm = ToonLLM()
    return _toon_llm
