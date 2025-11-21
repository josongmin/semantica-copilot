"""Pytest fixtures"""

import httpx
import pytest

from semantica_copilot.tools.codegraph import BackendType, CodeGraphClient, SearchResult


class MockCodeGraphClient(CodeGraphClient):
    """테스트용 Mock 클라이언트"""

    def __init__(self):
        self.backend = BackendType.HTTP
        self.search_calls = []

    async def search_with_intent(self, intent, repo_ids=None):
        self.search_calls.append(intent)

        # 더미 결과 반환
        return [
            SearchResult(
                repo_id=repo_ids[0] if repo_ids else "test-repo",
                chunk_id=f"chunk-{i}",
                file_path=f"test_{i}.py",
                line_start=i * 10,
                line_end=i * 10 + 5,
                text=f"def test_{i}():\n    pass",
                score=0.9 - i * 0.1,
                scores={
                    "lexical": 0.5,
                    "semantic": 0.6,
                    "graph": 0.7,
                    "fuzzy": 0.3,
                },
            )
            for i in range(5)
        ]

    async def aclose(self):
        pass


class ErrorMockClient(CodeGraphClient):
    """에러를 발생시키는 Mock 클라이언트"""

    def __init__(self, error_type: str = "generic"):
        self.backend = BackendType.HTTP
        self.error_type = error_type
        self.call_count = 0

    async def search_with_intent(self, intent, repo_ids=None):
        self.call_count += 1

        if self.error_type == "timeout":
            raise httpx.TimeoutException("Request timeout")
        elif self.error_type == "http_500":
            raise httpx.HTTPStatusError("Server error", request=None, response=httpx.Response(500))
        elif self.error_type == "network":
            raise httpx.NetworkError("Network unreachable")
        elif self.error_type == "intermittent":
            if self.call_count == 1:
                raise httpx.TimeoutException("Timeout")
            return []
        else:
            raise Exception("Generic error")

    async def aclose(self):
        pass


class LargeResultsMockClient(CodeGraphClient):
    """대량 결과를 반환하는 Mock 클라이언트"""

    def __init__(self, num_results: int = 100):
        self.backend = BackendType.HTTP
        self.num_results = num_results

    async def search_with_intent(self, intent, repo_ids=None):
        return [
            SearchResult(
                repo_id=repo_ids[0] if repo_ids else "test-repo",
                chunk_id=f"chunk-{i}",
                file_path=f"file_{i % 20}.py",
                line_start=i * 5,
                line_end=i * 5 + 3,
                text=f"code block {i}",
                score=0.95 - (i * 0.001),
                scores={"lexical": 0.8, "semantic": 0.7},
            )
            for i in range(self.num_results)
        ]

    async def aclose(self):
        pass


@pytest.fixture
def mock_client():
    return MockCodeGraphClient()


@pytest.fixture
def error_client():
    """에러 Mock 클라이언트 팩토리"""

    def _create(error_type: str = "generic"):
        return ErrorMockClient(error_type)

    return _create


@pytest.fixture
def large_results_client():
    """대량 결과 Mock 클라이언트 팩토리"""

    def _create(num_results: int = 100):
        return LargeResultsMockClient(num_results)

    return _create


@pytest.fixture
def codegraph_available():
    """codegraph API 실행 여부 확인"""
    import httpx

    async def _check():
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/", timeout=2.0)
                return response.status_code == 200
        except Exception:
            return False

    return _check
