import json
import os
from typing import Optional

from openai import OpenAI

from .usage_logger import log_usage

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ["NEBIUS_API_KEY"].strip(),
            base_url="https://api.studio.nebius.com/v1",
        )
    return _client

DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"


def list_models() -> list[str]:
    client = get_client()
    return sorted(m.id for m in client.models.list().data)

SEVERITY_SYSTEM_PROMPT = """あなたはファクトチェックの前処理を行うアシスタントです。
ユーザーがハイライトしたテキストの重要度・深刻度を判定し、Web検索(Tavily)の設定パラメータを決定してください。

重要度が高い(例: 健康・安全・政治・経済・統計データ・重大な主張など)場合は、より深く広い検索(advanced, 多めのmax_results, 低めのscore_threshold)を、
重要度が低い(雑談・一般的な言い回し・主観的意見など)場合は軽量な検索(basic, 少なめのmax_results, 高めのscore_threshold)を選んでください。

重要: "severity_reasoning" と "reason" は必ず英語で書いてください。

以下のJSON形式のみで出力してください（説明文は不要）:
{
  "severity": "low" | "medium" | "high",
  "severity_reasoning": "判定理由を英語で簡潔に",
  "search_depth": "basic" | "advanced",
  "max_results": 3から10の整数,
  "score_threshold": 0.0から1.0の小数,
  "reason": "このTavily設定を選んだ理由を英語で簡潔に"
}
"""

SUMMARY_SYSTEM_PROMPT = """あなたはファクトチェックのアシスタントです。要約は必ず英語で書いてください。
ユーザーがハイライトした文章と、Web検索で得られた情報源を照らし合わせて、
その内容が事実として妥当か、誤りや誇張がないかを簡潔に要約してください。
情報源に基づかない推測は避け、根拠が不十分な場合はその旨を明記してください。
"""


def judge_severity(text: str, model: Optional[str] = None) -> tuple[dict, dict]:
    model = model or DEFAULT_MODEL
    client = get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SEVERITY_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    log_usage("judge_severity", model, response.usage)
    usage = response.usage.model_dump()
    return json.loads(response.choices[0].message.content), usage


def summarize_fact_check(text: str, sources: list[dict], model: Optional[str] = None) -> tuple[str, dict]:
    model = model or DEFAULT_MODEL
    client = get_client()
    sources_text = "\n\n".join(
        f"[{s['title']}]({s['url']}) score={s['score']:.2f}\n{s['content'][:500]}"
        for s in sources
    )
    user_content = f"対象文章: {text}\n\n検索結果:\n{sources_text}"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
    )
    log_usage("summarize_fact_check", model, response.usage)
    usage = response.usage.model_dump()
    return response.choices[0].message.content, usage
