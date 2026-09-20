# ローカルLLMを「そのまま」使わない——Agent Router + Opik で始める観測可能なゲートウェイ

ローカルで Qwen などの LLM を動かしていると、ついアプリから `llama-server` へ直結したくなります。動く。速い。でも、モデルが増えたり、呼び出しを追いたくなったりした瞬間に、その直結が足かせになります。

このリポジトリ **agent-router-opik-lab** は、その足かせを最初から外しておくための最小ラボです。

## 何が困るのか

直結だと次のようなことが起きがちです。

- アプリが「どのモデルを呼ぶか」まで知ってしまう
- リトライやフォールバックの置き場がない
- リクエストがどこで遅れたのか、Opik のような観測基盤に届かない

本番の AI Gateway をいきなり組むのは重い。だから「ローカル1台」でも、責務だけは本番に近い形に分けておく——それがこのラボの狙いです。

## 経路はこうなる

```text
Application
  → Task Router（いまは Dummy）
  → Agent Router（:1975）
  → llama-server（:2067）
         ↘ OpenTelemetry
            → Opik（:5181）
```

役割は短く言うと次のとおりです。

| 層 | やること |
| --- | --- |
| Application | `LLMGatewayClient` でプロンプトを送るだけ |
| Task Router | `model=Auto` を実モデル名へ解決する（HTTPはしない） |
| Agent Router | OpenAI互換の入口。Provider通信と将来の Retry / Fallback の境界 |
| Opik | Agent Router から届く Trace を見て、latency・model・入出力を確認する |

重要なのは、**アプリが llama-server を直接叩かない**ことです。入口はいつも Agent Router の `:1975/v1` です。

## コードはこんな感じ

```python
from llm_gateway import LLMGatewayClient

async with LLMGatewayClient.from_env() as client:
    text = await client.complete("Hello", model="Auto")
```

`Auto` はいま DummyTaskRouter がローカル Qwen へ固定解決します。将来ここを Classifier や判断専用モデル（Jev）に差し替えても、アプリ側の呼び出しは変えなくてよい——そう設計しています。

既存コード向けに、以前の `LlamaServerEnvConfig.complete()` や `call_llama_server(...)` も残してあり、内部では必ず Agent Router 経由になります。

## なぜ Opik を一緒に置くのか

ゲートウェイを挟んだだけでは、「本当にパラメータが届いたか」「thinking が有効だったか」は見えません。

このラボでは Agent Router が OpenTelemetry（OpenInference）で Opik へ Trace を送ります。`top_k` や `min_p`、`enable_thinking` といったローカル特有のパラメータも、E2E テストで Opik API から検証できるようにしています。

「通ったつもり」ではなく、「Trace で確認できた」までがゴールです。

## 最短で触るなら

前提は起動済みの `llama-server`（`:2067`）と、Python 3.12 + `uv` です。あとはだいたい次の順です。

```bash
make opik-up          # Opik UI: :5181
make agent-router-up  # Gateway: :1975
make smoke-test       # Auto で Hello を送る
```

詳細は [Quick Start](./QUICKSTART.md) をどうぞ。

## いまできること / まだやっていないこと

できること:

- ローカル LLM への OpenAI互換ゲートウェイ
- `Auto` ルーティングの差し替え可能な境界
- Opik への OTLP Trace
- Unit / Integration / Smoke の一連の検証

まだやっていないこと:

- 本物の Classifier / LLM ベース Task Router
- 複数 Provider や Fallback、Cost-aware routing
- Kubernetes や本番向け Rate Limit / Quota

意図的に薄いです。薄いから、責務の線引きと観測の筋道だけ先に固められます。

## おわりに

ローカル LLM の実験は「動けば勝ち」になりやすい。でも一度ゲートウェイと観測を挟んでおくと、次にモデルを増やしたり、ルーティングを賢くしたりするときの書き換えが小さくなります。

agent-router-opik-lab は、その「最初の一歩」を手元で再現するためのサンプルです。興味があれば README と Quick Start から、まずは `make smoke-test` まで到達してみてください。
