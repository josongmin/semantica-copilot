"""CodeGraphClient 테스트"""

import pytest

from semantica_copilot.agent.state import CodeSearchIntent, SearchStrategy


@pytest.mark.asyncio
async def test_mock_client_search_with_intent(mock_client):
    """Mock 클라이언트 테스트"""
    intent = CodeSearchIntent(
        entities=["UserService"],
        strategy=SearchStrategy.HYBRID,
        limit=10,
    )

    results = await mock_client.search_with_intent(intent, repo_ids=["test-repo"])

    assert len(results) == 5
    assert results[0].repo_id == "test-repo"
    assert results[0].score > results[1].score  # 점수 역순


@pytest.mark.asyncio
async def test_mock_client_tracks_calls(mock_client):
    """Mock 클라이언트가 호출 이력 추적"""
    intent1 = CodeSearchIntent(entities=["test1"])
    intent2 = CodeSearchIntent(entities=["test2"])

    await mock_client.search_with_intent(intent1)
    await mock_client.search_with_intent(intent2)

    assert len(mock_client.search_calls) == 2
    assert mock_client.search_calls[0].entities == ["test1"]
    assert mock_client.search_calls[1].entities == ["test2"]
