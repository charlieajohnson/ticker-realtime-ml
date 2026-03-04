"""Training script for TickerNet.

Loads tick data from DuckDB, builds feature windows, trains the model
with early stopping, and saves the best checkpoint.

Usage:
    python -m backend.models.train
    python -m backend.models.train --epochs 30 --lr 0.0005
"""

import argparse
import logging
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

from backend.config import get_settings
from backend.database import get_connection
from backend.models.tickernet import TickerNet
from backend.pipeline.features import build_feature_vector

logger = logging.getLogger(__name__)

CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"
MODEL_VERSION = "v0.1"


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------


class TickDataset(Dataset):
    """Builds (feature_window, label) pairs from stored ticks.

    For each window of `window_size` ticks, the label is:
        direction = 1 (LONG) if price rose over the next `horizon` ticks, else 0 (SHORT)
        confidence_target = abs(return) clipped to [0, 1]
    """

    def __init__(
        self,
        symbols: list[str],
        window_size: int = 60,
        horizon: int = 10,
    ) -> None:
        self.windows: list[np.ndarray] = []
        self.directions: list[int] = []
        self.confidences: list[float] = []

        conn = get_connection()
        try:
            for symbol in symbols:
                df = conn.execute(
                    """
                    SELECT price, volume, bid, ask, timestamp
                    FROM ticks
                    WHERE symbol = ?
                    ORDER BY timestamp ASC
                    """,
                    [symbol],
                ).fetchdf()

                if len(df) < window_size + horizon:
                    continue

                vec = build_feature_vector(df)
                if vec is None:
                    continue

                prices = df["price"].values

                # Slide a window across the data
                for i in range(len(vec) - window_size - horizon + 1):
                    window = vec[i : i + window_size]
                    future_price = prices[i + window_size + horizon - 1]
                    current_price = prices[i + window_size - 1]

                    if current_price == 0:
                        continue

                    ret = (future_price - current_price) / current_price
                    direction = 1 if ret > 0 else 0
                    confidence = min(abs(ret) * 100, 1.0)  # scale small returns

                    self.windows.append(window)
                    self.directions.append(direction)
                    self.confidences.append(confidence)
        finally:
            conn.close()

        logger.info("Built dataset with %d samples", len(self.windows))

    def __len__(self) -> int:
        return len(self.windows)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        window = torch.tensor(self.windows[idx], dtype=torch.float32)
        direction = torch.tensor(self.directions[idx], dtype=torch.long)
        confidence = torch.tensor(self.confidences[idx], dtype=torch.float32)
        return window, direction, confidence


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def train(
    epochs: int = 50,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    batch_size: int = 32,
    patience: int = 10,
    window_size: int = 60,
    horizon: int = 10,
) -> Path | None:
    """Train TickerNet and save the best checkpoint.

    Returns the path to the saved checkpoint, or None if no data.
    """
    settings = get_settings()
    symbols = settings.symbol_list

    dataset = TickDataset(symbols, window_size=window_size, horizon=horizon)
    if len(dataset) == 0:
        logger.warning("No training samples — collect more tick data first")
        return None

    # Time-based split (80/20)
    split = int(len(dataset) * 0.8)
    train_ds = torch.utils.data.Subset(dataset, list(range(split)))
    val_ds = torch.utils.data.Subset(dataset, list(range(split, len(dataset))))

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    logger.info("Train: %d samples, Val: %d samples", len(train_ds), len(val_ds))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = TickerNet().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    direction_loss_fn = nn.CrossEntropyLoss()
    confidence_loss_fn = nn.MSELoss()

    best_val_loss = float("inf")
    patience_counter = 0
    checkpoint_path = CHECKPOINT_DIR / f"tickernet_{MODEL_VERSION}.pt"
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    for epoch in range(epochs):
        # --- Train ---
        model.train()
        train_loss = 0.0
        for windows, directions, confidences in train_loader:
            windows = windows.to(device)
            directions = directions.to(device)
            confidences = confidences.to(device).unsqueeze(1)

            dir_probs, conf_pred = model(windows)
            loss = direction_loss_fn(dir_probs, directions) + confidence_loss_fn(conf_pred, confidences)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(windows)

        train_loss /= len(train_ds)

        # --- Validate ---
        model.eval()
        val_loss = 0.0
        correct = 0
        total = 0
        with torch.no_grad():
            for windows, directions, confidences in val_loader:
                windows = windows.to(device)
                directions = directions.to(device)
                confidences = confidences.to(device).unsqueeze(1)

                dir_probs, conf_pred = model(windows)
                loss = direction_loss_fn(dir_probs, directions) + confidence_loss_fn(conf_pred, confidences)
                val_loss += loss.item() * len(windows)

                correct += (dir_probs.argmax(dim=1) == directions).sum().item()
                total += len(directions)

        val_loss /= len(val_ds)
        accuracy = correct / total if total > 0 else 0

        logger.info(
            "Epoch %d/%d — train=%.4f val=%.4f acc=%.3f",
            epoch + 1, epochs, train_loss, val_loss, accuracy,
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "model_version": MODEL_VERSION,
                    "val_loss": val_loss,
                    "accuracy": accuracy,
                    "epoch": epoch + 1,
                },
                checkpoint_path,
            )
            logger.info("Saved checkpoint: %s", checkpoint_path)
        else:
            patience_counter += 1
            if patience_counter >= patience:
                logger.info("Early stopping at epoch %d", epoch + 1)
                break

    return checkpoint_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Train TickerNet")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--window", type=int, default=60)
    parser.add_argument("--horizon", type=int, default=10)
    args = parser.parse_args()

    logging.basicConfig(level="INFO")

    from backend.database import init_tables
    init_tables()

    result = train(
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        patience=args.patience,
        window_size=args.window,
        horizon=args.horizon,
    )
    if result:
        print(f"Training complete. Checkpoint: {result}")
    else:
        print("No data available for training.")


if __name__ == "__main__":
    main()
