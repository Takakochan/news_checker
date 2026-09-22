from dotenv import load_dotenv

load_dotenv()

import html
import os
from pathlib import Path

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

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/app", response_class=HTMLResponse)
def app_page(request: Request) -> HTMLResponse:
    template = (STATIC_DIR / "app.html").read_text(encoding="utf-8")
    backend_url = str(request.base_url).rstrip("/")
    demo_token = os.environ.get("DEMO_TOKEN", "")
    html_content = template.replace("__BACKEND_URL__", backend_url).replace("__DEMO_TOKEN__", demo_token)
    return HTMLResponse(content=html_content)


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


SEVERITY_LABELS = {"low": "Low severity", "medium": "Medium severity", "high": "High severity"}


def render_result_html(result_id: str, data: dict) -> str:
    severity = data["severity"]
    label = html.escape(SEVERITY_LABELS.get(severity, severity))
    summary = html.escape(data["summary"]).replace("\n", "<br/>")
    reasoning = html.escape(data["severity_reasoning"])

    sources_html = "".join(
        f"""
        <div class="source">
          <div class="source-top">
            <a href="{html.escape(s['url'])}" target="_blank" rel="noopener noreferrer">{html.escape(s['title'] or s['url'])}</a>
            <span class="score">match {round(s['score'] * 100)}%</span>
          </div>
          <div class="excerpt">{html.escape((s['content'] or '')[:200])}...</div>
        </div>"""
        for s in data["sources"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
<title>News Checker Result</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    color-scheme: light dark;
    --ink: #1c2321;
    --ink-soft: #4b5754;
    --paper: #faf7f0;
    --card: #ffffff;
    --line: #e2dfd3;
    --accent: #0f6b5c;
    --accent-soft: #e4efe9;
    --low-bg: #e5f3e9; --low-fg: #1e6b3c;
    --med-bg: #fbecd7; --med-fg: #8a5a00;
    --high-bg: #fbe4e1; --high-fg: #b23223;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --ink: #f1efe8;
      --ink-soft: #b9c2bd;
      --paper: #14181a;
      --card: #1d2324;
      --line: #303735;
      --accent: #4fbfa5;
      --accent-soft: #223530;
      --low-bg: #1c3324; --low-fg: #7fd89b;
      --med-bg: #3a2c10; --med-fg: #f0b64c;
      --high-bg: #3a1e1a; --high-fg: #f19488;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: "Source Sans 3", -apple-system, sans-serif;
    max-width: 640px;
    margin: 0 auto;
    padding: 20px;
    padding-top: max(24px, env(safe-area-inset-top));
    padding-bottom: max(32px, env(safe-area-inset-bottom));
    color: var(--ink);
    background: var(--paper);
    font-size: 17px;
    line-height: 1.5;
  }}
  h1 {{
    font-family: "Source Serif 4", Georgia, serif;
    font-size: 26px;
    font-weight: 700;
    margin: 0 0 16px;
  }}
  .badge {{
    display: inline-block;
    padding: 6px 14px;
    border-radius: 999px;
    font-size: 15px;
    font-weight: 700;
  }}
  .badge.low {{ background: var(--low-bg); color: var(--low-fg); }}
  .badge.medium {{ background: var(--med-bg); color: var(--med-fg); }}
  .badge.high {{ background: var(--high-bg); color: var(--high-fg); }}
  .reasoning {{ margin-top: 10px; color: var(--ink-soft); font-size: 15px; }}
  .block {{
    margin-top: 18px;
    padding: 18px;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 14px;
  }}
  .label {{
    font-family: "Source Serif 4", Georgia, serif;
    font-weight: 700;
    font-size: 20px;
    margin: 0 0 10px;
  }}
  .source {{ padding: 14px 0; border-top: 1px solid var(--line); }}
  .source:first-of-type {{ border-top: none; padding-top: 4px; }}
  .source-top {{ display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }}
  .source a {{ font-weight: 600; color: var(--accent); text-decoration: none; word-break: break-word; }}
  .score {{ font-size: 13px; color: var(--ink-soft); white-space: nowrap; }}
  .excerpt {{ font-size: 15px; color: var(--ink-soft); margin-top: 6px; }}
</style>
</head>
<body>
  <h1>News Checker Result</h1>
  <span class="badge {severity}">{label}</span>
  <div class="reasoning">{reasoning}</div>
  <div class="block">
    <div class="label">Summary</div>
    <div>{summary}</div>
  </div>
  <div class="block">
    <div class="label">Sources</div>
    {sources_html or '<div>No sources were found for this claim.</div>'}
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
