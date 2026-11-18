# News Checker

A fact-checking service that uses an LLM and the Tavily search API to verify claims in a piece of text. Built as a personal project; full documentation below is in Japanese, with an English summary here.

## English Summary

**What it does**: paste or highlight any text (a news snippet, a social media post, a rumor) and the service judges how serious/sensitive the claim is, searches the web for supporting or contradicting sources via Tavily, and has an LLM summarize the findings and assign two scores: a **severity** level (low/medium/high) and a **truth score** (0–100%) estimating how well the specific claims in the text are actually corroborated by the retrieved sources (not just whether the topic is being reported at all — see "Truth score" section below for a bug I found and fixed in this distinction).

**Two frontends**:
- A **Chrome extension** (Manifest V3) — highlight text on any webpage and check it on the spot. Currently wired to a local backend only.
- An **iPhone-friendly web app** (`/app`) — deployed against the production backend on Render, installable to the home screen, and supports extracting text from a pasted screenshot via in-browser OCR (Tesseract.js, no image ever leaves the device).

**Backend**: FastAPI + SQLite, deployed on Render (free tier). The backend dynamically adjusts how deep the Tavily search goes (basic vs. advanced, number of results, score threshold) based on the LLM's severity judgment, then re-prompts the LLM with the retrieved sources to produce the summary and truth score. Every LLM call's token usage is logged to `logs/token_usage.jsonl`.

**Stack**: Python (FastAPI, Pydantic), SQLite, Nebius Token Factory (OpenAI-compatible LLM API, model `Qwen/Qwen3-30B-A3B-Instruct-2507`), Tavily Search API, vanilla JS Chrome extension, Tesseract.js for client-side OCR.

**Notable bug fix** (see the "Truth scoreの既知の問題と修正履歴" section for details): the truth score originally conflated "sources report this topic exists" with "the specific claim in the text is verified," which let unverified/speculative claims score as high as 95%. Fixed by rewriting the scoring prompt to explicitly separate those two questions.

---

LLMとTavily検索を使ってテキストをファクトチェックするサービスです。バックエンド（FastAPI）は本番でRenderに常時デプロイされており、フロントエンドとして次の2つがあります。

- **Chrome拡張機能**: Webページ上でハイライトしたテキストをその場でチェック。**ローカルのバックエンドのみに接続する設定のまま**（後述）
- **iPhone向けWebアプリ**（`/app`）: 本番バックエンド（Render）に接続。ホーム画面に追加してアプリのように使える。スクリーンショットからのテキスト抽出（OCR）にも対応

いずれのUIも、重要度バッジと**Truth score（真実度スコア、0〜100%）**バッジ、要約、情報源一覧を表示する。デザインはセリフ体の見出し＋温かみのある配色で、幅広い年齢層が読みやすいよう文字サイズ・タップ領域を大きめにしている。表示は英語で統一。

## 仕組み

1. テキストが送られると、LLM（Nebius Token Factory経由）がテキストの**重要度・深刻度**（low / medium / high）を判定
2. その判定結果に応じて、Tavily検索の設定を動的に変更する
   - 重要度が高い → 深い検索（`advanced`）、多めの検索結果数、低めのスコア閾値
   - 重要度が低い → 軽い検索（`basic`）、少なめの検索結果数、高めのスコア閾値
3. 決定した設定でTavily検索APIを呼び出し、関連情報源を取得（各結果に関連性スコア0.0〜1.0が付く）
4. LLMが検索結果を踏まえてファクトチェックの要約を生成
5. LLMが要約と情報源を踏まえて**真実度スコア（Truth score, 0〜100%）**を判定
6. 結果をSQLiteに保存し、`result_id` / `result_url`（`/result/{id}`）を含めてレスポンスを返す

## 本番環境

- **バックエンドURL**: `https://news-checker-5a5b.onrender.com`
- **ホスティング**: Render（無料プラン、Webサービス）
- **iPhone Webアプリ**: `https://news-checker-5a5b.onrender.com/app`
- **GitHubリポジトリ**: `Takakochan/news_checker`（public）。`master`ブランチへのpushでRenderが自動デプロイする

## ディレクトリ構成

