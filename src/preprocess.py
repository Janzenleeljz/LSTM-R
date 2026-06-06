"""S1–S4：数据接入、清洗、稀疏对齐与重采样、行程切分。

对应发明专利的 S1（数据接入）、S2（清洗）、S3（稀疏对齐 + 长盲区分段 + 重采样
并生成插值掩码）、S4（依据持续停车切分行程）。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import CONFIG, DATA_INTERIM, PreprocessConfig

RAW_COLUMNS = ["plate_id", "speed", "lon", "lat", "mileage", "gps_time", "date"]
EARTH_R_KM = 6371.0088


def to_unix_s(ts) -> np.ndarray:
    """将 datetime 序列稳健地转换为 unix 秒（兼容 ns/us/ms 等分辨率）。"""
    return ts.to_numpy().astype("datetime64[ns]").astype("int64") / 1e9


def haversine_km(lon1, lat1, lon2, lat2):
    """向量化 haversine 距离（km）。"""
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0) ** 2
    return 2.0 * EARTH_R_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def load_raw(path: str | Path) -> pd.DataFrame:
    """S1：读取 GBK 原始 CSV，统一英文列名并解析时间。"""
    df = pd.read_csv(path, encoding="gbk", header=0, names=RAW_COLUMNS, dtype=str)
    for c in ["speed", "lon", "lat", "mileage"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ts"] = pd.to_datetime(
        df["date"].str.strip() + " " + df["gps_time"].str.strip(),
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce",
    )
    return df.drop(columns=["gps_time", "date"])


def clean(df: pd.DataFrame, cfg: PreprocessConfig) -> pd.DataFrame:
    """S2：清洗——去除缺失/越界/重复，统一排序。"""
    df = df.dropna(subset=["ts", "lon", "lat", "speed"]).copy()
    m = (
        df["lon"].between(cfg.lon_min, cfg.lon_max)
        & df["lat"].between(cfg.lat_min, cfg.lat_max)
        & df["speed"].between(cfg.speed_min, cfg.speed_max)
    )
    df = df[m]
    df = df.sort_values(["plate_id", "ts"])
    # 同一车辆同一时刻去重，保留第一条
    df = df.drop_duplicates(subset=["plate_id", "ts"], keep="first")
    return df.reset_index(drop=True)


def _drop_position_jumps(g: pd.DataFrame, cfg: PreprocessConfig) -> pd.DataFrame:
    """剔除相邻点位移异常跳变（短时间内大位移，物理不可达）。"""
    lon = g["lon"].to_numpy()
    lat = g["lat"].to_numpy()
    ts = to_unix_s(g["ts"])
    keep = np.ones(len(g), dtype=bool)
    if len(g) < 2:
        return g
    prev = 0
    for i in range(1, len(g)):
        dt = ts[i] - ts[prev]
        d = haversine_km(lon[prev], lat[prev], lon[i], lat[i])
        implied_kmh = d / (dt / 3600.0) if dt > 0 else np.inf
        # 短时大位移（>5km 且等效时速>150）判为跳变
        if d > cfg.max_step_dist_km and implied_kmh > 150.0:
            keep[i] = False
        else:
            prev = i
    return g[keep]


def _resample_segment(seg: pd.DataFrame, cfg: PreprocessConfig) -> pd.DataFrame | None:
    """对单个连续段（无长盲区）按固定步长重采样 + 线性插值 + 插值掩码。"""
    t = to_unix_s(seg["ts"])
    t0, t1 = t[0], t[-1]
    if t1 - t0 < cfg.resample_step_s:
        return None
    grid = np.arange(t0, t1 + 1e-6, cfg.resample_step_s)
    if len(grid) < cfg.min_points_per_segment:
        return None
    lon = np.interp(grid, t, seg["lon"].to_numpy())
    lat = np.interp(grid, t, seg["lat"].to_numpy())
    speed = np.interp(grid, t, seg["speed"].to_numpy())
    mileage = np.interp(grid, t, seg["mileage"].to_numpy())
    # 插值掩码：网格点附近 (±step/2) 是否存在原始观测（向量化）
    half = cfg.resample_step_s / 2.0
    idx = np.searchsorted(t, grid)
    idx_hi = np.clip(idx, 0, len(t) - 1)
    idx_lo = np.clip(idx - 1, 0, len(t) - 1)
    nearest = np.minimum(np.abs(t[idx_hi] - grid), np.abs(t[idx_lo] - grid))
    obs_mask = (nearest <= half).astype(np.int8)
    # 每个网格点所在的原始采样间隔（Δt），反映局部稀疏程度
    seg_idx = np.clip(np.searchsorted(t, grid, side="right"), 1, len(t) - 1)
    local_gap = t[seg_idx] - t[seg_idx - 1]
    out = pd.DataFrame(
        {
            "t_unix": grid,
            "lon": lon,
            "lat": lat,
            "speed": speed,
            "mileage": mileage,
            "interp_mask": obs_mask,
            "gap_s": local_gap,
        }
    )
    return out


def _segment_and_resample(g: pd.DataFrame, cfg: PreprocessConfig) -> pd.DataFrame:
    """S3：按长盲区断开为连续段，逐段重采样。"""
    ts = to_unix_s(g["ts"])
    gap = np.diff(ts, prepend=ts[0])
    seg_break = (gap > cfg.long_gap_s).astype(int)
    seg_id = np.cumsum(seg_break)
    g = g.assign(_seg=seg_id)
    parts = []
    sid = 0
    for _, seg in g.groupby("_seg", sort=True):
        rs = _resample_segment(seg, cfg)
        if rs is None:
            continue
        rs["seg_id"] = sid
        parts.append(rs)
        sid += 1
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def _segment_trips(seg: pd.DataFrame, cfg: PreprocessConfig) -> np.ndarray:
    """S4：在重采样段内依据持续停车切分行程，返回 trip 局部编号（-1=停车不计行程）。"""
    speed = seg["speed"].to_numpy()
    moving = speed > cfg.stop_speed_kmh
    n = len(seg)
    trip_id = np.full(n, -1, dtype=int)
    step = cfg.resample_step_s
    min_stop_steps = max(1, int(cfg.stop_min_duration_s / step))
    # 标记长停车段
    is_stop = ~moving
    # 行程 = 被长停车分隔的运动区间
    cur_trip = -1
    i = 0
    in_trip = False
    while i < n:
        if moving[i]:
            if not in_trip:
                cur_trip += 1
                in_trip = True
            trip_id[i] = cur_trip
            i += 1
        else:
            # 计算连续停车长度
            j = i
            while j < n and is_stop[j]:
                j += 1
            stop_len = j - i
            if stop_len >= min_stop_steps:
                in_trip = False  # 长停车，结束当前行程
            else:
                # 短停车（如等红灯）并入当前行程（若在行程中）
                if in_trip:
                    trip_id[i:j] = cur_trip
            i = j
    return trip_id


def _enrich(seg: pd.DataFrame, cfg: PreprocessConfig) -> pd.DataFrame:
    """为重采样后的网格点计算逐步派生特征（位移、等效速度、加速度、jerk）。"""
    step = cfg.resample_step_s
    lon = seg["lon"].to_numpy()
    lat = seg["lat"].to_numpy()
    dist_km = np.zeros(len(seg))
    dist_km[1:] = haversine_km(lon[:-1], lat[:-1], lon[1:], lat[1:])
    speed_ms = seg["speed"].to_numpy() / 3.6
    eq_speed_ms = dist_km * 1000.0 / step
    acc = np.zeros(len(seg))
    acc[1:] = np.diff(speed_ms) / step
    jerk = np.zeros(len(seg))
    jerk[1:] = np.diff(acc) / step
    seg = seg.assign(
        dist_km=dist_km,
        speed_ms=speed_ms,
        eq_speed_ms=eq_speed_ms,
        acc=acc,
        jerk=jerk,
        speed_change=np.r_[0.0, np.abs(np.diff(seg["speed"].to_numpy()))],
    )
    return seg


def preprocess_vehicle(g: pd.DataFrame, cfg: PreprocessConfig) -> pd.DataFrame:
    g = _drop_position_jumps(g, cfg)
    if len(g) < cfg.min_points_per_segment:
        return pd.DataFrame()
    rs = _segment_and_resample(g, cfg)
    if rs.empty:
        return pd.DataFrame()
    rs["ts"] = pd.to_datetime(rs["t_unix"], unit="s")
    parts = []
    for seg_id, seg in rs.groupby("seg_id", sort=True):
        seg = seg.reset_index(drop=True)
        seg = _enrich(seg, cfg)
        local_trip = _segment_trips(seg, cfg)
        seg = seg.assign(local_trip=local_trip)
        parts.append(seg)
    out = pd.concat(parts, ignore_index=True)
    # 生成全局 trip_id（车辆内唯一）：seg_id * 1000 + local_trip
    out["trip_id"] = np.where(
        out["local_trip"] >= 0,
        out["seg_id"].astype(int) * 1000 + out["local_trip"].astype(int),
        -1,
    )
    return out


def build_trips_table(points: pd.DataFrame, cfg: PreprocessConfig) -> pd.DataFrame:
    """聚合得到有效行程表（过滤过短行程）。"""
    moving = points[points["trip_id"] >= 0].copy()
    rows = []
    for (plate, trip), g in moving.groupby(["plate_id", "trip_id"], sort=True):
        dur_s = (len(g)) * cfg.resample_step_s
        dist = g["dist_km"].sum()
        if dur_s < cfg.trip_min_duration_s or dist < cfg.trip_min_distance_km:
            continue
        rows.append(
            {
                "plate_id": plate,
                "trip_id": trip,
                "n_points": len(g),
                "duration_s": dur_s,
                "distance_km": dist,
                "start_ts": g["ts"].min(),
                "end_ts": g["ts"].max(),
            }
        )
    return pd.DataFrame(rows)


def run_preprocess(cfg=CONFIG.pre, data_path=None, save=True):
    from .config import DATA_RAW

    raw = load_raw(data_path or DATA_RAW)
    clean_df = clean(raw, cfg)
    parts = []
    for plate, g in clean_df.groupby("plate_id", sort=True):
        out = preprocess_vehicle(g.reset_index(drop=True), cfg)
        if not out.empty:
            out["plate_id"] = plate
            parts.append(out)
    points = pd.concat(parts, ignore_index=True)
    trips = build_trips_table(points, cfg)
    valid_keys = set(zip(trips["plate_id"], trips["trip_id"]))
    points["valid_trip"] = [
        (p, t) in valid_keys for p, t in zip(points["plate_id"], points["trip_id"])
    ]
    if save:
        DATA_INTERIM.mkdir(parents=True, exist_ok=True)
        points.to_parquet(DATA_INTERIM / "points.parquet", index=False)
        trips.to_parquet(DATA_INTERIM / "trips.parquet", index=False)
    return points, trips


if __name__ == "__main__":
    pts, tr = run_preprocess()
    print(f"重采样网格点: {len(pts):,}")
    print(f"有效行程数: {len(tr):,}")
    print(tr.groupby("plate_id")["distance_km"].agg(["count", "sum"]).round(1))
