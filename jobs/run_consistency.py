import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.monitoring.consistency import ConsistencyMonitor


def run_consistency_check() -> dict:
    if os.environ.get("AUTO_EVAL_ENABLED", "false").lower() != "true":
        return {"status": "skipped", "reason": "AUTO_EVAL_ENABLED=false"}

    async def _run():
        engine = create_async_engine(os.environ["DATABASE_URL"])
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as session:
            rows = await session.execute(text(
                "SELECT model_version_id, beta_hat FROM rating_snapshots WHERE is_current"
            ))
            human = {r[0]: float(r[1]) for r in rows}
        await engine.dispose()
        return human

    human = asyncio.run(_run())

    def auto_eval():
        # 占位：真实部署时替换为 Arena-Hard-Auto 的固定 prompt 子集评估
        import numpy as np
        rng = np.random.default_rng(0)
        return {m: float(v + rng.normal(0, 0.05)) for m, v in human.items()}

    monitor = ConsistencyMonitor(auto_eval, threshold=0.75)
    return monitor.weekly_check(human)


if __name__ == "__main__":
    print(run_consistency_check())
