arena-platform/
├── Dockerfile
├── compose.yaml
├── compose.prod.yaml
├── Makefile
├── .env.example
├── pyproject.toml
├── uv.lock
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial.py
├── src/
│   ├── models.py               # SQLAlchemy ORM 模型
│   ├── api.py
│   ├── tasks.py
│   ├── celery_app.py
│   ├── logging_config.py
│   ├── model_hub/
│   ├── orchestrator/
│   ├── rating/
│   ├── security/
│   └── monitoring/
├── jobs/
│   ├── run_rating.py
│   └── run_consistency.py
├── prometheus/
│   └── prometheus.yml
└── secrets/
    └── db_password.txt         # 需手动创建
