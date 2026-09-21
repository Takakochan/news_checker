import json
import time
from pathlib import Path

LOG_PATH = Path(__file__).parent.parent / "logs" / "token_usage.jsonl"


def log_usage(call_name: str, model: str, usage) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.time(),
        "call": call_name,
        "model": model,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
