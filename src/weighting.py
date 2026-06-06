"""S6–S7：标准化与组合赋权（熵权法 + CRITIC，几何平均组合）。

所有指标均为正向（越大越危险），统一采用极差(min-max)标准化到 [0,1]。
组合赋权降低单一客观赋权的偏倚：w = norm(sqrt(w_entropy * w_critic))。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

EPS = 1e-12


def minmax_normalize(X: np.ndarray) -> np.ndarray:
    """逐列极差标准化到 [0,1]（正向指标）。"""
    lo = X.min(axis=0)
    hi = X.max(axis=0)
    rng = np.where(hi - lo < EPS, 1.0, hi - lo)
    return (X - lo) / rng


def entropy_weight(X: np.ndarray) -> np.ndarray:
    """熵权法权重。输入为原始指标矩阵（正向）。"""
    R = minmax_normalize(X)
    n = R.shape[0]
    col_sum = R.sum(axis=0)
    col_sum = np.where(col_sum < EPS, 1.0, col_sum)
    P = R / col_sum
    k = 1.0 / np.log(n)
    with np.errstate(divide="ignore", invalid="ignore"):
        plnp = np.where(P > EPS, P * np.log(P), 0.0)
    e = -k * plnp.sum(axis=0)
    d = 1.0 - e
    d = np.where(d < 0, 0.0, d)
    if d.sum() < EPS:
        return np.ones(X.shape[1]) / X.shape[1]
    return d / d.sum()


def critic_weight(X: np.ndarray) -> np.ndarray:
    """CRITIC 法权重：对比强度(标准差) × 冲突性(1-相关)。"""
    R = minmax_normalize(X)
    sigma = R.std(axis=0, ddof=1)
    corr = np.corrcoef(R, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0)
    conflict = (1.0 - corr).sum(axis=1)
    C = sigma * conflict
    if C.sum() < EPS:
        return np.ones(X.shape[1]) / X.shape[1]
    return C / C.sum()


def combined_weight(X: np.ndarray) -> dict:
    """几何平均组合熵权与 CRITIC 权重。"""
    w_e = entropy_weight(X)
    w_c = critic_weight(X)
    w = np.sqrt(w_e * w_c)
    w = w / w.sum()
    return {"entropy": w_e, "critic": w_c, "combined": w}


def weighted_score(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """标准化后加权求和，得指标综合分量（[0,1] 量级）。"""
    R = minmax_normalize(X)
    return R @ w


def weights_table(cols: list[str], w: dict) -> pd.DataFrame:
    return pd.DataFrame(
        {"indicator": cols, "w_entropy": w["entropy"],
         "w_critic": w["critic"], "w_combined": w["combined"]}
    )
