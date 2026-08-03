"""端到端流程编排：S1–S10。

用法：
    python -m src.run_pipeline                # 全流程
    python -m src.run_pipeline --use-cache    # 复用已缓存的预处理结果
"""
from __future__ import annotations

import argparse
import json
import time

import pandas as pd

from . import viz
from .config import CONFIG, DATA_INTERIM, TABLE_DIR, ensure_dirs
from .grading import assign_levels, validate
from .indicators import aggregate_vehicle, build_trip_indicators
from .preprocess import run_preprocess
from .representation import (
    build_windows, prepare_features, train_autoencoder, trip_anomaly, window_scores,
)
from .risk_index import aggregate_vehicle_risk, compute_risk_index
from .sensitive import annotate_exposure
from .weighting import weights_table


def _load_or_preprocess(use_cache: bool):
    pf = DATA_INTERIM / "points.parquet"
    tf = DATA_INTERIM / "trips.parquet"
    if use_cache and pf.exists() and tf.exists():
        return pd.read_parquet(pf), pd.read_parquet(tf)
    return run_preprocess()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--use-cache", action="store_true")
    ap.add_argument("--alpha", type=float, default=0.3, help="自监督异常分量权重")
    args = ap.parse_args()

    ensure_dirs()
    t0 = time.time()
    log = {}

    print("[1/8] 预处理（S1–S4）...")
    points, trips = _load_or_preprocess(args.use_cache)
    log["n_grid_points"] = int(len(points))
    log["n_valid_trips"] = int(len(trips))
    log["n_vehicles"] = int(points["plate_id"].nunique())

    print("[2/8] 危货情境暴露标注（S5）...")
    points = annotate_exposure(points)

    print("[3/8] 多维替代安全指标（S5）...")
    trip_ind = build_trip_indicators(points)
    veh_ind = aggregate_vehicle(trip_ind)
    trip_ind.to_csv(TABLE_DIR / "trip_indicators.csv", index=False, encoding="utf-8-sig")
    veh_ind.to_csv(TABLE_DIR / "vehicle_indicators.csv", index=False, encoding="utf-8-sig")

    print("[4/8] 自监督 LSTM 自编码器表征（S8）...")
    mv = prepare_features(points)
    X, owners = build_windows(mv, CONFIG.model)
    log["n_windows"] = int(len(X))
    model, history = train_autoencoder(X)
    history.to_csv(TABLE_DIR / "training_history.csv", index=False)
    win = window_scores(model, X, owners)
    trip_anom = trip_anomaly(win)

    print("[5/8] 综合运行风险指数（TOPSIS 融合，S8）...")
    trip_risk, weights = compute_risk_index(trip_ind, trip_anom, alpha=args.alpha)
    wt = weights_table(weights["indicator_cols"], {
        "entropy": weights["w_entropy"], "critic": weights["w_critic"],
        "combined": weights["w_combined"]})
    wt.to_csv(TABLE_DIR / "indicator_weights.csv", index=False, encoding="utf-8-sig")

    print("[6/8] 风险分级与验证（S9）...")
    trip_risk = assign_levels(trip_risk)
    val = validate(trip_risk)
    veh_risk = aggregate_vehicle_risk(trip_risk)
    # 车辆级分级
    from .grading import grade_kmeans
    veh_risk["grade"] = grade_kmeans(veh_risk["risk_index"].to_numpy(),
                                     CONFIG.grade.n_levels, CONFIG.grade.seed)
    veh_risk["grade_name"] = veh_risk["grade"].map(dict(enumerate(CONFIG.grade.level_names)))

    trip_risk.to_csv(TABLE_DIR / "trip_risk.csv", index=False, encoding="utf-8-sig")
    veh_risk.to_csv(TABLE_DIR / "vehicle_risk.csv", index=False, encoding="utf-8-sig")
    val["consistency"].to_csv(TABLE_DIR / "validation_consistency.csv",
                              index=False, encoding="utf-8-sig")

    print("[7/8] 生成图表...")
    viz.all_figures(points, trips, trip_ind, history, wt, trip_risk, veh_risk, val)

    print("[8/8] 汇总...")
    log["elapsed_s"] = round(time.time() - t0, 1)
    log["validation"] = val["summary"]
    log["alpha"] = args.alpha
    log["final_val_loss"] = float(history["val_loss"].iloc[-1])
    (TABLE_DIR / "run_summary.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(log, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
