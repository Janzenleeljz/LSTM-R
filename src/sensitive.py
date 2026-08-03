"""危货情境暴露图层：敏感目标接近度 + 数据驱动建成区点密度代理。

说明：在缺乏权威 POI/GIS 图层的条件下，本模块采用两类可复现的代理：
1) 研究区（苏皖沿江为主）已知的跨江大桥/隧道与主要城市中心坐标（近似值，
   作为示例性敏感目标图层，便于复现，亦可替换为权威数据）；
2) 由轨迹点自身构建的网格点密度，作为建成区/人口密集区暴露代理。
论文中明确说明该图层为近似代理，并列为局限与未来工作（接入权威 GIS）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CONFIG, ExposureConfig
from .preprocess import haversine_km

# 跨江大桥/隧道（近似坐标，lon, lat）——苏皖沿江为主
BRIDGE_TUNNEL = [
    ("南京长江大桥", 118.745, 32.115),
    ("南京长江隧道", 118.680, 32.050),
    ("南京长江二桥", 118.860, 32.180),
    ("南京长江三桥", 118.550, 32.070),
    ("南京长江四桥", 118.950, 32.230),
    ("大胜关长江大桥", 118.660, 31.970),
    ("润扬长江大桥", 119.400, 32.230),
    ("泰州长江大桥", 119.970, 32.140),
    ("江阴长江大桥", 120.230, 31.940),
    ("苏通长江大桥", 120.840, 31.950),
    ("扬中长江大桥", 119.800, 32.180),
    ("马鞍山长江大桥", 118.430, 31.660),
    ("芜湖长江大桥", 118.300, 31.300),
    ("铜陵长江大桥", 117.780, 30.920),
    ("安庆长江大桥", 117.050, 30.500),
]

# 主要城市中心（人口密集区，近似坐标，lon, lat）
CITY_CENTER = [
    ("南京", 118.800, 32.060),
    ("扬州", 119.410, 32.390),
    ("镇江", 119.450, 32.200),
    ("泰州", 119.920, 32.460),
    ("常州", 119.970, 31.810),
    ("无锡", 120.300, 31.570),
    ("苏州", 120.620, 31.300),
    ("南通", 120.890, 31.980),
    ("合肥", 117.230, 31.820),
    ("马鞍山", 118.510, 31.670),
    ("滁州", 118.320, 32.300),
    ("上海", 121.470, 31.230),
]


def _min_dist_km(lon: np.ndarray, lat: np.ndarray, targets) -> np.ndarray:
    """每个点到目标集合的最近距离（km）。"""
    if len(targets) == 0:
        return np.full(len(lon), np.inf)
    d = np.full(len(lon), np.inf)
    for _, tlon, tlat in targets:
        d = np.minimum(d, haversine_km(lon, lat, tlon, tlat))
    return d


def annotate_exposure(points: pd.DataFrame, cfg: ExposureConfig = CONFIG.exp) -> pd.DataFrame:
    """为每个网格点标注敏感目标接近度与建成区点密度暴露标志。"""
    lon = points["lon"].to_numpy()
    lat = points["lat"].to_numpy()
    d_bt = _min_dist_km(lon, lat, BRIDGE_TUNNEL)
    d_city = _min_dist_km(lon, lat, CITY_CENTER)
    near_bt = (d_bt <= cfg.bridge_tunnel_radius_km).astype(np.int8)
    near_city = (d_city <= cfg.city_center_radius_km).astype(np.int8)

    # 数据驱动建成区点密度代理：网格化计数（仅用运动点，避免装卸场站长期停车主导）
    g = cfg.density_grid_deg
    gx = np.floor(lon / g).astype(np.int64)
    gy = np.floor(lat / g).astype(np.int64)
    cell = pd.Series(list(zip(gx, gy)))
    counts = cell.map(cell.value_counts())
    thresh = np.quantile(counts.to_numpy(), cfg.density_high_quantile)
    high_density = (counts.to_numpy() >= thresh).astype(np.int8)

    return points.assign(
        dist_bridge_tunnel_km=d_bt,
        dist_city_km=d_city,
        near_bridge_tunnel=near_bt,
        near_city=near_city,
        high_density=high_density,
    )
