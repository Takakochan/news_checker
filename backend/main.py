from dotenv import load_dotenv

load_dotenv()

import html
import os

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from . import db, llm, tavily_client
from .models import CheckRequest, CheckResponse, SourceResult, TavilySettings, TokenUsage

app = FastAPI(title="News Checker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_auth(authorization: str = Header(default=None)) -> None:
    expected = os.environ.get("DEMO_TOKEN")
    if not expected:
        raise HTTPException(status_code=500, detail="DEMO_TOKEN is not configured on the server.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = authorization[len("Bearer "):].strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Invalid token.")


@app.post("/check", response_model=CheckResponse)
def check(req: CheckRequest, request: Request, authorization: str = Header(default=None)) -> CheckResponse:
    require_auth(authorization)
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

    tavily_settings = TavilySettings(
        search_depth=search_depth,
        max_results=max_results,
        score_threshold=score_threshold,
        reason=reason,
    )

    result_id = db.save_result(
        {
            "text": text,
            "severity": severity_result["severity"],
            "severity_reasoning": severity_result["severity_reasoning"],
            "tavily_settings": tavily_settings.model_dump(),
            "summary": summary,
            "sources": [s.model_dump() for s in sources],
            "token_usage": total_usage.model_dump(),
        }
    )
    result_url = str(request.base_url).rstrip("/") + f"/result/{result_id}"

    return CheckResponse(
        severity=severity_result["severity"],
        severity_reasoning=severity_result["severity_reasoning"],
        tavily_settings=tavily_settings,
        summary=summary,
        sources=sources,
        token_usage=total_usage,
        result_id=result_id,
        result_url=result_url,
    )


SEVERITY_LABELS = {"low": "Severity: Low", "medium": "Severity: Medium", "high": "Severity: High"}
SEVERITY_COLORS = {"low": "#34a853", "medium": "#f9ab00", "high": "#d93025"}


def render_result_html(result_id: str, data: dict) -> str:
    severity = data["severity"]
    label = html.escape(SEVERITY_LABELS.get(severity, severity))
    color = SEVERITY_COLORS.get(severity, "#5f6368")
    summary = html.escape(data["summary"]).replace("\n", "<br/>")
    reasoning = html.escape(data["severity_reasoning"])
    settings = data["tavily_settings"]

    sources_html = "".join(
        f"""
        <div class="source">
          <div class="score">score {s['score']:.2f}</div>
          <a href="{html.escape(s['url'])}" target="_blank" rel="noopener noreferrer">{html.escape(s['title'] or s['url'])}</a>
          <div class="excerpt">{html.escape((s['content'] or '')[:200])}...</div>
        </div>"""
        for s in data["sources"]
    )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>News Checker Result</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 640px; margin: 0 auto; padding: 16px; color: #202124; }}
  h1 {{ font-size: 18px; }}
  .badge {{ display: inline-block; padding: 4px 10px; border-radius: 12px; color: #fff; font-size: 13px; background: {color}; }}
  .block {{ margin-top: 16px; padding: 12px; background: #f8f9fa; border-radius: 8px; }}
  .source {{ margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee; }}
  .source a {{ font-weight: 600; color: #1a73e8; word-break: break-all; }}
  .score {{ font-size: 12px; color: #5f6368; }}
  .excerpt {{ font-size: 13px; color: #3c4043; margin-top: 4px; }}
  .label {{ font-weight: 600; font-size: 13px; color: #5f6368; }}
</style>
</head>
<body>
  <h1>News Checker Result</h1>
  <span class="badge">{label}</span>
  <div class="block">
    <div class="label">Severity Reasoning</div>
    <div>{reasoning}</div>
  </div>
  <div class="block">
    <div class="label">Summary</div>
    <div>{summary}</div>
  </div>
  <div class="block">
    <div class="label">Tavily Settings</div>
    <div>search_depth: {html.escape(settings['search_depth'])}</div>
    <div>max_results: {settings['max_results']}</div>
    <div>score_threshold: {settings['score_threshold']}</div>
    <div>Reason: {html.escape(settings['reason'])}</div>
  </div>
  <div class="block">
    <div class="label">Sources</div>
    {sources_html or '<div>No sources.</div>'}
  </div>
</body>
</html>"""


@app.get("/result/{result_id}", response_class=HTMLResponse)
def result_page(result_id: str) -> HTMLResponse:
    data = db.get_result(result_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Result not found.")
    return HTMLResponse(content=render_result_html(result_id, data))


@app.get("/models")
def models() -> dict:
    return {"models": llm.list_models(), "default": llm.DEFAULT_MODEL}


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