```
news_checker/
├── backend/
│   ├── main.py            # APIエンドポイント (/check, /result/{id}, /app, /models, /health)
│   ├── llm.py              # LLM呼び出し（重要度判定・要約生成・真実度スコア判定）
│   ├── tavily_client.py    # Tavily検索API呼び出し
│   ├── db.py                # SQLiteへの結果保存・取得
│   ├── models.py            # リクエスト/レスポンスのPydanticモデル
│   ├── usage_logger.py      # トークン使用量のログ記録
│   └── static/
│       └── app.html         # iPhone向けWebアプリ（/appで配信、テンプレート変数を実行時に置換）
├── extension/                # Chrome拡張機能 (Manifest V3)。ローカルバックエンド専用のまま
│   ├── manifest.json
│   ├── background.js         # service worker。/checkの実際のfetchはここで行う
│   ├── config.js             # バックエンドURL・トークンの読み書き（storage.sync）
│   ├── content.js             # テキスト選択の検知とUI表示（/app・/resultと同じデザイン言語）、background.jsへメッセージ送信
│   ├── content.css            # ポップアップパネルのスタイル。/app・/resultと共通のセリフ体+温かみのある配色
│   ├── options.html / options.js  # 設定画面（モデル・Tavily設定・バックエンドURL/トークン）
│   └── popup.html / popup.js
├── passenger_wsgi.py       # 未使用。cPanel(Passenger)向けに作ったが、mixhostがPython App非対応のため本番はRenderへ移行済み
├── render.yaml              # Renderのサービス定義（無料プラン、ビルド/起動コマンド）
├── requirements.txt         # 全パッケージをバージョン固定
├── .env.example             # 必要な環境変数名の一覧（値は空）
├── data/                    # SQLite DB置き場（ローカル用。DB_PATHで変更可、Git管理外）
├── logs/
│   └── token_usage.jsonl   # LLM呼び出しごとのトークン使用量ログ
├── venv/                    # ローカル開発用Python仮想環境
└── .env                      # APIキー等（Git管理外）
```

## ローカルセットアップ

### 1. 仮想環境の有効化

```bash
cd news_checker
source venv/bin/activate
```

`requirements.txt` に記載のパッケージがインストール済みです。

### 2. 環境変数

`.env`（Git管理外）に以下を設定します。名前だけを記した雛形が `.env.example` にあります。

```
NEBIUS_API_KEY=（Nebius Token FactoryのAPIキー）
TAVILY_API_KEY=（TavilyのAPIキー）
DEMO_TOKEN=（/check の Authorization: Bearer <token> チェックに使う共通トークン。ローカル用と本番用で別の値を使っている）
DB_PATH=（省略可。SQLiteファイルの絶対パス。省略時は data/results.sqlite3）
```

### 3. バックエンドサーバーの起動

```bash
cd news_checker
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

### 4. Chrome拡張機能の読み込み（ローカルバックエンド専用）

Chrome拡張機能は**常にローカルのバックエンドを使う設計のまま**です（Renderには向けていません）。使う前に必ず手順3でローカルサーバーを起動しておく必要があります。

1. `uvicorn backend.main:app --port 8787` でローカルサーバーを起動しておく
2. Chromeで `chrome://extensions` を開く
3. 右上の「デベロッパーモード」をONにする
4. 「パッケージ化されていない拡張機能を読み込む」をクリック
5. リポジトリの `extension` フォルダを選択
6. 拡張機能の「Open Settings」を開き、Backend URLが `http://localhost:8787`、Backend Tokenが `.env` の `DEMO_TOKEN` と同じ値になっていることを確認（デフォルトでlocalhostを向いている）

以降、任意のWebページでテキストを選択すると「事実確認」ボタンが出ます。ローカルサーバーを止めると拡張機能は動かなくなります。

Renderの本番バックエンドに向けたい場合は、`extension/manifest.json` の `host_permissions` に本番ドメインを追加した上で、Options画面のBackend URL/Tokenを本番の値に変更する必要があります（未実施）。

## iPhone向けWebアプリの使い方

本番バックエンド（Render）にデプロイ済みなので、ローカルサーバーの起動は不要です。

1. iPhoneのSafariで `https://news-checker-5a5b.onrender.com/app` を開く
2. 共有ボタン → 「ホーム画面に追加」でアプリのように起動できるようにする
3. テキストを直接ペーストするか、「Extract text from a screenshot」ボタンで写真ライブラリからスクリーンショットを選ぶ
   - 画像はブラウザ内で Tesseract.js を使ってOCRされ（サーバーには送られない）、抽出結果がテキスト欄に自動入力される。内容を確認・編集してから送信できる
   - iOSはWeb Share Target APIを未対応のため、共有シートから直接このアプリを選ぶことはできない。「アプリを開く → 画像を選ぶ」という流れになる
