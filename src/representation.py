"""S8（表征部分）：自监督 LSTM 自编码器，Δt 感知 + 掩码重构。

在无标签的重采样行程序列上，以"重构自身"为自监督目标学习低维轨迹表征；
对部分时间步做随机掩码以增强对稀疏/不等间隔（北斗短报文）的鲁棒性；
将每个滑窗的重构误差作为综合风险指数的"异常分量"。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .config import CONFIG, ModelConfig


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)


def prepare_features(points: pd.DataFrame) -> pd.DataFrame:
    """为 moving 有效点构造逐步特征并做全局 z-score 标准化。"""
    mv = points[(points["trip_id"] >= 0) & points["valid_trip"]].copy()
    mv = mv.sort_values(["plate_id", "trip_id", "ts"])
    raw = pd.DataFrame({
        "speed": mv["speed"].to_numpy(),
        "acc": mv["acc"].to_numpy(),
        "jerk": mv["jerk"].to_numpy(),
        "speed_change": mv["speed_change"].to_numpy(),
        "dt": mv["gap_s"].to_numpy(),
    })
    for col, tgt in [("speed", "speed_norm"), ("acc", "acc_norm"),
                     ("jerk", "jerk_norm"), ("speed_change", "speed_change_norm"),
                     ("dt", "dt_norm")]:
        x = raw[col].to_numpy().astype(np.float64)
        mu, sd = x.mean(), x.std()
        mv[tgt] = (x - mu) / (sd if sd > 1e-9 else 1.0)
    return mv


def build_windows(mv: pd.DataFrame, cfg: ModelConfig):
    """按行程切滑窗，返回 (X[n,L,F], owner[(plate,trip)])。"""
    feats = list(cfg.feature_cols)
    X, owners = [], []
    for (plate, trip), g in mv.groupby(["plate_id", "trip_id"], sort=True):
        arr = g[feats].to_numpy(dtype=np.float32)
        n = len(arr)
        if n < cfg.seq_len:
            pad = np.repeat(arr[-1:], cfg.seq_len - n, axis=0)
            arr = np.vstack([arr, pad])
            n = len(arr)
        for s in range(0, n - cfg.seq_len + 1, cfg.seq_stride):
            X.append(arr[s:s + cfg.seq_len])
            owners.append((plate, trip))
        last = n - cfg.seq_len
        if last % cfg.seq_stride != 0:
            X.append(arr[last:last + cfg.seq_len])
            owners.append((plate, trip))
    return np.asarray(X, dtype=np.float32), owners


class LSTMAutoencoder(nn.Module):
    def __init__(self, cfg: ModelConfig, n_features: int):
        super().__init__()
        self.cfg = cfg
        self.n_features = n_features
        self.encoder = nn.LSTM(n_features, cfg.hidden_size, cfg.num_layers,
                               batch_first=True, dropout=cfg.dropout)
        self.to_latent = nn.Linear(cfg.hidden_size, cfg.latent_size)
        self.from_latent = nn.Linear(cfg.latent_size, cfg.hidden_size)
        self.decoder = nn.LSTM(cfg.hidden_size, cfg.hidden_size, cfg.num_layers,
                               batch_first=True, dropout=cfg.dropout)
        self.out = nn.Linear(cfg.hidden_size, n_features)

    def forward(self, x):
        _, (h, _) = self.encoder(x)
        z = self.to_latent(h[-1])                     # [B, latent]
        dec_in = self.from_latent(z).unsqueeze(1).repeat(1, x.size(1), 1)
        dec_out, _ = self.decoder(dec_in)
        return self.out(dec_out), z


def _mask(x: torch.Tensor, ratio: float) -> torch.Tensor:
    """对时间步随机掩码（置零），返回掩码后的输入。"""
    if ratio <= 0:
        return x
    B, L, _ = x.shape
    m = (torch.rand(B, L, device=x.device) < ratio).unsqueeze(-1)
    return x.masked_fill(m, 0.0)


def train_autoencoder(X: np.ndarray, cfg: ModelConfig = CONFIG.model):
    set_seed(cfg.seed)
    n = len(X)
    idx = np.random.permutation(n)
    n_val = int(n * cfg.val_ratio)
    val_idx, tr_idx = idx[:n_val], idx[n_val:]
    Xt = torch.from_numpy(X)
    tr = DataLoader(TensorDataset(Xt[tr_idx]), batch_size=cfg.batch_size, shuffle=True)
    va = DataLoader(TensorDataset(Xt[val_idx]), batch_size=cfg.batch_size)

    model = LSTMAutoencoder(cfg, X.shape[2])
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    lossf = nn.MSELoss()
    history = []
    for ep in range(cfg.epochs):
        model.train()
        tl = 0.0
        for (xb,) in tr:
            opt.zero_grad()
            recon, _ = model(_mask(xb, cfg.mask_ratio))
            loss = lossf(recon, xb)
            loss.backward()
            opt.step()
            tl += loss.item() * len(xb)
        model.eval()
        vl = 0.0
        with torch.no_grad():
            for (xb,) in va:
                recon, _ = model(xb)
                vl += lossf(recon, xb).item() * len(xb)
        history.append({"epoch": ep + 1,
                        "train_loss": tl / len(tr_idx),
                        "val_loss": vl / max(len(val_idx), 1)})
    return model, pd.DataFrame(history)


def window_scores(model: LSTMAutoencoder, X: np.ndarray, owners,
                  cfg: ModelConfig = CONFIG.model) -> pd.DataFrame:
    """计算每个滑窗的重构误差，并附 (plate,trip)。"""
    model.eval()
    Xt = torch.from_numpy(X)
    errs = np.zeros(len(X), dtype=np.float64)
    with torch.no_grad():
        for s in range(0, len(X), cfg.batch_size):
            xb = Xt[s:s + cfg.batch_size]
            recon, _ = model(xb)
            e = ((recon - xb) ** 2).mean(dim=(1, 2)).cpu().numpy()
            errs[s:s + len(xb)] = e
    plate = [o[0] for o in owners]
    trip = [o[1] for o in owners]
    return pd.DataFrame({"plate_id": plate, "trip_id": trip, "recon_error": errs})


def trip_anomaly(win_scores: pd.DataFrame) -> pd.DataFrame:
    """滑窗误差聚合到行程（均值 + 高分位捕捉极端片段）。"""
    g = win_scores.groupby(["plate_id", "trip_id"])["recon_error"]
    out = g.agg(recon_error_mean="mean",
                recon_error_p90=lambda s: s.quantile(0.90),
                n_windows="count").reset_index()
    return out
