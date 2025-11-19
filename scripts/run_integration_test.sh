#!/bin/bash
# 연동 테스트 실행 스크립트

echo "🚀 Semantica Copilot - 연동 테스트"
echo ""

# codegraph 연결 확인
echo "1. codegraph API 연결 확인..."
if ! curl -s http://localhost:8000/ > /dev/null 2>&1; then
    echo "❌ codegraph가 실행 중이 아닙니다"
    echo ""
    echo "⚠️  다음 명령으로 codegraph를 먼저 실행하세요:"
    echo "   cd ../semantica-codegraph"
    echo "   python -m apps.api.main"
    echo ""
    exit 1
fi
echo "✅ codegraph 실행 중"
echo ""

# 연동 테스트 실행
echo "2. 연동 테스트 실행..."
python tests/integration_test.py

