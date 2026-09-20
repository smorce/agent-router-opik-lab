# LLM Gateway Architecture

## 目的

Applicationが特定のLLM Providerへ直接依存せず、Task Routerでモデルを解決し、Agent Routerを共通のOpenAI互換Gatewayとして利用する。

## 現在の経路

```text
Application
  |
  v
DummyTaskRouter
  |  Auto -> qwen3.8-27b-exl3-3.5bpw-wm
  v
Agent Router :1975/v1
  |
  v
llama-server :2067/v1
  |
  v
Qwen local model

Agent Router -- OTLP HTTP/protobuf --> Opik :5181
```

## 境界

### Task Router

- `TaskRouter` Protocolを実装する。
- `RouteDecision`にmodel、provider、reasonを返す。
- モデル選択だけを担当し、HTTP通信を行わない。
- `Auto`解決をDummy実装からClassifier、LLM、MoE実装へ差し替えられる。

### Agent Router

- ApplicationへOpenAI互換APIを提供する。
- Backendへの通信、Provider差分、将来のFallback、Retry、Rate Limitの境界になる。
- Standalone開発では`aigw run`と環境変数自動設定を使用する。

### Opik

- Agent RouterのOpenTelemetry Traceを収集する。
- Trace、latency、token usage、cost、evaluationを担当する。
- Routing判断は担当しない。

## Retry

OpenAI SDKの自動Retryは`max_retries=0`にし、Application側ではAgent Routerとの接続エラー、timeout、5xxだけを少数回Retryする。Provider単位のRetryやFallbackを将来Agent Routerへ移せるよう、Application側にProvider条件分岐を増やさない。

## Generation parameters

Chat Completionsを標準経路とし、llama.cpp固有値は`extra_body`で渡す。

```text
temperature
top_p
max_tokens
extra_body.top_k
extra_body.min_p
extra_body.chat_template_kwargs.enable_thinking
```

Responses APIは削除せず、`LLM_API_STYLE=responses`で選択できる。Agent Router 1.1の公式仕様では `POST /v1/responses` はFully Supportedである。実測では llama-server 直接（Test A）も Agent Router 経由（Test B）も 404 で、起点は `:2067` の aiohttp/exl3 サーバーが Responses 未実装なことである。今回の初期経路は Chat Completions で問題ない。Responses を通したいなら、`:2067` 側が `/v1/responses` を実装する必要がある。

## セキュリティと観測

- API keyとAuthorization headerはログへ出さない。
- Applicationログへプロンプト全文を出さない。
- Applicationは `X-Request-ID` と `X-Session-ID` に加え、Agent Router既定の `agent-session-id` も送る。
- Agent Routerは Header Mapping で `x-session-id → session.id` と `x-request-id → request.id` をspanへ写す。
- `OPENINFERENCE_HIDE_INPUTS`と`OPENINFERENCE_HIDE_OUTPUTS`で内容の収集を制御する。
- 本番で入力・出力を保存する前に、個人情報・機密情報の扱いを確認する。
