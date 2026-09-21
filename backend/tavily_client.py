import os

import httpx

TAVILY_URL = "https://api.tavily.com/search"


def search(query: str, search_depth: str, max_results: int, score_threshold: float) -> list[dict]:
    api_key = os.environ["TAVILY_API_KEY"].strip()
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
        "include_answer": False,
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(TAVILY_URL, json=payload)
        response.raise_for_status()
        data = response.json()

    results = data.get("results", [])
    filtered = [r for r in results if r.get("score", 0) >= score_threshold]
    return filtered or results
