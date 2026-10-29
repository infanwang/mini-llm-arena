# --- 构建阶段 ---
FROM python:3.12-slim AS builder
WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- 运行阶段 ---
FROM python:3.12-slim AS runtime
RUN groupadd -r arena && useradd -r -g arena -d /app -s /sbin/nologin arena
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY jobs/ ./jobs/
USER arena
