#!/usr/bin/env bash
set -euo pipefail

PROJ_DIR="${HOME}/arena-platform"
BASE_ROOT="${HOME}/arena-platform-baselines"
TS="$(date +%Y%m%d-%H%M%S)"
BASE_DIR="${BASE_ROOT}/${TS}"
IMG_TAG="baseline-${TS}"

cd "${PROJ_DIR}"

echo "==> 基线目录: ${BASE_DIR}"
mkdir -p "${BASE_DIR}/runtime"

# ---------- 1. 代码层：文件哈希清单 ----------
echo "==> [1/6] 记录源文件哈希"
find . -type f \
  -not -path './.git/*' \
  -not -path './.venv/*' \
  -not -path './__pycache__/*' \
  -not -path './src/**/__pycache__/*' \
  -not -path './alembic/versions/__pycache__/*' \
  -not -name '*.pyc' \
  -not -name '.env' \
  -not -path './secrets/*' \
  -print0 | sort -z | xargs -0 sha256sum > "${BASE_DIR}/file-hashes.txt"

# ---------- 2. 配置层 ----------
echo "==> [2/6] 快照配置"
docker compose -f compose.yaml -f compose.prod.yaml config \
  > "${BASE_DIR}/compose-config.txt" 2>&1 || true

sed -E \
  -e 's/^(POSTGRES_PASSWORD=).*/\1<REDACTED>/' \
  -e 's/^(REDIS_PASSWORD=).*/\1<REDACTED>/' \
  -e 's#^(REDIS_URL=redis://:)[^@]*(@.*)#\1<REDACTED>\2#' \
  -e 's#^(DATABASE_URL=postgresql\+asyncpg://[^:]+:)[^@]*(@.*)#\1<REDACTED>\2#' \
  .env > "${BASE_DIR}/env.redacted"

SALT_FP="$(grep '^ANONYMIZATION_SALT=' .env | cut -d= -f2- | sha256sum | cut -c1-16)"
echo "ANONYMIZATION_SALT_FINGERPRINT=${SALT_FP}" >> "${BASE_DIR}/env.redacted"

# ---------- 3. 镜像层 ----------
echo "==> [3/6] 固定镜像 tag 为 ${IMG_TAG}"
: > "${BASE_DIR}/images.txt"
for svc in api migrate worker beat rating-job; do
  img="arena-platform-${svc}"
  if docker image inspect "${img}:latest" >/dev/null 2>&1; then
    docker tag "${img}:latest" "${img}:${IMG_TAG}"
    iid="$(docker image inspect "${img}:latest" --format '{{.Id}}')"
    echo "${img}:${IMG_TAG}  ${iid}" | tee -a "${BASE_DIR}/images.txt"
  else
    echo "${img}:latest  <MISSING>" | tee -a "${BASE_DIR}/images.txt"
  fi
done

# ---------- 4. 数据层 ----------
echo "==> [4/6] 导出数据库"
docker compose exec -T postgres \
  pg_dump -U arena -d arena --no-owner --no-privileges \
  > "${BASE_DIR}/db.dump"

for tbl in model_versions battles votes rating_snapshots; do
  grep -q "CREATE TABLE public.${tbl}" "${BASE_DIR}/db.dump" \
    || { echo "ERROR: db.dump 缺少表 ${tbl}"; exit 1; }
done

# ---------- 5. 运行状态层 ----------
echo "==> [5/6] 采集运行状态"
docker compose ps > "${BASE_DIR}/runtime/compose-ps.txt"

curl -sf http://localhost:8000/healthz > "${BASE_DIR}/runtime/healthz.txt"
curl -sf http://localhost:8000/readyz >> "${BASE_DIR}/runtime/healthz.txt"

curl -sf http://localhost:8000/api/v1/leaderboard \
  | python3 -m json.tool > "${BASE_DIR}/runtime/leaderboard.json"

docker compose --profile batch run --rm rating-job \
  > "${BASE_DIR}/runtime/rating-run.log" 2>&1 || true

# ---------- 6. MANIFEST ----------
echo "==> [6/6] 写 MANIFEST"
{
  echo "baseline_timestamp=${TS}"
  echo "image_tag=${IMG_TAG}"
  echo "project_dir=${PROJ_DIR}"
  echo "git_commit=$(git -C "${PROJ_DIR}" rev-parse HEAD 2>/dev/null || echo 'no-git')"
  echo "docker_version=$(docker version --format '{{.Server.Version}}')"
  echo "compose_version=$(docker compose version --short)"
  echo "host=$(uname -a)"
  echo "leaderboard_rows=$(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))))' \
        "${BASE_DIR}/runtime/leaderboard.json" 2>/dev/null || echo '0')"
} > "${BASE_DIR}/MANIFEST.txt"

