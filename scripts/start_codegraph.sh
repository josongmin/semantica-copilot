#!/bin/bash
# codegraph 실행 스크립트

cd ../semantica-codegraph || exit 1

echo "Starting semantica-codegraph API server..."
echo "URL: http://localhost:8000"
echo ""

python -m apps.api.main

