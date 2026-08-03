"""S5：多维替代安全指标体系（行程级，moving 点）。

三类指标，方向统一为"数值越大风险越高"（正向指标）：
  驾驶行为类：超速占比、超速强度、急刹率、急加速率、速度标准差、速度熵、加速度均方根
  监管合规类：连续驾驶超 4h 时间占比、夜间行驶占比
  危货情境暴露类：跨江桥隧接近暴露、城市中心接近暴露、建成区高密度暴露
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CONFIG, IndicatorConfig

# 指标列（与权重、风险指数共享顺序）
BEHAVIOR_COLS = [
    "overspeed_ratio", "overspeed_intensity", "hard_brake_rate", "hard_accel_rate",
    "speed_std", "speed_entropy", "acc_rms",
]
COMPLIANCE_COLS = ["continuous_over4h_ratio", "night_ratio"]
EXPOSURE_COLS = ["bridge_tunnel_exposure", "city_exposure", "density_exposure"]
INDICATOR_COLS = BEHAVIOR_COLS + COMPLIANCE_COLS + EXPOSURE_COLS


def _speed_entropy(speed_kmh: np.ndarray, bins) -> float:
    h, _ = np.histogram(speed_kmh, bins=bins)
    p = h / h.sum() if h.sum() > 0 else h
    p = p[p > 0]
    if p.size == 0:
        return 0.0
    return float(-(p * np.log(p)).sum())


def trip_indicators(g: pd.DataFrame, cfg: IndicatorConfig, step_s: int) -> dict:
    """对单个行程（已按时间排序的 moving 网格点）计算各替代安全指标。"""
    speed = g["speed"].to_numpy()          # km/h
    acc = g["acc"].to_numpy()              # m/s^2
    dist_km = g["dist_km"].to_numpy()
    gap_s = g["gap_s"].to_numpy()
    hours = g["ts"].dt.hour.to_numpy()
    n = len(g)
    total_dist = max(dist_km.sum(), 1e-6)
    duration_h = n * step_s / 3600.0

    overspeed = speed > cfg.speed_limit_kmh
    overspeed_ratio = float(overspeed.mean())
    overspeed_intensity = float(
        np.clip(speed[overspeed] - cfg.speed_limit_kmh, 0, None).mean()
    ) if overspeed.any() else 0.0

    # 急刹/急加速：相邻报文速度突变，仅在密采样步（Δt≤dense_gap_s）计数，按每 100km 归一
    dspeed = np.diff(speed, prepend=speed[0])
    dense = gap_s <= cfg.dense_gap_s
    hard_brake_rate = float(((dspeed <= cfg.hard_brake_delta_kmh) & dense).sum()
                            / total_dist * 100.0)
    hard_accel_rate = float(((dspeed >= cfg.hard_accel_delta_kmh) & dense).sum()
                            / total_dist * 100.0)

    speed_std = float(speed.std())
    speed_entropy = _speed_entropy(speed, cfg.speed_entropy_bins)
    acc_rms = float(np.sqrt((acc ** 2).mean()))

    # 连续驾驶超 4h：行程为连续运动，超过 4h 的时间占比
    over4h = max(duration_h - cfg.continuous_drive_limit_s / 3600.0, 0.0)
    continuous_over4h_ratio = float(over4h / duration_h) if duration_h > 0 else 0.0

    is_night = (hours >= cfg.night_start_hour) | (hours < cfg.night_end_hour)
    night_ratio = float(is_night.mean())

    bridge_tunnel_exposure = float(g["near_bridge_tunnel"].mean())
    city_exposure = float(g["near_city"].mean())
    density_exposure = float(g["high_density"].mean())

    return {
        "overspeed_ratio": overspeed_ratio,
        "overspeed_intensity": overspeed_intensity,
        "hard_brake_rate": hard_brake_rate,
        "hard_accel_rate": hard_accel_rate,
        "speed_std": speed_std,
        "speed_entropy": speed_entropy,
        "acc_rms": acc_rms,
        "continuous_over4h_ratio": continuous_over4h_ratio,
        "night_ratio": night_ratio,
        "bridge_tunnel_exposure": bridge_tunnel_exposure,
        "city_exposure": city_exposure,
        "density_exposure": density_exposure,
        "n_points": n,
        "distance_km": float(total_dist),
        "duration_h": duration_h,
        "mean_speed": float(speed.mean()),
    }


def build_trip_indicators(points: pd.DataFrame, cfg: IndicatorConfig = CONFIG.ind,
                          step_s: int = CONFIG.pre.resample_step_s) -> pd.DataFrame:
    moving = points[(points["trip_id"] >= 0) & points["valid_trip"]].copy()
    rows = []
    for (plate, trip), g in moving.groupby(["plate_id", "trip_id"], sort=True):
        rec = {"plate_id": plate, "trip_id": trip}
        rec.update(trip_indicators(g.sort_values("ts"), cfg, step_s))
        rows.append(rec)
    return pd.DataFrame(rows)


def aggregate_vehicle(trip_ind: pd.DataFrame) -> pd.DataFrame:
    """行程级 → 车辆级：以里程为权重做加权平均（计数类指标已按里程归一）。"""
    rows = []
    for plate, g in trip_ind.groupby("plate_id", sort=True):
        w = g["distance_km"].to_numpy()
        w = w / w.sum() if w.sum() > 0 else np.ones(len(g)) / len(g)
        rec = {"plate_id": plate, "n_trips": len(g),
               "total_distance_km": float(g["distance_km"].sum()),
               "total_duration_h": float(g["duration_h"].sum())}
        for c in INDICATOR_COLS:
            rec[c] = float((g[c].to_numpy() * w).sum())
        rows.append(rec)
    return pd.DataFrame(rows)
