.PHONY: check-llama opik-up agent-router-up smoke-test test integration

# 既存のllama-serverが起動していることを確認する。
check-llama:
	./scripts/check-llama-server.sh

# 公式Opikリポジトリの既存インストールを起動・確認する。
opik-up:
	./scripts/start-opik.sh
	for attempt in $$(seq 1 30); do \
		if ./scripts/check-opik.sh; then exit 0; fi; \
		sleep 2; \
	done; \
	exit 1

# Agent RouterをStandaloneモードで起動する。
agent-router-up:
	./scripts/start-agent-router.sh

# 主要経路をまとめて確認する。
smoke-test:
	./scripts/smoke-test.sh

# 外部サービスを必要としないテストを実行する。
test:
	UV_CACHE_DIR="$${UV_CACHE_DIR:-$$(pwd)/.uv-cache}" uv run --link-mode=copy pytest tests/unit

# 起動済みサービスを使う統合テストを明示的に実行する。
integration:
	RUN_LLM_INTEGRATION=true UV_CACHE_DIR="$${UV_CACHE_DIR:-$$(pwd)/.uv-cache}" uv run --link-mode=copy pytest tests/integration
