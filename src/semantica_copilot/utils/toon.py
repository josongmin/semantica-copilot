"""TOON (Token-Oriented Object Notation) 유틸리티

TOON은 LLM 프롬프트를 위한 컴팩트한 JSON 형식입니다.
참고: https://github.com/toon-format/toon
"""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def encode_to_toon(data: dict[str, Any]) -> str:
    """
    JSON 데이터를 TOON 형식으로 인코딩

    Args:
        data: 인코딩할 JSON 데이터

    Returns:
        TOON 형식 문자열
    """
    # 임시 파일에 JSON 저장
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f, ensure_ascii=False)
        json_path = f.name

    try:
        # TOON CLI로 변환
        result = subprocess.run(
            ["npx", "--yes", "@toon-format/cli", json_path],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    finally:
        # 임시 파일 삭제
        Path(json_path).unlink(missing_ok=True)


def decode_from_toon(toon_str: str) -> dict[str, Any]:
    """
    TOON 형식 문자열을 JSON으로 디코딩

    Args:
        toon_str: TOON 형식 문자열

    Returns:
        JSON 데이터
    """
    # 임시 파일에 TOON 저장
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toon", delete=False) as f:
        f.write(toon_str)
        toon_path = f.name

    try:
        # TOON CLI로 변환
        result = subprocess.run(
            ["npx", "--yes", "@toon-format/cli", "-d", toon_path],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    finally:
        # 임시 파일 삭제
        Path(toon_path).unlink(missing_ok=True)


def get_token_stats(data: dict[str, Any]) -> dict[str, int]:
    """
    JSON과 TOON 형식의 토큰 수 비교

    Args:
        data: 비교할 JSON 데이터

    Returns:
        토큰 통계 딕셔너리
    """
    json_str = json.dumps(data, ensure_ascii=False)
    toon_str = encode_to_toon(data)

    # 간단한 토큰 추정 (공백으로 분리)
    json_tokens = len(json_str.split())
    toon_tokens = len(toon_str.split())

    return {
        "json_tokens": json_tokens,
        "toon_tokens": toon_tokens,
        "saved": json_tokens - toon_tokens,
        "saved_percent": int(round((1 - toon_tokens / json_tokens) * 100))
        if json_tokens > 0
        else 0,
    }
