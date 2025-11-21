#!/bin/bash
# uv를 사용한 code-question-test 실행 스크립트

set -e

# 현재 디렉토리 저장
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 기본 설정
QUERY="${1:-이거 뭐하는 프로젝트야}"
USE_LLM="${2:-}"

# uv로 실행
if [ "$USE_LLM" = "--llm" ]; then
    echo "LLM 모드로 실행: $QUERY"
    uv run python example/code-question-test.py --llm "$QUERY"
else
    echo "템플릿 모드로 실행: $QUERY"
    uv run python example/code-question-test.py "$QUERY"
fi
