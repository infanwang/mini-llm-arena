from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

HEARTBEAT_TTL = timedelta(seconds=90)


class ModelRegistry:
    async def touch(self, session: AsyncSession, model_version_id: str) -> None:
        await session.execute(
            text("UPDATE model_versions SET last_heartbeat_at = :ts WHERE model_version_id = :mid"),
            {"ts": datetime.now(timezone.utc), "mid": model_version_id},
        )

    async def healthy_models(self, session: AsyncSession, domain: str | None = None) -> list[str]:
        cutoff = datetime.now(timezone.utc) - HEARTBEAT_TTL
        rows = await session.execute(
            text(
                "SELECT model_version_id FROM model_versions "
                "WHERE status = 'active' AND last_heartbeat_at > :cutoff"
            ),
            {"cutoff": cutoff},
        )
        return [r[0] for r in rows]