# ---------- 7. 生成回滚脚本（修复版模板） ----------
cat > "${BASE_DIR}/restore.sh" <<RESTORE
#!/usr/bin/env bash
set -euo pipefail
cd "${PROJ_DIR}"

BASE_DIR="${BASE_DIR}"
IMG_TAG="${IMG_TAG}"
COMPOSE="docker compose -f compose.yaml -f compose.prod.yaml"

echo "[restore] 停栈并清卷"
for c in \$(docker ps -q --filter "network=arena-platform_default"); do
    svc=\$(docker inspect -f '{{.Config.Labels.com.docker.compose.service}}' \$c 2>/dev/null || echo "")
    if [ -z "\${svc}" ]; then
        docker network disconnect -f arena-platform_default \$c 2>/dev/null || true
    fi
done
\${COMPOSE} down -v

echo "[restore] 回切镜像 tag"
for svc in api migrate worker beat rating-job; do
    docker tag "arena-platform-\${svc}:\${IMG_TAG}" "arena-platform-\${svc}:latest"
done

echo "[restore] 只启动 postgres 与 redis"
\${COMPOSE} up -d postgres redis

echo "[restore] 等待 postgres healthy"
for _ in \$(seq 1 60); do
    if \${COMPOSE} ps postgres | grep -q "healthy"; then break; fi
    sleep 2
done
\${COMPOSE} ps postgres | grep -q "healthy" || { echo "[restore] ✗ postgres 未就绪"; exit 1; }
echo "[restore] ✓ postgres 已就绪"

echo "[restore] 导入完整 dump（含 schema）"
cat "\${BASE_DIR}/db.dump" \\
  | \${COMPOSE} exec -T postgres psql -U arena -d arena -v ON_ERROR_STOP=1 -q
echo "[restore] ✓ dump 导入完成"

echo "[restore] 启动 migrate（应 no-op 退出 0）"
\${COMPOSE} up -d migrate
migrate_ok=0
for _ in \$(seq 1 60); do
    cid=\$(\${COMPOSE} ps -a -q migrate 2>/dev/null | head -1 || true)
    if [ -n "\${cid}" ]; then
        status=\$(docker inspect -f '{{.State.Status}}' "\${cid}" 2>/dev/null || echo "unknown")
        code=\$(docker inspect -f '{{.State.ExitCode}}' "\${cid}" 2>/dev/null || echo "-1")
        if [ "\${status}" = "exited" ] && [ "\${code}" = "0" ]; then
            migrate_ok=1; break
        elif [ "\${status}" = "exited" ] && [ "\${code}" != "0" ]; then
            echo "[restore] ✗ migrate 退出码 \${code}"; exit 1
        fi
    fi
    sleep 1
done
[ "\${migrate_ok}" = "1" ] || { echo "[restore] ✗ migrate 等待超时"; exit 1; }
echo "[restore] ✓ migrate 已成功退出"

echo "[restore] 启动其余服务"
\${COMPOSE} up -d

echo "[restore] 等待 api healthy"
for _ in \$(seq 1 60); do
    curl -sf http://localhost:8000/healthz >/dev/null 2>&1 && break
    sleep 2
done
curl -sf http://localhost:8000/healthz >/dev/null || { echo "[restore] ✗ api 未就绪"; exit 1; }
echo "[restore] ✓ api 已就绪"

echo "[restore] 校验排行榜语义"
curl -s http://localhost:8000/api/v1/leaderboard \\
  | python3 -c '
import json, sys
rows = json.load(sys.stdin)
baseline = json.load(open("'"\${BASE_DIR}"'/runtime/leaderboard.json"))
key = lambda r: (r["model"], round(r["rating"], 2), r["rank_ci"][0], r["rank_ci"][1], r["provisional"], r["n_battles"])
if sorted(map(key, rows)) == sorted(map(key, baseline)):
    print("[restore] ✓ 排行榜语义与基线一致")
    sys.exit(0)
else:
    print("[restore] ✗ 排行榜与基线不一致")
    sys.exit(1)
'

echo "[restore] ✓ 完成"
RESTORE
chmod +x "${BASE_DIR}/restore.sh"

echo
echo "✓ 基线化完成: ${BASE_DIR}"
echo "  镜像 tag: ${IMG_TAG}"
echo "  下一步：在无干扰时执行一次回滚演练以验证基线有效性"
