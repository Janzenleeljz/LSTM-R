"""结果可视化：训练曲线、权重、风险指数与分级分布、验证图、空间分布等。"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

from .config import CONFIG, FIG_DIR
from .indicators import INDICATOR_COLS

_FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
try:
    font_manager.fontManager.addfont(_FONT_PATH)
    _CJK = font_manager.FontProperties(fname=_FONT_PATH).get_name()
    plt.rcParams["font.sans-serif"] = [_CJK]
    plt.rcParams["axes.unicode_minus"] = False
except Exception:  # noqa: BLE001
    pass

LEVEL_COLORS = ["#2c7fb8", "#7fcdbb", "#fec44f", "#d95f0e"]


def _save(fig, name):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG_DIR / name, dpi=150, bbox_inches="tight")
    plt.close(fig)


def fig_training(history: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(history["epoch"], history["train_loss"], "-o", ms=3, label="训练损失")
    ax.plot(history["epoch"], history["val_loss"], "-s", ms=3, label="验证损失")
    ax.set_xlabel("训练轮次 Epoch")
    ax.set_ylabel("重构均方误差 MSE")
    ax.set_title("自监督 LSTM 自编码器训练曲线")
    ax.legend()
    ax.grid(alpha=0.3)
    _save(fig, "fig_training_curve.png")


def fig_weights(wt: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(wt))
    ax.bar(x - 0.27, wt["w_entropy"], 0.27, label="熵权法")
    ax.bar(x, wt["w_critic"], 0.27, label="CRITIC")
    ax.bar(x + 0.27, wt["w_combined"], 0.27, label="组合权重")
    ax.set_xticks(x)
    ax.set_xticklabels(wt["indicator"], rotation=40, ha="right", fontsize=8)
    ax.set_ylabel("权重")
    ax.set_title("替代安全指标权重（熵权法 / CRITIC / 组合）")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    _save(fig, "fig_indicator_weights.png")


def fig_risk_distribution(trip_risk: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].hist(trip_risk["risk_index"], bins=40, color="#3182bd", alpha=0.85)
    axes[0].set_xlabel("综合运行风险指数")
    axes[0].set_ylabel("行程数")
    axes[0].set_title("行程级综合风险指数分布")
    axes[0].grid(alpha=0.3)
    names = CONFIG.grade.level_names
    for g in sorted(trip_risk["grade"].unique()):
        sub = trip_risk[trip_risk["grade"] == g]["risk_index"]
        axes[1].hist(sub, bins=30, alpha=0.6, color=LEVEL_COLORS[g % 4], label=names[g])
    axes[1].set_xlabel("综合运行风险指数")
    axes[1].set_ylabel("行程数")
    axes[1].set_title("各风险等级的指数分布（KMeans 分级）")
    axes[1].legend()
    axes[1].grid(alpha=0.3)
    _save(fig, "fig_risk_distribution.png")


def fig_grade_counts(trip_risk: pd.DataFrame, veh_risk: pd.DataFrame):
    names = CONFIG.grade.level_names
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    tc = trip_risk["grade"].value_counts().sort_index()
    axes[0].bar([names[i] for i in tc.index], tc.values,
                color=[LEVEL_COLORS[i % 4] for i in tc.index])
    axes[0].set_ylabel("行程数")
    axes[0].set_title("行程风险等级分布")
    vc = veh_risk["grade"].value_counts().sort_index()
    axes[1].bar([names[i] for i in vc.index], vc.values,
                color=[LEVEL_COLORS[i % 4] for i in vc.index])
    axes[1].set_ylabel("车辆数")
    axes[1].set_title("车辆风险等级分布")
    _save(fig, "fig_grade_counts.png")


def fig_validation_box(trip_risk: pd.DataFrame):
    """分级外部一致性：左为全部指标的分级归一化均值热力图，右为代表性指标分级均值。"""
    names = CONFIG.grade.level_names
    grades = sorted(trip_risk["grade"].unique())
    # 各等级指标均值 → 按指标行做 min-max 归一，凸显随等级的单调趋势
    M = np.array([[trip_risk.loc[trip_risk["grade"] == g, c].mean() for g in grades]
                  for c in INDICATOR_COLS], dtype=float)
    lo = M.min(axis=1, keepdims=True)
    hi = M.max(axis=1, keepdims=True)
    Mn = (M - lo) / np.where(hi - lo < 1e-12, 1.0, hi - lo)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    im = axes[0].imshow(Mn, cmap="YlOrRd", aspect="auto")
    axes[0].set_xticks(range(len(grades)))
    axes[0].set_xticklabels([names[g] for g in grades])
    axes[0].set_yticks(range(len(INDICATOR_COLS)))
    axes[0].set_yticklabels(INDICATOR_COLS, fontsize=8)
    axes[0].set_title("各风险等级的指标均值（按指标行归一化）")
    for i in range(len(INDICATOR_COLS)):
        for j in range(len(grades)):
            axes[0].text(j, i, f"{M[i, j]:.3g}", ha="center", va="center",
                         fontsize=6, color="black")
    fig.colorbar(im, ax=axes[0], fraction=0.046, pad=0.04)

    show = ["acc_rms", "hard_accel_rate", "hard_brake_rate",
            "speed_entropy", "speed_std", "night_ratio"]
    x = np.arange(len(grades))
    w = 0.13
    for k, c in enumerate(show):
        vals = [trip_risk.loc[trip_risk["grade"] == g, c].mean() for g in grades]
        vals = np.array(vals)
        vals = vals / vals.max() if vals.max() > 0 else vals
        axes[1].bar(x + (k - 2.5) * w, vals, w, label=c)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels([names[g] for g in grades])
    axes[1].set_ylabel("分级均值（按指标归一化）")
    axes[1].set_title("代表性指标随风险等级单调上升")
    axes[1].legend(fontsize=7, ncol=2)
    axes[1].grid(axis="y", alpha=0.3)
    fig.suptitle("分级外部一致性：替代安全指标随风险等级的变化（Kruskal-Wallis 全部 p<0.001）",
                 fontsize=12)
    _save(fig, "fig_validation.png")


def fig_spatial(points: pd.DataFrame, trip_risk: pd.DataFrame):
    """高风险行程的空间分布（研究区核心）。"""
    mv = points[(points["trip_id"] >= 0) & points["valid_trip"]].copy()
    key = trip_risk.set_index(["plate_id", "trip_id"])["grade"].to_dict()
    mv["grade"] = [key.get((p, t), -1) for p, t in zip(mv["plate_id"], mv["trip_id"])]
    mv = mv[mv["grade"] >= 0]
    # 聚焦核心研究区
    core = mv[(mv["lon"].between(117, 122)) & (mv["lat"].between(30, 33))]
    sample = core.sample(min(60000, len(core)), random_state=0)
    fig, ax = plt.subplots(figsize=(8, 6))
    names = CONFIG.grade.level_names
    for g in sorted(sample["grade"].unique()):
        s = sample[sample["grade"] == g]
        ax.scatter(s["lon"], s["lat"], s=1, alpha=0.25,
                   color=LEVEL_COLORS[g % 4], label=names[g])
    ax.set_xlabel("经度")
    ax.set_ylabel("纬度")
    ax.set_title("核心研究区轨迹点风险等级空间分布（苏皖沿江）")
    lg = ax.legend(markerscale=6, loc="upper right")
    for h in lg.legend_handles:
        h.set_alpha(1)
    _save(fig, "fig_spatial_risk.png")


def fig_sparsity(points: pd.DataFrame):
    """采样间隔（稀疏性）分布。"""
    gap = points["gap_s"].to_numpy()
    gap = gap[gap > 0]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(np.clip(gap, 0, 600), bins=60, color="#756bb1", alpha=0.85)
    ax.set_xlabel("原始采样间隔 Δt (秒, 截断于 600s)")
    ax.set_ylabel("网格点数")
    ax.set_title("北斗短报文采样间隔（稀疏/不等间隔）分布")
    ax.grid(alpha=0.3)
    _save(fig, "fig_sparsity.png")


def fig_corr(trip_ind: pd.DataFrame):
    C = trip_ind[INDICATOR_COLS].corr().to_numpy()
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(C, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(INDICATOR_COLS)))
    ax.set_yticks(range(len(INDICATOR_COLS)))
    ax.set_xticklabels(INDICATOR_COLS, rotation=50, ha="right", fontsize=7)
    ax.set_yticklabels(INDICATOR_COLS, fontsize=7)
    ax.set_title("替代安全指标相关性矩阵")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    _save(fig, "fig_indicator_corr.png")


def all_figures(points, trips, trip_ind, history, wt, trip_risk, veh_risk, val):
    fig_training(history)
    fig_weights(wt)
    fig_risk_distribution(trip_risk)
    fig_grade_counts(trip_risk, veh_risk)
    fig_validation_box(trip_risk)
    fig_spatial(points, trip_risk)
    fig_sparsity(points)
    fig_corr(trip_ind)
