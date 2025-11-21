"""LLM Provider (LiteLLM 래퍼)"""

import logging
import os
from typing import Optional

from litellm import acompletion, completion

logger = logging.getLogger(__name__)


class LLMProvider:
    """
    LiteLLM 기반 LLM Provider

    여러 LLM 제공자를 통일된 인터페이스로 사용
    - OpenAI (gpt-4, gpt-3.5-turbo)
    - Anthropic (claude-3)
    - 로컬 모델 (ollama)
    """

    def __init__(
        self,
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.1,
        max_tokens: int = 2000,
        **kwargs,
    ):
        """
        Args:
            model: 모델명 (LiteLLM 형식)
                - "gpt-4-turbo-preview"
                - "claude-3-sonnet-20240229"
                - "ollama/llama3"
            temperature: 0.0-1.0
            max_tokens: 최대 토큰 수
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.kwargs = kwargs

        logger.info(f"LLMProvider initialized: model={model}, temp={temperature}")

    async def ainvoke(self, messages_or_prompt, system: Optional[str] = None, **kwargs):
        """
        비동기 LLM 호출

        Args:
            messages_or_prompt: messages 리스트 또는 prompt 문자열
            system: 시스템 프롬프트 (선택, prompt 모드일 때만)
            **kwargs: 추가 파라미터 (temperature, max_tokens 등)

        Returns:
            응답 객체 (content 속성 포함) 또는 문자열
        """
        # messages 리스트로 직접 호출
        if isinstance(messages_or_prompt, list):
            messages = messages_or_prompt
        # prompt + system 모드
        else:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": messages_or_prompt})

        # 파라미터 병합
        params = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            **self.kwargs,
        }

        try:
            response = await acompletion(**params)
            logger.info(f"LLM response: {len(response.choices[0].message.content)} chars")
            return response.choices[0].message

        except Exception as e:
            logger.error(f"LLM error: {e}")
            raise

    def invoke(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        동기 LLM 호출 (테스트용)

        Args:
            prompt: 사용자 프롬프트
            system: 시스템 프롬프트 (선택)

        Returns:
            LLM 응답 텍스트
        """
        messages = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": prompt})

        params = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            **self.kwargs,
        }

        try:
            response = completion(**params)
            content = response.choices[0].message.content
            return content  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"LLM error: {e}")
            raise


# 전역 인스턴스 (lazy initialization)
_llm: Optional[LLMProvider] = None


def get_llm() -> LLMProvider:
    """LLM 싱글톤"""
    global _llm
    if _llm is None:
        model = os.getenv("LLM_MODEL", "gpt-4-turbo-preview")
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
        _llm = LLMProvider(model=model, temperature=temperature)
    return _llm
