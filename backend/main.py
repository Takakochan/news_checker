from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import llm, tavily_client
from .models import CheckRequest, CheckResponse, SourceResult, TavilySettings, TokenUsage

app = FastAPI(title="News Checker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/check", response_model=CheckResponse)
def check(req: CheckRequest) -> CheckResponse:
    text = req.text.strip()
    auto_score = req.auto_score if req.auto_score is not None else True

    severity_result, severity_usage = llm.judge_severity(text, model=req.model)

    search_depth = severity_result["search_depth"]
    reason = severity_result["reason"]

    if auto_score:
        max_results = severity_result["max_results"]
        score_threshold = severity_result["score_threshold"]
    else:
        max_results = severity_result["max_results"]
        score_threshold = req.score_threshold if req.score_threshold is not None else severity_result["score_threshold"]
        reason = "Manual score threshold set by user."

    if req.max_results is not None:
        max_results = req.max_results

    raw_sources = tavily_client.search(
        query=text,
        search_depth=search_depth,
        max_results=max_results,
        score_threshold=score_threshold,
    )

    sources = [
        SourceResult(
            title=s.get("title", ""),
            url=s.get("url", ""),
            score=s.get("score", 0.0),
            content=s.get("content", ""),
        )
        for s in raw_sources
    ]

    summary, summary_usage = llm.summarize_fact_check(text, raw_sources, model=req.model)

    total_usage = TokenUsage(
        prompt_tokens=severity_usage["prompt_tokens"] + summary_usage["prompt_tokens"],
        completion_tokens=severity_usage["completion_tokens"] + summary_usage["completion_tokens"],
        total_tokens=severity_usage["total_tokens"] + summary_usage["total_tokens"],
    )

    return CheckResponse(
        severity=severity_result["severity"],
        severity_reasoning=severity_result["severity_reasoning"],
        tavily_settings=TavilySettings(
            search_depth=search_depth,
            max_results=max_results,
            score_threshold=score_threshold,
            reason=reason,
        ),
        summary=summary,
        sources=sources,
        token_usage=total_usage,
    )


@app.get("/models")
def models() -> dict:
    return {"models": llm.list_models(), "default": llm.DEFAULT_MODEL}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
