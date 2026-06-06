"""S8（融合部分）：综合运行风险指数 = 加权指标分量 ⊕ 自监督异常分量（TOPSIS）。

将 12 项替代安全指标与自监督重构误差合成一个决策矩阵（全部为正向风险准则），
采用 TOPSIS 计算每条行程相对"最危险/最安全"理想解的贴近度，得到 [0,1]
综合运行风险指数（越大越危险）。异常分量权重 alpha 可配置。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import INDICATOR_COLS
from .weighting import combined_weight

EPS = 1e-12


def topsis_risk(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """对正向风险矩阵做 TOPSIS，返回风险贴近度 [0,1]（越大越危险）。"""
    norm = np.sqrt((X ** 2).sum(axis=0))
    norm = np.where(norm < EPS, 1.0, norm)
    R = X / norm
    V = R * w
    risky_ideal = V.max(axis=0)   # 正理想解：最危险
    safe_ideal = V.min(axis=0)    # 负理想解：最安全
    d_to_risky = np.sqrt(((V - risky_ideal) ** 2).sum(axis=1))
    d_to_safe = np.sqrt(((V - safe_ideal) ** 2).sum(axis=1))
    denom = d_to_risky + d_to_safe
    denom = np.where(denom < EPS, 1.0, denom)
    return d_to_safe / denom


def compute_risk_index(trip_ind: pd.DataFrame, trip_anom: pd.DataFrame,
                       alpha: float = 0.3):
    """合成行程级综合运行风险指数。

    alpha: 自监督异常分量在融合中的权重；(1-alpha) 分配给 12 项指标（按组合权重）。
    返回 (带风险指数的行程表, 权重明细 dict)。
    """
    df = trip_ind.merge(trip_anom, on=["plate_id", "trip_id"], how="left")
    df["recon_error_mean"] = df["recon_error_mean"].fillna(df["recon_error_mean"].median())

    X_ind = df[INDICATOR_COLS].to_numpy(dtype=np.float64)
    w = combined_weight(X_ind)
    w_ind = w["combined"]

    anom = df["recon_error_mean"].to_numpy(dtype=np.float64).reshape(-1, 1)
    X_aug = np.hstack([X_ind, anom])
    w_aug = np.concatenate([w_ind * (1.0 - alpha), [alpha]])
    w_aug = w_aug / w_aug.sum()

    df["risk_index"] = topsis_risk(X_aug, w_aug)
    # 仅指标（消融：去掉自监督分量）
    df["risk_index_ind_only"] = topsis_risk(X_ind, w_ind)
    # 仅自监督（消融）：异常分量的分位归一
    r = df["recon_error_mean"].rank(pct=True)
    df["risk_index_anom_only"] = r.to_numpy()

    weights = {
        "indicator_cols": INDICATOR_COLS,
        "w_entropy": w["entropy"],
        "w_critic": w["critic"],
        "w_combined": w_ind,
        "alpha_anomaly": alpha,
        "w_augmented": w_aug,
    }
    return df, weights


def aggregate_vehicle_risk(trip_risk: pd.DataFrame) -> pd.DataFrame:
    """行程级风险指数 → 车辆级（里程加权平均 + 高风险行程占比）。"""
    rows = []
    for plate, g in trip_risk.groupby("plate_id", sort=True):
        wdist = g["distance_km"].to_numpy()
        wdist = wdist / wdist.sum() if wdist.sum() > 0 else np.ones(len(g)) / len(g)
        rows.append({
            "plate_id": plate,
            "n_trips": len(g),
            "total_distance_km": float(g["distance_km"].sum()),
            "risk_index": float((g["risk_index"].to_numpy() * wdist).sum()),
            "risk_index_mean": float(g["risk_index"].mean()),
            "risk_index_p90": float(g["risk_index"].quantile(0.90)),
        })
    return pd.DataFrame(rows)
