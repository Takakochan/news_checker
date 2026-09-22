from typing import Optional

from pydantic import BaseModel


class CheckRequest(BaseModel):
    text: str
    model: Optional[str] = None
    max_results: Optional[int] = None
    auto_score: Optional[bool] = None
    score_threshold: Optional[float] = None


class TavilySettings(BaseModel):
    search_depth: str
    max_results: int
    score_threshold: float
    reason: str


class SourceResult(BaseModel):
    title: str
    url: str
    score: float
    content: str


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class CheckResponse(BaseModel):
    severity: str
    severity_reasoning: str
    tavily_settings: TavilySettings
    summary: str
    sources: list[SourceResult]
    token_usage: TokenUsage
    result_id: str
    result_url: str
