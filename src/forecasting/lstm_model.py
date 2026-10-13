"""PyTorch LSTM for PM2.5 t+1h experiment (not production lock)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from src.forecasting.constants import (
    LSTM_DROPOUT,
    LSTM_HIDDEN,
    LSTM_STATION_EMB_DIM,
)
from src.forecasting.metrics import regression_metrics
from src.forecasting.models import RANDOM_STATE


def resolve_device(prefer_cuda: bool = True) -> torch.device:
    if prefer_cuda and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class Pm25LSTM(nn.Module):
    """1-layer LSTM; station embedding concatenated at every timestep."""

    def __init__(
        self,
        n_features: int,
        n_stations: int,
        *,
        hidden: int = LSTM_HIDDEN,
        dropout: float = LSTM_DROPOUT,
        emb_dim: int = LSTM_STATION_EMB_DIM,
    ) -> None:
        super().__init__()
        self.station_emb = nn.Embedding(n_stations, emb_dim)
        self.lstm = nn.LSTM(
            input_size=n_features + emb_dim,
            hidden_size=hidden,
            num_layers=1,
            batch_first=True,
            dropout=0.0,
        )
        self.drop = nn.Dropout(dropout)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor, station_ids: torch.Tensor) -> torch.Tensor:
        # x: (B, T, F); station_ids: (B,)
        emb = self.station_emb(station_ids)  # (B, E)
        emb_t = emb.unsqueeze(1).expand(-1, x.size(1), -1)
        inp = torch.cat([x, emb_t], dim=-1)
        out, _ = self.lstm(inp)
        h = self.drop(out[:, -1, :])
        return self.head(h).squeeze(-1)


@dataclass
class LstmTrainResult:
    model: Pm25LSTM
    metrics: dict[str, dict[str, float]]
    predictions: np.ndarray
    best_epoch: int
    history: list[dict[str, float]]
    device: str


def _set_seed(seed: int = RANDOM_STATE) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


@torch.no_grad()
def _predict(
    model: Pm25LSTM,
    X: np.ndarray,
    station_ids: np.ndarray,
    *,
    device: torch.device,
    batch_size: int = 1024,
) -> np.ndarray:
    model.eval()
    preds: list[np.ndarray] = []
    n = len(X)
    for start in range(0, n, batch_size):
        xb = torch.from_numpy(X[start : start + batch_size]).to(device)
        sb = torch.from_numpy(station_ids[start : start + batch_size]).to(device)
        preds.append(model(xb, sb).cpu().numpy())
    return np.concatenate(preds, axis=0) if preds else np.array([], dtype=np.float32)


def train_lstm(
    X: np.ndarray,
    station_ids: np.ndarray,
    y: np.ndarray,
    meta: pd.DataFrame,
    *,
    n_stations: int,
    device: torch.device | None = None,
    hidden: int = LSTM_HIDDEN,
    dropout: float = LSTM_DROPOUT,
    emb_dim: int = LSTM_STATION_EMB_DIM,
    lr: float = 1e-3,
    batch_size: int = 256,
    max_epochs: int = 30,
    patience: int = 5,
    random_state: int = RANDOM_STATE,
) -> LstmTrainResult:
    """Train with Adam + L1 loss; early stop on val MAE."""
    _set_seed(random_state)
    device = device or resolve_device()

    train_m = (meta["split"] == "train").to_numpy()
    val_m = (meta["split"] == "val").to_numpy()
    if not train_m.any() or not val_m.any():
        raise ValueError("Need non-empty train and val splits for LSTM")

    model = Pm25LSTM(
        n_features=X.shape[-1],
        n_stations=n_stations,
        hidden=hidden,
        dropout=dropout,
        emb_dim=emb_dim,
    ).to(device)

    train_ds = TensorDataset(
        torch.from_numpy(X[train_m]),
        torch.from_numpy(station_ids[train_m]),
        torch.from_numpy(y[train_m].astype(np.float32)),
    )
    loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.L1Loss()

    best_state: dict[str, Any] | None = None
    best_val = float("inf")
    best_epoch = 0
    bad_epochs = 0
    history: list[dict[str, float]] = []

    for epoch in range(1, max_epochs + 1):
        model.train()
        epoch_losses: list[float] = []
        for xb, sb, yb in loader:
            xb = xb.to(device)
            sb = sb.to(device)
            yb = yb.to(device)
            opt.zero_grad(set_to_none=True)
            pred = model(xb, sb)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()
            epoch_losses.append(float(loss.item()))

        val_pred = _predict(model, X[val_m], station_ids[val_m], device=device)
        val_mae = float(np.mean(np.abs(y[val_m] - val_pred)))
        train_mae_approx = float(np.mean(epoch_losses)) if epoch_losses else float("nan")
        history.append(
            {"epoch": epoch, "train_l1": train_mae_approx, "val_mae": val_mae}
        )

        if val_mae < best_val - 1e-6:
            best_val = val_mae
            best_epoch = epoch
            bad_epochs = 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                break

    if best_state is None:
        raise RuntimeError("LSTM training produced no checkpoint")
    model.load_state_dict(best_state)
    model.to(device)

    all_pred = _predict(model, X, station_ids, device=device)
    metrics: dict[str, dict[str, float]] = {}
    for split in ("train", "val", "test"):
        m = (meta["split"] == split).to_numpy()
        if not m.any():
            continue
        metrics[split] = regression_metrics(y[m], all_pred[m])

    return LstmTrainResult(
        model=model,
        metrics=metrics,
        predictions=all_pred.astype(np.float64),
        best_epoch=best_epoch,
        history=history,
        device=str(device),
    )