4. 「Check the facts」をタップすると結果（重要度・要約・情報源）がその場に表示される
5. 「Open full result page」から `/result/{id}` のページも開ける

Renderの無料プランは一定時間アクセスがないとスリープするため、しばらく使っていないと最初の1回だけ起動に数十秒かかることがある。

## API概要

### `POST /check`

- 認証: `Authorization: Bearer <DEMO_TOKEN>` 必須（一致しないと401）
- リクエスト: `{ text, model?, max_results?, auto_score?, score_threshold? }`
- レスポンス: `{ severity, severity_reasoning, tavily_settings, summary, truth_score, sources[], token_usage, result_id, result_url }`
- `truth_score`: 0〜100の整数。対象文章の**具体的な主張**が情報源にどれだけ裏付けられているかを表す（「話題が報じられているか」ではなく「主張の中身が確認されているか」を採点するようプロンプトで明示している。過去に前者と混同して未確認情報に95%が付く不具合があり修正済み、詳細は後述）
- 呼び出しのたびに結果をSQLiteに保存し、`result_id`（一意なID）と`result_url`（`/result/{id}`への完全URL）を返す

### `GET /result/{id}`

- 認証不要。保存済みの結果をスマホ向けレイアウトのHTMLページとして返す（外部CSS/JS読み込みなし、日英ともに英語表記）
- 存在しないIDは404

### `GET /app`

- 認証不要（ページ自体はログイン不要で開けるが、ページ内から呼ぶ`/check`にはトークンが埋め込まれている）
- iPhone向けWebアプリのHTMLを返す。`backend/static/app.html` をテンプレートとして、リクエスト時に `__BACKEND_URL__` と `__DEMO_TOKEN__` を環境変数の値に置換して返す。そのためソースコード上にはトークンが残らない

### `GET /models` / `GET /health`

- 認証不要。モデル一覧とヘルスチェック用

iPhoneのショートカットからも `/check` に同じ形式（JSONボディ + Authorization ヘッダー）でPOSTすれば利用できる。

## トークン使用量ログ

LLM呼び出し（重要度判定・要約生成）のたびに `logs/token_usage.jsonl` に1行ずつ記録される。

```json
{"timestamp": 1789962989.83, "call": "judge_severity", "model": "Qwen/Qwen3-30B-A3B-Instruct-2507", "prompt_tokens": 299, "completion_tokens": 112, "total_tokens": 411}
```

- `call`: `judge_severity`（重要度判定）または `summarize_fact_check`（要約生成）
- `prompt_tokens` / `completion_tokens` / `total_tokens`: トークン数

## 使用しているモデル・API

- **LLM**: Nebius Token Factory（OpenAI互換API） / モデル: `Qwen/Qwen3-30B-A3B-Instruct-2507`
  - 利用可能なモデル一覧は `client.models.list()` で確認できる
- **検索**: Tavily Search API（`https://api.tavily.com/search`）
- **OCR**: Tesseract.js（`/app` ページ内、ブラウザ側で完結。サーバー側の処理は無い）

## Renderへのデプロイ

### 経緯

当初はmixhostのcPanelにPassenger/WSGI経由でデプロイする予定で `passenger_wsgi.py` を用意したが、mixhostはSetup Python App機能を提供していないことが判明したため、Renderへ切り替えた（`passenger_wsgi.py` はリポジトリに残っているが未使用）。

### Render側の設定

GitHubリポジトリ `Takakochan/news_checker` の `master` ブランチを接続したWeb Serviceとして稼働中。設定内容は `render.yaml` にも記述してあるが、実際のサービスはRenderダッシュボード上で手動フォーム入力して作成した。

