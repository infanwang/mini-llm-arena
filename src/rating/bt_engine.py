import numpy as np
from sklearn.linear_model import LogisticRegression


class BTEngine:
    def __init__(self, C: float = 1.0, n_bootstrap: int = 1000, seed: int = 42,
                 style_keys: tuple[str, ...] = ("token_length", "markdown_density"),
                 correct_position: bool = True):
        self.C = C
        self.B = n_bootstrap
        self.rng = np.random.default_rng(seed)
        self.style_keys = style_keys
        self.correct_position = correct_position

    def _build_design(self, battles, model_index):
        n_models = len(model_index)
        rows, labels, weights = [], [], []
        for bt in battles:
            ya = 1.0 if bt["winner"] == "A" else 0.0
            w = bt["quality_weight"]
            ra = np.zeros(n_models); ra[model_index[bt["model_a"]]] = 1.0
            rb = np.zeros(n_models); rb[model_index[bt["model_b"]]] = 1.0

            extra_a = [bt["style_a"][k] - bt["style_b"][k] for k in self.style_keys]
            if self.correct_position:
                extra_a.append(1.0 if bt["position_order"] == "a_first" else 0.0)

            xa = np.concatenate([ra - rb, extra_a])
            xb = -xa
            rows.extend([xa, xb])
            labels.extend([ya, 1.0 - ya])
            weights.extend([w, w])
        return np.array(rows), np.array(labels), np.array(weights)

    def _fit_one(self, battles, model_index):
        X, y, w = self._build_design(battles, model_index)
        # 不显式传 penalty，默认即 L2；避免 sklearn 1.8+ 的 deprecation 警告
        clf = LogisticRegression(
            C=self.C, fit_intercept=False, solver="lbfgs", max_iter=1000,
        )
        clf.fit(X, y, sample_weight=w)
        return clf.coef_.ravel()

    def fit(self, battles, model_index):
        beta_hat = self._fit_one(battles, model_index)
        boot_betas = []
        for _ in range(self.B):
            idx = self.rng.integers(0, len(battles), size=len(battles))
            try:
                boot_betas.append(self._fit_one([battles[i] for i in idx], model_index))
            except Exception:
                continue
        boot_betas = np.array(boot_betas)
        n_models = len(model_index)
        beta_boot = boot_betas[:, :n_models]

        ci_lower = np.percentile(beta_boot, 2.5, axis=0)
        ci_upper = np.percentile(beta_boot, 97.5, axis=0)
        ranks = np.argsort(np.argsort(-beta_boot, axis=1), axis=1)
        rank_ci_lower = np.percentile(ranks, 2.5, axis=0).astype(int)
        rank_ci_upper = np.percentile(ranks, 97.5, axis=0).astype(int)

        return {
            "beta_hat": beta_hat[:n_models],
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "rank_ci_lower": rank_ci_lower,
            "rank_ci_upper": rank_ci_upper,
            "gamma": beta_hat[n_models:],
        }
