# Quick Start

最短で次の経路を通します。

```text
Application → DummyTaskRouter → Agent Router(:1975) → llama-server(:2067)
Agent Router → OpenTelemetry → Opik(:5181)
```

Linux / WSL2 向けです。Windowsネイティブでは `aigw` は動作保証しません。

## 前提

- llama-server が `http://127.0.0.1:2067/v1` で起動済み
- Python 3.12以上、`uv`、`docker`、`git`、`gh`（または手動で `aigw` 取得）
- `:5173` は使わない（既存WebLLMと衝突するため Opik は `:5181`）

## 1. 依存関係

```bash
cd /path/to/agent-router-opik-lab
cp .env.example .env
UV_CACHE_DIR="$PWD/.uv-cache" uv venv --python 3.12
UV_CACHE_DIR="$PWD/.uv-cache" uv sync --link-mode=copy
```

## 2. Agent Router CLI (`aigw`)

```bash
gh release download v1.1.0 \
  --repo envoyproxy/ai-gateway \
  --pattern 'aigw-linux-amd64' \
  --output "$HOME/.local/bin/aigw"
chmod +x "$HOME/.local/bin/aigw"
aigw version
```

## 3. Opik（初回のみ clone）

```bash
git clone https://github.com/comet-ml/opik.git "$HOME/opik"
make opik-up
```

UI: http://127.0.0.1:5181

## 4. llama-server 確認

```bash
make check-llama
```

## 5. Agent Router 起動

別ターミナルで:

```bash
make agent-router-up
```

入口: `http://127.0.0.1:1975/v1`  
Admin: `http://127.0.0.1:1064/health`

## 6. Smoke Test

```bash
make smoke-test
```

成功時、Application から `model=Auto` で応答が返り、Opik の `agent-router-local` に Trace が入ります。

## 7. Python から呼ぶ

```bash
UV_CACHE_DIR="$PWD/.uv-cache" uv run --link-mode=copy \
  python -m llm_gateway.cli "1+1は？" --model Auto
```

または:

```python
from llm_gateway import LLMGatewayClient

async with LLMGatewayClient.from_env() as client:
    print(await client.complete("Hello", model="Auto"))
```

## 8. テスト

```bash
make test
make integration
```

## ポート早見表

| サービス | URL |
| --- | --- |
| llama-server | http://127.0.0.1:2067/v1 |
| Agent Router | http://127.0.0.1:1975/v1 |
| Agent Router Admin | http://127.0.0.1:1064/health |
| Opik UI / OTLP | http://127.0.0.1:5181 |

## 詰まったとき

- `aigw was not found` → PATH に `aigw` を置くか `AIGW_BIN` を指定
- Opik OTLP が届かない → `make opik-up` 後に `./scripts/check-opik.sh`
- Responses API 404 → 初期経路は Chat Completions。既知制限は [実装レポート](./agent-router-opik-implementation-report.md)

詳細は [README](../README.md) を参照してください。
