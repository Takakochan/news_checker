import os

from fastapi.testclient import TestClient

from backend import llm, tavily_client
from backend.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_check_requires_auth():
    response = client.post("/check", json={"text": "hello"})
    assert response.status_code == 401


def test_check_rejects_wrong_token():
    response = client.post(
        "/check",
        json={"text": "hello"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401


def test_result_not_found():
    response = client.get("/result/does-not-exist")
    assert response.status_code == 404


def test_check_returns_summary_and_truth_score(monkeypatch):
    monkeypatch.setattr(
        llm,
        "judge_severity",
        lambda text, model=None: (
            {
                "severity": "low",
                "severity_reasoning": "test",
                "search_depth": "basic",
                "max_results": 3,
                "score_threshold": 0.5,
                "reason": "test",
            },
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        ),
    )
    monkeypatch.setattr(
        tavily_client,
        "search",
        lambda **kwargs: [
            {"title": "Example", "url": "https://example.com", "score": 0.9, "content": "example content"}
        ],
    )
    monkeypatch.setattr(
        llm,
        "summarize_fact_check",
        lambda text, sources, model=None: (
            "This is a test summary.",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        ),
    )
    monkeypatch.setattr(
        llm,
        "score_truth",
        lambda text, sources, summary, model=None: (
            80,
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        ),
    )

    response = client.post(
        "/check",
        json={"text": "This is a test."},
        headers={"Authorization": f"Bearer {os.environ['DEMO_TOKEN']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["severity"] == "low"
    assert data["truth_score"] == 80
    assert data["sources"][0]["url"] == "https://example.com"
    assert "result_id" in data