| 項目 | 値 |
|---|---|
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT` |
| Plan | Free（$0/month） |

**注意**: 無料プランはPersistent Diskに対応していないため、デプロイやコンテナの再起動のたびにSQLite（`data/results.sqlite3`）の中身は消える。結果の永続的な保存が必要になったら、有料のStarterプラン以上 + Persistent Diskへの切り替えが必要。

### 環境変数（Renderダッシュボードの Environment タブ）

| 変数名 | 説明 |
|---|---|
| `NEBIUS_API_KEY` | Nebius Token Factory APIキー |
| `TAVILY_API_KEY` | Tavily APIキー |
| `DEMO_TOKEN` | `/check` の認証トークン。本番用に生成したランダムな文字列（ローカルの`.env`とは別の値） |

`DB_PATH` は設定していない（未設定時のデフォルト `data/results.sqlite3` を使用。無料プランではどのみち永続化されないため）。

### 継続的なデプロイ

GitHubリポジトリの `master` ブランチにpushすると、Renderが自動的にビルド・デプロイする（Auto-Deploy設定がデフォルトで有効）。手動で再デプロイしたい場合はRenderダッシュボードの「Manual Deploy」から行う。

## GitHubリポジトリとデプロイ鍵

- リポジトリ: `Takakochan/news_checker`（public）
- Render用にGitHub OAuth連携を許可済み（Renderダッシュボードから作成したWeb Service経由）
- 当初mixhost向けに作成したSSHデプロイ鍵やGitHub Deploy Key、Fine-grained Personal Access Tokenは、cPanelデプロイを断念した後に整理済み（未使用のGitHub Deploy Keyは削除済み）

## Truth scoreの既知の問題と修正履歴

初回実装時、`truth_score`が「情報源がその話題・出来事を報じているか」を採点してしまい、「対象文章の具体的な主張（原因・正体など）が確認されているか」とは別物であることを区別できていなかった。

例: テヘラン上空の謎の発光体についての文章で、要約は「正体は未確認」「当局の公式発表なし」「証拠は決定的ではない」と結論づけているにもかかわらず、`truth_score`が95%になっていた（情報源がこの目撃情報自体を複数報じていたことをもって高評価してしまっていた）。

`backend/llm.py` の `TRUTH_SCORE_SYSTEM_PROMPT` を修正し、「出来事が報じられている事実」と「対象文章の具体的な主張が確認されているか」を明示的に区別し、未確認・憶測の内容は40〜59の範囲に収まるよう採点基準を明文化した。修正後は同じ文章で55%程度になることを確認済み。プロンプトを変更する際は、この区別を崩さないよう注意する。

なお `judge_severity` と `summarize_fact_check` のプロンプト・ロジックは、ユーザーからの要望により変更していない。`truth_score` は別関数 `score_truth` として独立させてある。

## Kubernetes運用（SRE学習用インフラ）

Renderの本番とは別に、`infra/`・`deploy/`配下に、同じアプリをHetzner Cloud + k3s上でTerraform→Ansible→Helm→GitOps(Argo CD)→監視という構成で動かす学習用インフラが入っている。Renderの運用には影響しない。

- `infra/terraform/`: Hetzner VM + ファイアウォールの定義
- `infra/ansible/`: VMの初期設定（`deploy`ユーザー、SSH鍵認証限定、ufw、自動更新、k3s）
- `deploy/helm/news-checker/`: アプリのHelm chart（Deployment/Service/Ingress/Secret）
- `deploy/cert-manager/`: Let's Encrypt用のClusterIssuer
- `deploy/argocd/`: Argo CDのApplication定義（GitOpsでこのリポジトリを自動sync）
- `deploy/monitoring/`: kube-prometheus-stackの values とアラートルール

公開URL: `https://49.13.129.122.nip.io`（IPアドレスは変わる可能性がある。実際の値は`terraform output`で確認）

### Runbook（よくある操作・障害対応）

**VMにSSH接続する**
```bash
ssh deploy@<server_ipv4>
```
`root`では接続できない（`PermitRootLogin no`）。`deploy`ユーザーはNOPASSWDでsudo可能。

**クラスタの状態をざっくり確認する**
```bash
ssh deploy@<ip> "sudo k3s kubectl get pods -A | grep -v Running | grep -v Completed"
```
何も出なければ異常Podなし。

**kubectl/helmを使う（kubeconfigがroot専有のため）**
```bash
ssh deploy@<ip> "sudo k3s kubectl get nodes"
ssh deploy@<ip> "sudo KUBECONFIG=/etc/rancher/k3s/k3s.yaml helm list -A"
```

**Argo CDの同期状態を確認する**
```bash
ssh deploy@<ip> "sudo k3s kubectl get application news-checker -n argocd -o jsonpath='{.status.sync.status} {.status.health.status}'"
```
`Synced`/`Healthy`以外なら、まずGitの最新commitとズレていないか（`.status.sync.revision`）を見る。

