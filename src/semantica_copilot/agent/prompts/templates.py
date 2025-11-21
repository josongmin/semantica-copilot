"""프롬프트 템플릿"""

import logging
from pathlib import Path

from semantica_copilot.agent.state import AgentState

logger = logging.getLogger(__name__)


def load_template(name: str) -> str:
    """프롬프트 템플릿 파일 로드"""
    template_path = Path(__file__).parent / f"{name}.md"
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    else:
        logger.warning(f"Template not found: {name}")
        return ""


def build_code_explain_prompt(state: AgentState) -> str:
    """
    Code Explanation 프롬프트 생성

    검색 결과를 LLM에 전달하여 설명 요청
    """
    template = load_template("code_explain")

    # 상위 5개 결과
    top_results = state.accumulated_context.get_top_k(5)

    # 검색 결과 포맷팅
    results_text = []
    for i, result in enumerate(top_results, 1):
        results_text.append(f"\n## Result {i}")
        results_text.append(f"**File**: {result.file_path}:{result.line_start}-{result.line_end}")
        results_text.append(f"**Score**: {result.score:.3f}")

        if result.text:
            # 텍스트가 너무 길면 잘라내기
            text = result.text[:1000]
            if len(result.text) > 1000:
                text += "\n... (truncated)"
            results_text.append(f"\n```\n{text}\n```")
        else:
            results_text.append("\n_코드 내용 없음_")

    search_results_str = "\n".join(results_text)

    # 템플릿 치환
    prompt = template.format(
        query=state.query,
        total_results=len(state.accumulated_context.results),
        search_results=search_results_str,
    )

    return prompt


def build_search_plan_prompt(state: AgentState) -> str:
    """
    Search Plan 프롬프트 생성 (Phase 3+)

    현재 컨텍스트 기반으로 다음 검색 전략 요청
    """
    template = load_template("search_plan")

    # 상위 파일 목록
    unique_files = list({r.file_path for r in state.accumulated_context.results})
    top_files = "\n".join(f"- {f}" for f in unique_files[:10])

    prompt = template.format(
        query=state.query,
        search_steps=state.search_steps,
        max_search_steps=state.max_search_steps,
        total_results=len(state.accumulated_context.results),
        top_files=top_files if top_files else "없음",
    )

    return prompt
