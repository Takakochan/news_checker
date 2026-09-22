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
├── backend/
│   ├── main.py           # APIエンドポイント (/check, /result/{id}, /models, /health)
│   ├── llm.py            # LLM呼び出し（重要度判定・要約生成）
│   ├── tavily_client.py  # Tavily検索API呼び出し
│   ├── db.py             # SQLiteへの結果保存・取得
│   ├── models.py         # リクエスト/レスポンスのPydanticモデル
│   └── usage_logger.py   # トークン使用量のログ記録
├── extension/                # Chrome拡張機能 (Manifest V3)
│   ├── manifest.json
│   ├── background.js         # service worker。/checkの実際のfetchはここで行う
│   ├── config.js             # バックエンドURL・トークンの読み書き（storage.sync）
│   ├── content.js             # テキスト選択の検知とUI表示、background.jsへメッセージ送信
│   ├── content.css
│   ├── options.html / options.js  # 設定画面（モデル・Tavily設定・バックエンドURL/トークン）
│   └── popup.html / popup.js
├── passenger_wsgi.py     # cPanel(Passenger/WSGI)用エントリーポイント。application変数を公開
├── requirements.txt       # 全パッケージをバージョン固定
├── .env.example           # 必要な環境変数名の一覧（値は空）
├── data/                  # SQLite DB置き場（デフォルト。DB_PATHで変更可、Git管理外）
├── logs/
│   └── token_usage.jsonl # LLM呼び出しごとのトークン使用量ログ
├── venv/                 # ローカル開発用Python仮想環境
└── .env                  # APIキー等（Git管理外）
```

## セットアップ

### 1. 仮想環境の有効化

```bash
cd /Users/takako/news_checker
source venv/bin/activate
```

すでに以下がインストール済みです: `openai`, `pydantic`, `python-dotenv`, `fastapi`, `uvicorn`

### 2. 環境変数

`.env`（Git管理外）に以下を設定します。名前だけを記した雛形が `.env.example` にあります。

```
NEBIUS_API_KEY=（Nebius Token FactoryのAPIキー）
TAVILY_API_KEY=（TavilyのAPIキー）
DEMO_TOKEN=（/check の Authorization: Bearer <token> チェックに使う共通トークン）
DB_PATH=（省略可。SQLiteファイルの絶対パス。省略時は data/results.sqlite3）
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
5. 拡張機能の「Open Settings」からBackend URL（バックエンドのベースURL）とBackend Token（`DEMO_TOKEN`と同じ値）を設定して保存

以降、任意のWebページでテキストを選択すると「事実確認」ボタンが出ます。

## 使い方

1. バックエンドサーバーを起動しておく（上記手順3）
2. 拡張機能の設定でBackend URL / Backend Tokenを設定しておく（上記手順4-5）
3. 任意のWebページでファクトチェックしたい文章をドラッグして選択
4. 出てきた「事実確認」ボタンをクリック
5. ポップアップに以下が表示される
   - **重要度バッジ**（低・中・高）とその判定理由
   - **Tavily設定**（search_depth / max_results / score_threshold）とLLMが選んだ理由
   - **要約**（事実確認の結果）
   - **情報源一覧**（各情報源のタイトル・関連性スコア・抜粋・リンク）
   - **結果ページへのリンク**（`/result/{id}`。スマホでも見られるHTMLページ、外部CSS/JSなし）

## API概要

### `POST /check`

- 認証: `Authorization: Bearer <DEMO_TOKEN>` 必須（一致しないと401）
- リクエスト: `{ text, model?, max_results?, auto_score?, score_threshold? }`
- レスポンス: `{ severity, severity_reasoning, tavily_settings, summary, sources[], token_usage, result_id, result_url }`
- 呼び出しのたびに結果をSQLiteに保存し、`result_id`（一意なID）と`result_url`（`/result/{id}`への完全URL）を返す

### `GET /result/{id}`

- 認証不要。保存済みの結果をスマホ向けレイアウトのHTMLページとして返す（外部CSS/JS読み込みなし）
- 存在しないIDは404

### `GET /models` / `GET /health`

- 認証不要。モデル一覧とヘルスチェック用（変更なし）

iPhoneのショートカットからも `/check` に同じ形式（JSONボディ + Authorization ヘッダー）でPOSTすれば利用できます。

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

- ローカル開発時のバックエンドはデフォルトでポート `8787` を使用します。
- `.env` はGit管理から除外されています（`.gitignore`参照）。`data/`（SQLite DB）も同様にGit管理外です。
- 拡張機能のバックエンドURL・トークンは `extension/config.js` 経由で `chrome.storage.sync` に保存され、options画面から設定します。ソースコードにURLやキーはハードコードしていません。
- `extension/manifest.json` の `host_permissions` には現在プレースホルダー `https://example.com/*` が入っています。cPanelデプロイ後、実際のバックエンドドメインに置き換える必要があります。

## cPanelへのデプロイ（Setup Python App / Passenger）

### 事前準備

- `requirements.txt`・`passenger_wsgi.py`はリポジトリに含まれている
- `passenger_wsgi.py` は `a2wsgi.ASGIMiddleware` で `backend.main:app`（FastAPI）を包み、変数名 `application` として公開している
- ローカルで `python -c "import passenger_wsgi"` がエラーなく通ることを確認済み

### cPanel側の設定（Setup Python App）

| 項目 | 値 |
|---|---|
| Application root | リポジトリのルート（`passenger_wsgi.py`がある場所） |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |
| Python version | 3.9系（開発環境と合わせる。使えるなら新しめでも可） |

デプロイ後、cPanelのvirtualenv内で:

```bash
pip install -r requirements.txt
```

### 環境変数（cPanelの Environment variables）

| 変数名 | 説明 |
|---|---|
| `NEBIUS_API_KEY` | Nebius Token Factory APIキー |
| `TAVILY_API_KEY` | Tavily APIキー |
| `DEMO_TOKEN` | `/check` の認証トークン。拡張機能とiPhoneショートカットで共通利用する、推測困難な文字列 |
| `DB_PATH` | SQLite DBの絶対パス。公開Webルートの外（例: `/home/<user>/private/news_checker/results.sqlite3`）を指定する |

`.env` ファイル自体はcPanelにアップロードせず、cPanelの環境変数機能側で設定する。

### デプロイ後の残作業

- 実際のバックエンドドメインが決まり次第、`extension/manifest.json` の `host_permissions` を `https://example.com/*` から実ドメインに置き換える
- 拡張機能のoptionsページでBackend URL / Backend Tokenを設定する

### 継続的なデプロイ（更新の反映方法）

cPanelでSSHアクセスとGit Version Controlが使えるかどうかで運用方法が変わる（要確認・未確定）。有力な候補:

1. **SSH + git pull**（推奨・最もシンプル）: サーバー上にリポジトリをcloneしておき、更新のたびに `ssh user@host 'cd app && git pull && touch tmp/restart.txt'` を実行する。`tmp/restart.txt` の作成でPassengerアプリが再起動される
2. **cPanel Git Version Control機能**: cPanel UI上でリポジトリを登録し、「Pull or Deploy」から更新を取り込む
3. **SSHが使えない場合**: File Manager/FTPで変更ファイルを手動アップロードし、`tmp/restart.txt` を作成して再起動する

→ SSH/Git機能の有無を確認後、この節に具体的な手順・デプロイスクリプトを追記する。
