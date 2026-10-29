"""
评分快照批处理：从 votes 表读取对战数据，拟合 BT + Bootstrap，写入 rating_snapshots。
votes 为空时使用合成数据跑通管道，便于部署验证（make rating）。
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.rating.bt_engine import BTEngine
from src.rating.tied_groups import assign_tied_groups

PROVISIONAL_THRESHOLD = int(os.environ.get("PROVISIONAL_THRESHOLD_TEXT", "5000"))


def synth_battles(n_models: int = 6, n_battles: int = 600, seed: int = 7) -> list[dict]:
    rng = np.random.default_rng(seed)
    true_betas = rng.normal(0, 1, n_models)
    battles = []
    for _ in range(n_battles):
        i, j = rng.choice(n_models, 2, replace=False)
        p = 1 / (1 + np.exp(-(true_betas[i] - true_betas[j])))
        winner = "A" if rng.random() < p else "B"
        battles.append({
            "model_a": f"mock-{i}", "model_b": f"mock-{j}", "winner": winner,
            "quality_weight": 1.0,
            "style_a": {"token_length": 100, "markdown_density": 0.01},
            "style_b": {"token_length": 100, "markdown_density": 0.01},
            "position_order": "a_first" if rng.random() < 0.5 else "b_first",
        })
    return battles


async def load_battles_from_db(session) -> list[dict]:
    rows = await session.execute(text(
        "SELECT b.model_a_version_id, b.model_b_version_id, v.winner, v.quality_flag, "
        "b.style_a, b.style_b, b.position_order "
        "FROM battles b JOIN votes v ON v.battle_id = b.battle_id "
        "WHERE b.is_invalid = FALSE AND b.de_anonymized_at IS NOT NULL"
    ))
    out = []
    for r in rows:
        if not r[0] or not r[1]:
            continue
        w = 0.0 if r[3] == "bot_flagged" else (0.3 if r[3] == "suspicious" else 1.0)
        out.append({
            "model_a": r[0], "model_b": r[1], "winner": r[2],
            "quality_weight": w,
            "style_a": r[4] or {"token_length": 0, "markdown_density": 0.0},
            "style_b": r[5] or {"token_length": 0, "markdown_density": 0.0},
            "position_order": r[6],
        })
    return out


async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        battles = await load_battles_from_db(session)
        source = "db"
        if not battles:
            battles = synth_battles()
            source = "synthetic"
            print(f"[run_rating] votes table empty; using {len(battles)} synthetic battles")

        models = sorted({b["model_a"] for b in battles} | {b["model_b"] for b in battles})
        model_index = {m: i for i, m in enumerate(models)}

        # 先注册模型，满足 rating_snapshots 的外键约束
        for m in models:
            await session.execute(text(
                "INSERT INTO model_versions (model_version_id, display_name, provider, capabilities) "
                "VALUES (:m, :m, 'synthetic', '{}') ON CONFLICT (model_version_id) DO NOTHING"
            ), {"m": m})
        await session.flush()

        engine_bt = BTEngine(
            n_bootstrap=int(os.environ.get("BOOTSTRAP_ROUNDS", "1000")),
            style_keys=("token_length", "markdown_density"),
        )
        result = engine_bt.fit(battles, model_index)

        n_battles = {m: 0 for m in models}
        for b in battles:
            n_battles[b["model_a"]] += 1
            n_battles[b["model_b"]] += 1

        groups = assign_tied_groups(
            models, result["beta_hat"], result["rank_ci_lower"], result["rank_ci_upper"],
        )
        rank_point = {}
        for g in groups:
            for m in g["models"]:
                rank_point[m] = g["group_rank"]

        await session.execute(text("UPDATE rating_snapshots SET is_current = FALSE WHERE is_current"))

        now = datetime.now(timezone.utc)
        for i, m in enumerate(models):
            provisional = n_battles[m] < PROVISIONAL_THRESHOLD
            beta_val = float(result["beta_hat"][i])
            rating_display = 1000 + 200 * beta_val
            # CI 与 rating_display 同一量纲
            ci_lo = 1000 + 200 * float(result["ci_lower"][i])
            ci_hi = 1000 + 200 * float(result["ci_upper"][i])
            # 排名区间转为 1-based
            rcl = int(result["rank_ci_lower"][i]) + 1
            rcu = int(result["rank_ci_upper"][i]) + 1
            await session.execute(text(
                "INSERT INTO rating_snapshots "
                "(snapshot_id, model_version_id, beta_hat, rating_display, ci_lower, ci_upper, "
                " rank_point, rank_ci_lower, rank_ci_upper, n_battles, provisional, "
                " gamma_len, gamma_md, gamma_pos, fitted_at, is_current) "
                "VALUES (gen_random_uuid(), :m, :b, :rd, :cl, :cu, :rp, :rcl, :rcu, :nb, :pv, "
                "        :gl, :gm, :gp, :ts, TRUE)"
            ), {
                "m": m,
                "b": beta_val,
                "rd": rating_display,
                "cl": ci_lo,
                "cu": ci_hi,
                "rp": None if provisional else rank_point[m],
                "rcl": rcl,
                "rcu": rcu,
                "nb": n_battles[m],
                "pv": provisional,
                "gl": float(result["gamma"][0]) if len(result["gamma"]) > 0 else None,
                "gm": float(result["gamma"][1]) if len(result["gamma"]) > 1 else None,
                "gp": float(result["gamma"][2]) if len(result["gamma"]) > 2 else None,
                "ts": now,
            })

        await session.commit()
        print(f"[run_rating] source={source} models={len(models)} battles={len(battles)}")
        print(f"[run_rating] wrote {len(models)} rating_snapshots")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
