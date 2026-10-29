import numpy as np
from scipy.stats import spearmanr


class ConsistencyMonitor:
    def __init__(self, auto_eval_fn, threshold: float = 0.75):
        self.auto_eval = auto_eval_fn
        self.threshold = threshold
        self.history: list[float] = []

    def weekly_check(self, human_bt_ranking: dict[str, float]) -> dict:
        auto_scores = self.auto_eval()
        common = sorted(set(auto_scores) & set(human_bt_ranking))
        if len(common) < 8:
            return {"status": "insufficient_models"}

        rho, p = spearmanr([auto_scores[m] for m in common],
                           [human_bt_ranking[m] for m in common])
        self.history.append(float(rho))
        baseline = float(np.median(self.history[-5:-1])) if len(self.history) > 4 else None
        alert = (rho < self.threshold) or (baseline is not None and rho < baseline - 0.10)
        return {
            "spearman_rho": float(rho),
            "p_value": float(p),
            "alert": bool(alert),
            "action": "trigger_vote_audit" if alert else "none",
        }
