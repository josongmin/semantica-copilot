"""프롬프트 빌더 싱글톤 (TOON 포맷 자동 적용)"""

import logging
from typing import Any, Optional

from semantica_copilot.utils.toon import encode_to_toon

logger = logging.getLogger(__name__)


class PromptBuilder:
    """
    프롬프트 빌더 싱글톤

    LLM 요청 전에 데이터를 TOON 포맷으로 자동 변환하여
    토큰 사용량을 최적화합니다.
    """

    _instance: Optional["PromptBuilder"] = None
    _use_toon: bool = True

    def __new__(cls):
        """싱글톤 패턴"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """초기화 (한 번만 실행)"""
        if self._initialized:
            return
        self._initialized = True
        self._use_toon = True
        logger.info("PromptBuilder 싱글톤 초기화 완료")

    def set_use_toon(self, use_toon: bool) -> None:
        """TOON 포맷 사용 여부 설정"""
        self._use_toon = use_toon
        logger.info(f"TOON 포맷 사용: {use_toon}")

    def build_prompt(
        self,
        template: str,
        data: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """
        프롬프트 빌드

        Args:
            template: 프롬프트 템플릿 문자열
            data: TOON으로 변환할 데이터 (dict)
            **kwargs: 템플릿에 전달할 추가 변수

        Returns:
            완성된 프롬프트 문자열
        """
        prompt_parts = []

        # 데이터가 있으면 TOON 형식으로 변환
        if data and self._use_toon:
            try:
                toon_data = encode_to_toon(data)
                prompt_parts.append("```toon")
                prompt_parts.append(toon_data)
                prompt_parts.append("```")
                prompt_parts.append("")  # 빈 줄
                logger.debug(f"TOON 데이터 추가: {len(toon_data)} chars")
            except Exception as e:
                logger.warning(f"TOON 변환 실패, JSON 사용: {e}")
                import json

                prompt_parts.append("```json")
                prompt_parts.append(json.dumps(data, indent=2, ensure_ascii=False))
                prompt_parts.append("```")
                prompt_parts.append("")
        elif data:
            # TOON 비활성화 시 JSON 사용
            import json

            prompt_parts.append("```json")
            prompt_parts.append(json.dumps(data, indent=2, ensure_ascii=False))
            prompt_parts.append("```")
            prompt_parts.append("")

        # 템플릿 적용
        if kwargs:
            try:
                formatted_template = template.format(**kwargs)
            except KeyError as e:
                logger.warning(f"템플릿 변수 누락: {e}, 원본 템플릿 사용")
                formatted_template = template
        else:
            formatted_template = template

        prompt_parts.append(formatted_template)

        return "\n".join(prompt_parts)

    def build_with_context(
        self,
        query: str,
        context_data: Optional[dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> tuple[str, Optional[str]]:
        """
        컨텍스트 데이터와 함께 프롬프트 빌드

        Args:
            query: 사용자 질문
            context_data: 검색 결과 등 컨텍스트 데이터 (TOON으로 변환됨)
            system_prompt: 시스템 프롬프트 (선택)
            **kwargs: 추가 템플릿 변수

        Returns:
            (user_prompt, system_prompt) 튜플
        """
        # 기본 프롬프트 템플릿
        if context_data:
            template = """위의 데이터를 참고하여 다음 질문에 답변해주세요:

{query}

답변은 한국어로 작성해주세요."""
        else:
            template = "{query}"

        user_prompt = self.build_prompt(template, data=context_data, query=query, **kwargs)

        return (user_prompt, system_prompt)


# 전역 인스턴스
_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder() -> PromptBuilder:
    """프롬프트 빌더 싱글톤"""
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder
