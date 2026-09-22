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

TRUTH_SCORE_SYSTEM_PROMPT = """あなたはファクトチェックのアシスタントです。
ユーザーがハイライトした文章（「対象文章」）が主張している具体的な内容が、どれだけ事実として正確かを
0から100の真実度スコアで採点してください。

重要: 「その話題がニュースやSNSで報じられている・話題になっている」という事実と、
「対象文章が主張している具体的な内容（原因・正体・結論など）が正しいかどうか」は別物です。
情報源が単にその出来事や話題の存在を報じているだけで、対象文章の具体的な主張（例: 原因の特定、
正体の断定、真偽の判定）そのものを裏付けていない場合は、高いスコアをつけてはいけません。

採点の目安:
- 90-100: 対象文章の具体的な主張が、複数の信頼できる情報源によって明確に確認されている
- 60-89: 主張の大筋は支持されているが、細部に不確実性がある
- 40-59: 情報源が不十分、主張が未確認、あるいは出来事自体は報じられているが具体的な主張（原因・正体など）は
  まだ特定されていない、憶測の域を出ない場合。「〜については未確認」「憶測」「正体不明」といった
  要約になっている場合は、必ずこの範囲にしてください
- 10-39: 主張の大筋が情報源と矛盾している、または誇張されている
- 0-9: 情報源によって明確に否定されている、または捏造・誤りである

以下のJSON形式のみで出力してください（説明文は不要）:
{
  "truth_score": 0から100の整数
}
"""


def score_truth(text: str, sources: list[dict], summary: str, model: Optional[str] = None) -> tuple[int, dict]:
    model = model or DEFAULT_MODEL
    client = get_client()
    sources_text = "\n\n".join(
        f"[{s['title']}]({s['url']}) score={s['score']:.2f}\n{s['content'][:500]}"
        for s in sources
    )
    user_content = f"対象文章: {text}\n\n検索結果:\n{sources_text}\n\n要約: {summary}"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": TRUTH_SCORE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    log_usage("score_truth", model, response.usage)
    usage = response.usage.model_dump()
    result = json.loads(response.choices[0].message.content)
    score = int(result["truth_score"])
    return max(0, min(100, score)), usage


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
