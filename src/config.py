"""全局配置与阈值。

所有可调参数集中于此，便于复现与敏感性分析。阈值取值依据数据剖析结果
（见 results/data_profile.txt）与危货运输监管常识设定。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw" / "bds_hazmat.csv"
DATA_INTERIM = ROOT / "data" / "interim"
RESULTS_DIR = ROOT / "results"
FIG_DIR = RESULTS_DIR / "figures"
TABLE_DIR = RESULTS_DIR / "tables"


@dataclass(frozen=True)
class PreprocessConfig:
    # 坐标有效范围（中国陆域大致范围，过滤明显异常点）
    lon_min: float = 73.0
    lon_max: float = 135.0
    lat_min: float = 3.0
    lat_max: float = 54.0
    # 速度有效范围（km/h），数据被限速封顶在 85
    speed_min: float = 0.0
    speed_max: float = 100.0
    # 单步位移上限（km）：相邻两点位移超过该值视为跳变异常
    max_step_dist_km: float = 5.0
    # 稀疏对齐重采样步长（秒）
    resample_step_s: int = 30
    # 长盲区阈值（秒）：相邻报文间隔超过该值不插值并断开
    long_gap_s: int = 600
    # 行程切分：速度近似为零阈值（km/h）与持续停车时长阈值（秒）
    # 停车阈值取 20min（1200s）：与危货监管"连续驾驶后须休息≥20min"的休息单元对齐，
    # 使切分出的行程对应一个"驾驶段（两次合规休息之间的连续驾驶）"。
    stop_speed_kmh: float = 2.0
    stop_min_duration_s: int = 1200
    # 行程有效性：最短时长（秒）与最短里程（km）
    trip_min_duration_s: int = 300
    trip_min_distance_km: float = 1.0
    # 重采样后单段最少有效点数
    min_points_per_segment: int = 10


@dataclass(frozen=True)
class IndicatorConfig:
    # 限速（km/h）：危货车强制限速，数据上限 85，取 80 作为合规超速阈值
    speed_limit_kmh: float = 80.0
    # 北斗短报文为 30s 级稀疏采样，无法观测瞬时加减速度，故以"单个采样间隔内
    # 速度突变"作为急刹/急加速的可观测替代：相邻报文速度变化阈值（km/h）。
    # 仅在密采样步（Δt≤dense_gap_s）上计数，避免跨长插值段的伪事件。
    hard_brake_delta_kmh: float = -15.0
    hard_accel_delta_kmh: float = 15.0
    dense_gap_s: float = 60.0
    # 夜间时段（含端点 start，不含 end）
    night_start_hour: int = 22
    night_end_hour: int = 6
    # 连续驾驶时长上限（秒）：监管要求 4h
    continuous_drive_limit_s: int = 4 * 3600
    # 速度熵分箱（km/h）
    speed_entropy_bins: tuple = (0, 5, 20, 40, 60, 80, 101)


@dataclass(frozen=True)
class ExposureConfig:
    # 敏感目标接近度缓冲半径（km）
    bridge_tunnel_radius_km: float = 1.0
    city_center_radius_km: float = 5.0
    # 数据驱动点密度（建成区代理）网格边长（度，约 0.01°≈1.1km）
    density_grid_deg: float = 0.02
    # 点密度暴露取分位阈值，高于该分位视为高密度（建成区）
    density_high_quantile: float = 0.9


@dataclass(frozen=True)
class ModelConfig:
    seq_len: int = 32          # 自编码器输入序列长度（重采样步）
    seq_stride: int = 16       # 滑窗步长
    hidden_size: int = 64
    latent_size: int = 16
    num_layers: int = 1
    dropout: float = 0.0
    mask_ratio: float = 0.15   # 掩码重构比例
    batch_size: int = 256
    epochs: int = 25
    lr: float = 1e-3
    weight_decay: float = 1e-5
    val_ratio: float = 0.15
    seed: int = 42
    # 自监督异常分量在综合指数中的方向（重构误差越大风险越高）
    feature_cols: tuple = (
        "speed_norm", "acc_norm", "jerk_norm", "speed_change_norm", "dt_norm",
    )


@dataclass(frozen=True)
class GradingConfig:
    n_levels: int = 4
    level_names: tuple = ("低风险", "中风险", "高风险", "极高风险")
    # 高风险片段识别分位（综合指数 / 重构误差）
    high_risk_quantile: float = 0.90
    seed: int = 42


@dataclass(frozen=True)
class Config:
    pre: PreprocessConfig = field(default_factory=PreprocessConfig)
    ind: IndicatorConfig = field(default_factory=IndicatorConfig)
    exp: ExposureConfig = field(default_factory=ExposureConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    grade: GradingConfig = field(default_factory=GradingConfig)
    seed: int = 42


CONFIG = Config()


def ensure_dirs() -> None:
    for d in (DATA_INTERIM, RESULTS_DIR, FIG_DIR, TABLE_DIR):
        d.mkdir(parents=True, exist_ok=True)
