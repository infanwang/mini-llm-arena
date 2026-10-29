import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.logging_config import configure
from src.model_hub.hub import ModelHub
from src.model_hub.registry import ModelRegistry
from src.orchestrator.anonymize import Anonymizer
from src.orchestrator.battle import BattleOrchestrator
from src.orchestrator.sampler import TwoPhaseSampler
from src.rating.tied_groups import assign_tied_groups

configure()

engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

BATTLES_TOTAL = Counter("arena_battles_total", "Battles", ["status"])
VOTES_TOTAL = Counter("arena_votes_total", "Votes", ["quality_flag"])
HEARTBEAT_STALE = Gauge("arena_heartbeat_stale_models", "Stale models")

# 低于此样本量时，Bootstrap CI 退化为宽度 0，展示会误导 → 返回 null
MIN_RELIABLE_BATTLES = int(os.environ.get("MIN_RELIABLE_BATTLES", "30"))

registry = ModelRegistry()
hub = ModelHub()
anonymizer = Anonymizer()
sampler = TwoPhaseSampler(registry, explore_ratio=0.15,
                          neighbor_window=float(os.environ.get("NEIGHBOR_WINDOW", "0.3")))
orchestrator = BattleOrchestrator(sampler=sampler, hub=hub, anonymizer=anonymizer)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Arena Platform", lifespan=lifespan)


async def get_session():
    async with SessionLocal() as s:
        yield s


class BattleRequest(BaseModel):
    prompt: str
    session_id: str
    domain: str | None = None


class VoteRequest(BaseModel):
    winner: str
    vote_duration_ms: int | None = None


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/battles")
async def create_battle(req: BattleRequest, session: AsyncSession = Depends(get_session)):
    try:
        result = await orchestrator.create_battle(session, req.prompt, req.session_id, req.domain)
    except RuntimeError as e:
        BATTLES_TOTAL.labels(status="error").inc()
        raise HTTPException(status_code=503, detail=str(e))
    status = "invalid" if result.get("invalid") else ("rejected" if result.get("rejected") else "ok")
    BATTLES_TOTAL.labels(status=status).inc()
    if result.get("rejected"):
        raise HTTPException(status_code=400, detail=result)
    return result


@app.post("/api/v1/battles/{battle_id}/vote")
async def vote(battle_id: str, req: VoteRequest, session: AsyncSession = Depends(get_session)):
    if req.winner not in ("A", "B", "tie", "both_bad"):
        raise HTTPException(status_code=400, detail="invalid winner")
    result = await orchestrator.cast_vote(session, battle_id, req.winner, req.vote_duration_ms)
    if not result.get("accepted"):
        raise HTTPException(status_code=400, detail=result)
    VOTES_TOTAL.labels(quality_flag=result["quality_flag"]).inc()
    return result


@app.get("/api/v1/leaderboard")
async def leaderboard(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(text(
        "SELECT model_version_id, rating_display, ci_lower, ci_upper, "
        "rank_point, rank_ci_lower, rank_ci_upper, n_battles, provisional "
        "FROM rating_snapshots WHERE is_current ORDER BY rating_display DESC"
    ))).all()

    if not rows:
        return []

    model_ids = [r[0] for r in rows]
    ratings = [r[1] for r in rows]           # rating_display = 1000 + 200*beta，与 beta 单调等价
    rank_ci_lower = [r[5] for r in rows]
    rank_ci_upper = [r[6] for r in rows]

    groups = assign_tied_groups(model_ids, ratings, rank_ci_lower, rank_ci_upper)
    model_to_group = {m: g["group_rank"] for g in groups for m in g["models"]}

    result = []
    for r in rows:
        n = r[7]
        reliable = n >= MIN_RELIABLE_BATTLES
        result.append({
            "model": r[0],
            "rating": r[1],
            "ci_lower": r[2] if reliable else None,
            "ci_upper": r[3] if reliable else None,
            "ci_reliable": reliable,
            "rank_point": r[4],
            "rank_ci": [r[5], r[6]],
            "tied_group": model_to_group.get(r[0]),
            "n_battles": n,
            "provisional": r[8],
        })
    return result


# 前端静态文件（放在最后，避免与 /api 路由冲突）
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/ui", StaticFiles(directory=_static_dir, html=True), name="ui")
