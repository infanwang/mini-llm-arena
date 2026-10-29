import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from src.model_hub.hub import ModelHub
from src.orchestrator.anonymize import Anonymizer
from src.orchestrator.sampler import TwoPhaseSampler
from src.rating.style_features import extract_style
from src.security.identity_probe import classify_probe


class BattleOrchestrator:
    def __init__(self, sampler: TwoPhaseSampler, hub: ModelHub, anonymizer: Anonymizer):
        self.sampler = sampler
        self.hub = hub
        self.anon = anonymizer

    async def create_battle(self, session: AsyncSession, prompt: str,
                            session_id: str, domain: str | None = None) -> dict:
        # 1. 身份探测前置过滤
        probe_class = classify_probe(prompt)
        if probe_class == "probe_hard":
            await session.execute(
                text("INSERT INTO probe_audit (id, normalized_hash, classification) "
                     "VALUES (:id, :h, :c)"),
                {"id": uuid.uuid4(),
                 "h": hashlib.sha256(prompt.encode()).hexdigest()[:32],
                 "c": probe_class},
            )
            await session.commit()
            return {"rejected": True, "reason": "identity_probe_detected"}

        # 2. 两阶段采样
        a, b = await self.sampler.sample_pair(session, domain)

        # 3. 匿名化
        ha, hb = self.anon.hash_model(a), self.anon.hash_model(b)
        position_order = secrets.choice(["a_first", "b_first"])

        # 4. 并发推理
        ra, rb = await self.hub.parallel_infer(session, a, b, prompt)

        # 5. 无效对战判定
        is_invalid = any(r.error is not None for r in (ra, rb))

        # 6. 落库：style_* 用 JSONB bindparam，让 SQLAlchemy 负责 dict → JSON 序列化
        battle_id = uuid.uuid4()
        style_a = extract_style(ra.text) if not ra.error else None
        style_b = extract_style(rb.text) if not rb.error else None

        stmt = text(
            "INSERT INTO battles (battle_id, prompt, prompt_hash, model_a_hash, model_b_hash, "
            "position_order, domain, session_id, style_a, style_b, is_invalid, created_at) "
            "VALUES (:bid, :p, :ph, :ha, :hb, :po, :d, :sid, :sa, :sb, :inv, :ts)"
        ).bindparams(
            bindparam("sa", type_=JSONB),
            bindparam("sb", type_=JSONB),
        )
        await session.execute(stmt, {
            "bid": battle_id, "p": prompt,
            "ph": hashlib.sha256(prompt.encode()).hexdigest(),
            "ha": ha, "hb": hb, "po": position_order, "d": domain,
            "sid": session_id,
            "sa": style_a, "sb": style_b,
            "inv": is_invalid, "ts": datetime.now(timezone.utc),
        })
        await session.commit()

        return {
            "battle_id": str(battle_id),
            "anonymized_pair": [{"seat": "A"}, {"seat": "B"}],
            "responses": {"A": ra.text, "B": rb.text},
            "invalid": is_invalid,
        }

    async def cast_vote(self, session: AsyncSession, battle_id: str, winner: str,
                        vote_duration_ms: int | None = None) -> dict:
        row = (await session.execute(
            text("SELECT is_invalid, model_a_hash, model_b_hash FROM battles WHERE battle_id = :bid"),
            {"bid": battle_id},
        )).first()
        if not row:
            return {"accepted": False, "reason": "battle_not_found"}
        is_invalid, ha, hb = row
        if is_invalid:
            return {"accepted": False, "reason": "battle_invalid"}

        quality_flag = "clean"
        if vote_duration_ms is not None and vote_duration_ms < 500:
            quality_flag = "suspicious"

        await session.execute(
            text(
                "INSERT INTO votes (vote_id, battle_id, winner, vote_duration_ms, quality_flag) "
                "VALUES (:vid, :bid, :w, :dur, :q)"
            ),
            {"vid": uuid.uuid4(), "bid": battle_id, "w": winner,
             "dur": vote_duration_ms, "q": quality_flag},
        )

        ma = self.anon.resolve(ha)
        mb = self.anon.resolve(hb)
        if ma and mb:
            await session.execute(
                text(
                    "UPDATE battles SET model_a_version_id = :ma, model_b_version_id = :mb, "
                    "de_anonymized_at = :ts WHERE battle_id = :bid"
                ),
                {"ma": ma, "mb": mb, "ts": datetime.now(timezone.utc), "bid": battle_id},
            )

        await session.commit()
        return {"accepted": True, "quality_flag": quality_flag}
