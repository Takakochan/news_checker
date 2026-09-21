# News Checker

Webページ上でハイライトしたテキストを、LLMとTavily検索を使ってファクトチェックするChrome拡張機能です。

## 仕組み

1. ユーザーがページ上のテキストをハイライトすると「事実確認」ボタンが表示される
2. ボタンを押すと、ハイライトしたテキストがバックエンドに送られる
3. LLM（Nebius Token Factory経由）がテキストの**重要度・深刻度**（low / medium / high）を判定
4. その判定結果に応じて、Tavily検索の設定を動的に変更する
   - 重要度が高い → 深い検索（`advanced`）、多めの検索結果数、低めのスコア閾値
   - 重要度が低い → 軽い検索（`basic`）、少なめの検索結果数、高めのスコア閾値
5. 決定した設定でTavily検索APIを呼び出し、関連情報源を取得（各結果に関連性スコア0.0〜1.0が付く）
6. LLMが検索結果を踏まえてファクトチェックの要約を生成
7. 拡張機能のポップアップに「重要度」「使用したTavily設定とその理由」「要約」「情報源とスコア」を表示

## ディレクトリ構成

```
news_checker/
├── backend/              # FastAPIバックエンド
│   ├── main.py           # APIエンドポイント (/check, /health)
│   ├── llm.py            # LLM呼び出し（重要度判定・要約生成）
│   ├── tavily_client.py  # Tavily検索API呼び出し
│   ├── models.py         # リクエスト/レスポンスのPydanticモデル
│   └── usage_logger.py   # トークン使用量のログ記録
├── extension/            # Chrome拡張機能 (Manifest V3)
│   ├── manifest.json
│   ├── content.js        # テキスト選択の検知とUI表示
│   └── content.css
├── logs/
│   └── token_usage.jsonl # LLM呼び出しごとのトークン使用量ログ
├── venv/                 # Python仮想環境
└── .env                  # APIキー（NEBIUS_API_KEY, TAVILY_API_KEY）
```

## セットアップ

### 1. 仮想環境の有効化

```bash
cd /Users/takako/news_checker
source venv/bin/activate
```

すでに以下がインストール済みです: `openai`, `pydantic`, `python-dotenv`, `fastapi`, `uvicorn`

### 2. APIキー

`.env` に以下が設定済みです。

```
NEBIUS_API_KEY=（Nebius Token FactoryのAPIキー）
TAVILY_API_KEY=（TavilyのAPIキー）
```

### 3. バックエンドサーバーの起動

```bash
cd /Users/takako/news_checker
source venv/bin/activate
uvicorn backend.main:app --port 8787
```

起動確認:

```bash
curl http://localhost:8787/health
# {"status":"ok"}
```

サーバーを止めるときは:

```bash
pkill -f "uvicorn backend.main"
```

### 4. Chrome拡張機能の読み込み

1. Chromeで `chrome://extensions` を開く
2. 右上の「デベロッパーモード」をONにする
3. 「パッケージ化されていない拡張機能を読み込む」をクリック
4. `/Users/takako/news_checker/extension` フォルダを選択

以降、任意のWebページでテキストを選択すると「事実確認」ボタンが出ます。

## 使い方

1. バックエンドサーバーを起動しておく（上記手順3）
2. 任意のWebページでファクトチェックしたい文章をドラッグして選択
3. 出てきた「事実確認」ボタンをクリック
4. ポップアップに以下が表示される
   - **重要度バッジ**（低・中・高）とその判定理由
   - **Tavily設定**（search_depth / max_results / score_threshold）とLLMが選んだ理由
   - **要約**（事実確認の結果）
   - **情報源一覧**（各情報源のタイトル・関連性スコア・抜粋・リンク）

## トークン使用量ログ

LLM呼び出し（重要度判定・要約生成）のたびに `logs/token_usage.jsonl` に1行ずつ記録されます。

```json
{"timestamp": 1789962989.83, "call": "judge_severity", "model": "Qwen/Qwen3-30B-A3B-Instruct-2507", "prompt_tokens": 299, "completion_tokens": 112, "total_tokens": 411}
```

- `call`: `judge_severity`（重要度判定）または `summarize_fact_check`（要約生成）
- `prompt_tokens` / `completion_tokens` / `total_tokens`: トークン数

## 使用しているモデル・API

- **LLM**: Nebius Token Factory（OpenAI互換API） / モデル: `Qwen/Qwen3-30B-A3B-Instruct-2507`
  - 利用可能なモデル一覧は `client.models.list()` で確認できます
- **検索**: Tavily Search API（`https://api.tavily.com/search`）

## 注意点

- バックエンドはデフォルトでポート `8787` を使用します（`8000`が別プロセスで使用中だったため変更済み）。ポートを変更する場合は `extension/manifest.json` の `host_permissions` と `extension/content.js` の `API_URL` も合わせて変更してください。
- `.env` はGit管理から除外されています（`.gitignore`参照）。