**アラートの発火状況を確認する**
```bash
curl -s https://alertmanager.<ip>.nip.io/api/v2/alerts | python3 -m json.tool
```

**クラスタへの変更は必ずGitの変更として行う**
VM上で直接`kubectl edit`や`helm upgrade --set`をしても、Argo CDの`selfHeal`が次の同期で必ずGitの状態に戻す。変更したいなら、該当する`deploy/helm/news-checker/values.yaml`等をコミット・pushする。

### 既知の障害とその対処

| 症状 | 原因 | 対処 |
|---|---|---|
| HTTPS証明書が`unable to get local issuer certificate`になる | `letsencrypt-staging`発行者を使っている（テスト用、信頼されないルート） | `values.yaml`の`ingress.clusterIssuer`を`letsencrypt-prod`にしてpush |
| 証明書発行が`Timeout during connect`で失敗 | Hetznerのクラウドファイアウォールで80/443が塞がれている（`ufw`だけ開けても届かない） | `infra/terraform/main.tf`の`hcloud_firewall`に80/443のルールがあるか確認し、`terraform apply` |
| SecretのAPIキーが急に空になる・`/check`が401/500になる | Argo CDの`sync`が`ignoreDifferences`対象のSecretを上書きした（`RespectIgnoreDifferences=true`が無いと表示上の無視だけで実際の適用には効かない） | `deploy/argocd/application.yaml`の`syncOptions`に`RespectIgnoreDifferences=true`があるか確認。値は`helm upgrade --set secrets.xxx=...`で復旧 |
| VM上で直接直した設定（ClusterIssuer・レプリカ数など）が勝手に元に戻る | Argo CDの`selfHeal`がGitの状態に戻している | Gitの値そのものを直してpushする（上記「クラスタへの変更は必ずGitの変更として行う」参照） |
| `kube-prometheus-stack`導入後にload averageが急騰し、APIサーバーが応答しなくなる | VMの容量不足（cx23=2vCPU/4GBではフルの監視スタックは入らない） | `helm uninstall kube-prometheus-stack -n monitoring`で緊急停止、VMを`cx33`以上にリサイズ（`infra/terraform/variables.tf`の`server_type`） |
| ArgoCDの`ApplicationSet`コントローラーがCrashLoopBackOff、ログに`no matches for kind "ApplicationSet"` | 高負荷時にCRD自体がクラスタから失われた | `kubectl apply --server-side --force-conflicts -f <argocdのinstall.yaml>`で再適用（CRDが大きく通常の`apply`は256KiBのannotation上限に引っかかるため`--server-side`が必要） |
| Grafanaに繋がらない（タイムアウト、ログに`Handler timeout`） | Grafana 13系の内部APIレイヤーの既知の不具合（リソース不足ではない） | Alertmanager/Prometheus自体は別物なので実害は小さい。直すなら`deploy/monitoring/values.yaml`で`grafana.image.tag`を安定版に固定 |

### 全部壊して作り直す／止める

```bash
cd infra/terraform
terraform destroy   # VM・ファイアウォール・SSH鍵を全部削除、課金が止まる
```

再構築する場合は `terraform apply` → Ansible playbook実行 → Helmでcert-manager/Argo CD/監視スタックを入れ直す → `deploy/argocd/application.yaml`を適用、の順。すべてコードになっているので手順通りにやれば同じ状態に戻せる。

## 注意点

- ローカル開発時のバックエンドはデフォルトでポート `8787` を使用する。
- `.env` はGit管理から除外されている（`.gitignore`参照）。`data/`（SQLite DB）も同様にGit管理外。
- 拡張機能のバックエンドURL・トークンは `extension/config.js` 経由で `chrome.storage.sync` に保存され、Options画面から設定する。ソースコードにURLやキーはハードコードしていない。
- `extension/manifest.json` の `host_permissions` には `http://localhost:8787/*` と、未使用のプレースホルダー `https://example.com/*` が入っている。
- `backend/static/app.html` にはビルド時・コミット時点ではプレースホルダー（`__BACKEND_URL__` / `__DEMO_TOKEN__`）のみが入っており、実際の値は `GET /app` のリクエスト時にサーバー側で環境変数から差し込まれる。
