import random

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class TwoPhaseSampler:
    PLACEMENT_MIN = 20

    def __init__(self, registry, explore_ratio: float = 0.15,
                 neighbor_window: float = 0.3):
        self.registry = registry
        self.explore_ratio = explore_ratio
        self.neighbor_window = neighbor_window

    async def _ratings(self, session: AsyncSession) -> dict:
        rows = await session.execute(text(
            "SELECT model_version_id, beta_hat, n_battles FROM rating_snapshots WHERE is_current"
        ))
        return {r[0]: {"beta": r[1], "n_battles": r[2]} for r in rows}

    async def sample_pair(self, session: AsyncSession, domain: str | None = None) -> tuple[str, str]:
        models = await self.registry.healthy_models(session, domain)
        if len(models) < 2:
            raise RuntimeError("fewer than 2 healthy models; cannot sample a pair")

        ratings = await self._ratings(session)
        new_models = [
            m for m in models
            if ratings.get(m, {}).get("n_battles", 0) < self.PLACEMENT_MIN
        ]
        if new_models:
            return self._placement_pair(new_models[0], models, ratings)
        return self._steady_pair(models, ratings)

    def _steady_pair(self, models, ratings):
        if random.random() < self.explore_ratio:
            return tuple(random.sample(models, 2))
        anchor = random.choice(models)
        anchor_beta = ratings.get(anchor, {}).get("beta", 0.0)
        neighbors = [
            m for m in models
            if m != anchor and abs(ratings.get(m, {}).get("beta", 0.0) - anchor_beta) <= self.neighbor_window
        ]
        if not neighbors:
            return anchor, random.choice([m for m in models if m != anchor])
        return anchor, random.choice(neighbors)

    def _placement_pair(self, new_model, models, ratings):
        ranked = sorted([m for m in models if m != new_model],
                        key=lambda m: -ratings.get(m, {}).get("beta", 0.0))
        if not ranked:
            return new_model, random.choice([m for m in models if m != new_model])
        return new_model, ranked[len(ranked) // 2]
