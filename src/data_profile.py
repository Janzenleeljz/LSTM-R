"""数据剖析脚本：了解北斗短报文危货车 GPS 轨迹数据的基本特征。

输出：字段、车辆数、时间范围、采样间隔分布、速度分布、停车占比、
空间范围、每车点数等，供后续预处理与建模决策参考。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

RAW_COLUMNS = ["plate_id", "speed", "lon", "lat", "mileage", "gps_time", "date"]


def load_raw(path: str | Path) -> pd.DataFrame:
    """读取 GBK 编码的原始 CSV，统一英文列名。"""
    df = pd.read_csv(path, encoding="gbk", header=0, names=RAW_COLUMNS, dtype=str)
    df["speed"] = pd.to_numeric(df["speed"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["mileage"] = pd.to_numeric(df["mileage"], errors="coerce")
    # 时间：日期 + gps时间 合成 datetime
    dt = pd.to_datetime(
        df["date"].str.strip() + " " + df["gps_time"].str.strip(),
        format="%Y-%m-%d %H:%M:%S",
        errors="coerce",
    )
    df["ts"] = dt
    return df


def profile(df: pd.DataFrame) -> str:
    lines: list[str] = []
    n = len(df)
    lines.append(f"总记录数: {n:,}")
    lines.append(f"车辆数(plate_id): {df['plate_id'].nunique()}")
    lines.append(f"时间范围: {df['ts'].min()} ~ {df['ts'].max()}")
    lines.append("")
    lines.append("=== 缺失/异常 ===")
    for c in ["speed", "lon", "lat", "mileage", "ts"]:
        lines.append(f"  {c}: NaN={df[c].isna().sum():,}")
    lines.append("")
    lines.append("=== 速度分布(km/h) ===")
    sp = df["speed"].dropna()
    lines.append(f"  min={sp.min()}, max={sp.max()}, mean={sp.mean():.2f}, median={sp.median()}")
    for q in [0.5, 0.9, 0.95, 0.99, 1.0]:
        lines.append(f"  q{int(q*100)}={sp.quantile(q):.1f}")
    lines.append(f"  速度=0 占比: {(sp == 0).mean()*100:.2f}%")
    lines.append(f"  速度>80 占比: {(sp > 80).mean()*100:.4f}%")
    lines.append("")
    lines.append("=== 空间范围 ===")
    lines.append(f"  lon: {df['lon'].min():.4f} ~ {df['lon'].max():.4f}")
    lines.append(f"  lat: {df['lat'].min():.4f} ~ {df['lat'].max():.4f}")
    lines.append("")
    lines.append("=== 里程(km) ===")
    mil = df["mileage"].dropna()
    lines.append(f"  min={mil.min()}, max={mil.max()}")
    lines.append("")
    lines.append("=== 每车记录数 ===")
    counts = df.groupby("plate_id").size().sort_values(ascending=False)
    lines.append(f"  min={counts.min():,}, max={counts.max():,}, mean={counts.mean():,.0f}")
    lines.append(counts.to_string())
    lines.append("")

    # 采样间隔分布（按车排序后 diff）
    lines.append("=== 采样间隔(秒) 分布（按车内时间差）===")
    df_sorted = df.dropna(subset=["ts"]).sort_values(["plate_id", "ts"])
    dts = df_sorted.groupby("plate_id")["ts"].diff().dt.total_seconds().dropna()
    dts = dts[dts > 0]
    lines.append(f"  count={len(dts):,}")
    for q in [0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]:
        lines.append(f"  q{int(q*100)}={dts.quantile(q):.0f}s")
    lines.append(f"  max={dts.max():.0f}s ({dts.max()/3600:.1f}h)")
    lines.append(f"  间隔>120s 占比: {(dts > 120).mean()*100:.2f}%")
    lines.append(f"  间隔>300s 占比: {(dts > 300).mean()*100:.2f}%")
    lines.append(f"  间隔>1800s(30min,长盲区) 占比: {(dts > 1800).mean()*100:.2f}%")
    # 众数区间
    lines.append("  常见间隔(top10 取整秒):")
    vc = dts.round().astype(int).value_counts().head(10)
    for k, v in vc.items():
        lines.append(f"    {k}s: {v:,} ({v/len(dts)*100:.1f}%)")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/raw/bds_hazmat.csv")
    ap.add_argument("--out", default="results/data_profile.txt")
    args = ap.parse_args()

    df = load_raw(args.data)
    report = profile(df)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
