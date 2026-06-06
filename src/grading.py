"""S9：风险等级划分与分级验证。

划分：对综合运行风险指数做分位法与一维 KMeans 聚类两种分级（4 级），
KMeans 聚类按簇均值升序映射到 低/中/高/极高。
验证：内部（轮廓系数）、外部一致性（各替代指标随等级单调性 + Kruskal-Wallis
检验）、消融（与"仅指标/仅自监督"分级的一致性 ARI、Spearman 相关）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import kruskal, spearmanr
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score

from .config import CONFIG, GradingConfig
from .indicators import INDICATOR_COLS


def grade_quantile(scores: np.ndarray, n_levels: int) -> np.ndarray:
    qs = np.quantile(scores, np.linspace(0, 1, n_levels + 1))
    qs[0], qs[-1] = -np.inf, np.inf
    return np.clip(np.digitize(scores, qs[1:-1]), 0, n_levels - 1)


def grade_kmeans(scores: np.ndarray, n_levels: int, seed: int) -> np.ndarray:
    km = KMeans(n_clusters=n_levels, random_state=seed, n_init=10)
    lab = km.fit_predict(scores.reshape(-1, 1))
    order = np.argsort([scores[lab == c].mean() for c in range(n_levels)])
    remap = {c: rank for rank, c in enumerate(order)}
    return np.array([remap[c] for c in lab])


def assign_levels(trip_risk: pd.DataFrame, cfg: GradingConfig = CONFIG.grade) -> pd.DataFrame:
    df = trip_risk.copy()
    s = df["risk_index"].to_numpy()
    df["grade_q"] = grade_quantile(s, cfg.n_levels)
    df["grade_km"] = grade_kmeans(s, cfg.n_levels, cfg.seed)
    df["grade"] = df["grade_km"]
    df["grade_name"] = df["grade"].map(dict(enumerate(cfg.level_names)))
    thr = np.quantile(s, cfg.high_risk_quantile)
    df["is_high_risk"] = (s >= thr).astype(int)
    return df


def validate(trip_risk: pd.DataFrame, cfg: GradingConfig = CONFIG.grade) -> dict:
    df = trip_risk
    s = df["risk_index"].to_numpy()
    grade = df["grade"].to_numpy()
    X = df[INDICATOR_COLS].to_numpy(dtype=np.float64)

    # 内部：轮廓系数（指标空间 + 一维指数空间）
    sil_index = float(silhouette_score(s.reshape(-1, 1), grade)) if len(set(grade)) > 1 else float("nan")
    Xn = (X - X.mean(0)) / np.where(X.std(0) < 1e-9, 1.0, X.std(0))
    sil_feat = float(silhouette_score(Xn, grade)) if len(set(grade)) > 1 else float("nan")

    # 外部一致性：各指标随等级的均值 + Kruskal-Wallis 检验
    rows = []
    for c in INDICATOR_COLS:
        groups = [df.loc[grade == g, c].to_numpy() for g in sorted(set(grade))]
        groups = [g for g in groups if len(g) > 0]
        try:
            H, p = kruskal(*groups)
        except ValueError:
            H, p = np.nan, np.nan
        rho, _ = spearmanr(s, df[c].to_numpy())
        rec = {"indicator": c, "kruskal_H": H, "kruskal_p": p, "spearman_rho": rho}
        for g in sorted(set(grade)):
            rec[f"mean_L{g}"] = float(df.loc[grade == g, c].mean())
        rows.append(rec)
    consistency = pd.DataFrame(rows)

    # 消融：与仅指标/仅自监督分级的一致性
    g_ind = grade_kmeans(df["risk_index_ind_only"].to_numpy(), cfg.n_levels, cfg.seed)
    g_anom = grade_kmeans(df["risk_index_anom_only"].to_numpy(), cfg.n_levels, cfg.seed)
    ari_ind = float(adjusted_rand_score(grade, g_ind))
    ari_anom = float(adjusted_rand_score(grade, g_anom))
    rho_ind, _ = spearmanr(s, df["risk_index_ind_only"])
    rho_anom, _ = spearmanr(s, df["risk_index_anom_only"])
    rho_qkm, _ = spearmanr(df["grade_q"], df["grade_km"])
    ari_qkm = float(adjusted_rand_score(df["grade_q"], df["grade_km"]))

    summary = {
        "silhouette_index_space": sil_index,
        "silhouette_feature_space": sil_feat,
        "ari_full_vs_ind_only": ari_ind,
        "ari_full_vs_anom_only": ari_anom,
        "spearman_full_vs_ind_only": float(rho_ind),
        "spearman_full_vs_anom_only": float(rho_anom),
        "spearman_quantile_vs_kmeans": float(rho_qkm),
        "ari_quantile_vs_kmeans": ari_qkm,
        "n_trips": int(len(df)),
        "grade_counts": {int(g): int((grade == g).sum()) for g in sorted(set(grade))},
    }
    return {"summary": summary, "consistency": consistency}
