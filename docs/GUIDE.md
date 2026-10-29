# 部署与接入指南

## 环境要求

- Docker Engine 23+ 与 Docker Compose v2
- 建议在 Linux 或 WSL2 Ubuntu 上运行（Windows 文件系统挂载性能较差）
- 内存建议 12GB+（若本地运行 vLLM 则需更高）

## 部署与启动

1. **配置密钥**：必须保证 `.env` 中的 `POSTGRES_PASSWORD` 与 `secrets/db_password.txt` 的内容完全一致。
2. **启动服务**：`make up` 会依次执行数据库迁移、启动 API、Celery 与 Beat。
3. **验证状态**：`make smoke` 确认 API 的 `/healthz` 与 `/readyz` 正常。

## 接入真实模型

平台通过 OpenAI 兼容接口与模型通信。你可以在数据库中直接注册模型：

```sql
INSERT INTO model_versions (model_version_id, display_name, provider, capabilities, last_heartbeat_at)
VALUES
  ('gpt-4o', 'GPT-4o', 'openai', '{"base_url":"https://api.openai.com","api_key":"sk-..."}', now()),
  ('qwen-72b', 'Qwen 72B', 'local', '{"base_url":"http://vllm:8000"}', now());
base_url：OpenAI 兼容端点（无需包含 /v1，代码会自动补齐）。

api_key：模型提供方的凭证（本地模型可随意填）。

心跳机制：模型版本只有在 last_heartbeat_at 的 90 秒内才会被采样。针对生产环境，你需要编写一个定时任务，每隔 60 秒执行一次 UPDATE model_versions SET last_heartbeat_at = now()。

基线化与回滚
平台内置了基线快照工具，用于代码变更或模型接入前的状态保护：

bash
# 创建基线（包含数据库 dump、镜像 tag、代码哈希）
./scripts/baseline.sh

# 回滚到指定基线（自动重建容器并导入数据）
BASE_DIR=$(ls -d ~/arena-platform-baselines/*/ | tail -1)
bash "${BASE_DIR}/restore.sh"
常见故障排查
password authentication failed：修改 .env 和 secrets 后，必须执行 docker compose down -v 清空卷再启动。

fewer than 2 healthy models：数据库中没有活跃模型，或心跳已超时。请在数据库执行 UPDATE 刷新。

Windows 浏览器无法访问：WSL2 端口转发问题。请尝试在 Windows 终端执行 netsh interface portproxy add ... 将 WSL IP 映射到 localhost，或在 .wslconfig 中开启 networkingMode=mirrored。
