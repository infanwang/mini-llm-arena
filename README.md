# LLM Arena Platform

基于 **Bradley-Terry 模型** 与 **成对 Bootstrap** 统计推断的 LLM 竞技机评估平台。旨在通过真实用户盲测与抗污染机制，提供比静态基准（如 MMLU）更贴近真实体验的模型能力排行。

## ✨ 核心特性

- **统计严谨性**：基于 Bradley-Terry MLE 拟合，结合 1000 次成对 Bootstrap 计算 95% 置信区间，避免统计噪声导致的排名误判。
- **偏差校正**：在评分模型中引入协变量（回答长度、Markdown 密度、呈现位置），剥离风格偏好对模型“真实能力”的干扰。
- **两阶段智能采样**：
  - *Placement Matches*：新模型接入时通过二分搜索快速定位初始区间。
  - *Proximity Sampling*：稳态期优先匹配评分相近的模型，最大化信息增益。
- **防作弊前置过滤**：对抗身份探测 Prompt（NFKC 归一化、Base64 解码、零宽字符剥离），并在评分层对协同投票进行降权。
- **极简前端**：内置原生 HTML/JS 竞技与排行榜 UI，无需复杂构建步骤。
- **一键部署**：基于 Docker Compose 与 Makefile，支持平滑回滚的基线化工具。

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone git@github.com:infanwang/mini-llm-arena.git
cd mini-llm-arena

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 替换所有 change-me-* 占位符（尤其是 ANONYMIZATION_SALT）

# 3. 创建数据库密码 secret
mkdir -p secrets
openssl rand -hex 32 > secrets/db_password.txt
chmod 600 secrets/db_password.txt
# 确保 db_password.txt 中的内容与 .env 的 POSTGRES_PASSWORD 完全一致

# 4. 一键启动
make up

# 5. 运行初始评分（合成数据）
make rating
启动后，访问：

Web UI: http://localhost:8000/ui/

API 文档: http://localhost:8000/docs

📚 文档索引
部署与接入指南 —— 如何接入真实的大模型（OpenAI/vLLM/Anthropic）。

架构与技术设计 —— 统计模型、两阶段采样与防作弊机制的实现细节。

🛠️ 技术栈
后端: Python 3.12, FastAPI, SQLAlchemy (async), Celery

数据与缓存: PostgreSQL (JSONB), Redis

统计引擎: scikit-learn (Logistic Regression), NumPy, SciPy

部署: Docker, Docker Compose, Prometheus

📄 License
MIT License
