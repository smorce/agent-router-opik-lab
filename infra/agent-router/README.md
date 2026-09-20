# Agent Routerローカル設定

この構成では、Agent Router v1.1.0のStandalone CLI `aigw run`を使用します。Backendが1つだけなので、独自のKubernetes CRDや複雑な設定ファイルは追加していません。

起動スクリプトは`.env`から次を設定し、llama-serverをOpenAI互換Backendとして登録します。

```text
OPENAI_BASE_URL=http://127.0.0.1:2067/v1
OPENAI_API_KEY=<LLAMA_SERVER_API_KEY>
```

Opik送信は `OPIK_ENABLED` と `OPIK_BASE_URL` から組み立てます。`OPIK_ENABLED=false` なら `OTEL_TRACES_EXPORTER=none` になります。

Applicationの `X-Session-ID` / `X-Request-ID` は、次の Header Mapping で OpenTelemetry span へ写します。

```text
OTEL_AIGW_SPAN_REQUEST_HEADER_ATTRIBUTES=agent-session-id:session.id,x-session-id:session.id,x-request-id:request.id
```

アプリケーションから見える入口は`http://127.0.0.1:1975/v1`です。healthとmetricsは`http://127.0.0.1:1064`です。

```bash
./scripts/start-agent-router.sh
./scripts/check-agent-router.sh
```

`aigw`がPATHにない場合は、READMEの公式v1.1.0リリース手順を使うか、`AIGW_BIN=/path/to/aigw`を指定してください。
