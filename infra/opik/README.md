# Opikローカル接続

Opik本体は公式`comet-ml/opik`リポジトリのLocal installationを使用します。このリポジトリはOpikのDocker Compose定義を複製せず、起動スクリプトと`http://127.0.0.1:5181`への接続確認だけを担当します。

```bash
git clone https://github.com/comet-ml/opik.git "$HOME/opik"
NGINX_PORT=5181 "$HOME/opik/opik.sh"
```

`:5173`は既存のWebLLMアプリが使用するため、公開UIポートを`:5181`へ変更しています。

Agent RouterからのTraceはOpenTelemetry HTTP/protobufで次へ送ります。

```text
http://127.0.0.1:5181/api/v1/private/otel/v1/traces
```

設定例:

```dotenv
OPIK_ENABLED=true
OPIK_BASE_URL=http://127.0.0.1:5181
OPIK_PROJECT_NAME=agent-router-local
```

`./scripts/start-agent-router.sh` は `OPIK_BASE_URL` から次を生成します。

```text
http://127.0.0.1:5181/api/v1/private/otel/v1/traces
```

`OPIK_ENABLED=false` にすると Agent Router の `OTEL_TRACES_EXPORTER` は `none` になります。

```bash
./scripts/check-opik.sh
```

入力・出力をOpikへ保存する場合は、個人情報・機密情報の取り扱いを確認してください。必要なら`OPENINFERENCE_HIDE_INPUTS`と`OPENINFERENCE_HIDE_OUTPUTS`を`true`にします。
