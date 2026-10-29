.PHONY: up down reset rating monitor smoke secrets-check heads

up: secrets-check
	docker compose -f compose.yaml -f compose.prod.yaml up -d --build
	@echo "等待 API 就绪..."
	@until curl -sf http://localhost:8000/healthz; do sleep 2; done
	@$(MAKE) smoke
	@echo "✓ 栈已就绪: http://localhost:8000"

secrets-check:
	@test -f secrets/db_password.txt || (echo "✗ 缺少 secrets/db_password.txt" && exit 1)
	@test -f .env || (echo "✗ 缺少 .env，请从 .env.example 复制" && exit 1)
	@test -f uv.lock || (echo "✗ 缺少 uv.lock，请运行 uv lock" && exit 1)
	@docker compose -f compose.yaml -f compose.prod.yaml config -q || (echo "✗ compose 校验失败" && exit 1)
	@echo "✓ 配置检查通过"

heads:
	@docker compose run --rm migrate alembic heads

rating:
	docker compose --profile batch run --rm rating-job

monitor:
	docker compose --profile monitoring up -d prometheus

smoke:
	@curl -sf http://localhost:8000/healthz > /dev/null && echo "healthz OK"
	@curl -sf http://localhost:8000/readyz > /dev/null && echo "readyz OK"

reset:
	docker compose down --volumes
	$(MAKE) up

down:
	docker compose down
