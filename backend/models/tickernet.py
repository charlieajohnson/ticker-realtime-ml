"""PyTorch model definition — LSTM + Attention.

TickerNet: a lightweight model for short-term price movement prediction.

Architecture:
    Input (batch, seq_len, 10)
    → LSTM (hidden=64, layers=2, dropout=0.2)
    → Single-head Attention over hidden states
    → Linear(64→32) + ReLU + Dropout(0.3)
    → Linear(32→2) → direction (softmax) + confidence (sigmoid)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class Attention(nn.Module):
    """Single-head attention over LSTM hidden states.

    Uses the last hidden state as the query to attend over all timesteps.
    """

    def __init__(self, hidden_size: int) -> None:
        super().__init__()
        self.attn = nn.Linear(hidden_size, hidden_size)
        self.v = nn.Linear(hidden_size, 1, bias=False)

    def forward(self, lstm_output: torch.Tensor) -> torch.Tensor:
        """
        Args:
            lstm_output: (batch, seq_len, hidden_size)

        Returns:
            context: (batch, hidden_size)
        """
        # Score each timestep
        energy = torch.tanh(self.attn(lstm_output))  # (batch, seq, hidden)
        scores = self.v(energy).squeeze(-1)  # (batch, seq)
        weights = F.softmax(scores, dim=1)  # (batch, seq)

        # Weighted sum of hidden states
        context = torch.bmm(weights.unsqueeze(1), lstm_output).squeeze(1)  # (batch, hidden)
        return context


class TickerNet(nn.Module):
    """LSTM + Attention model for price direction prediction.

    Args:
        input_size: Number of features per timestep (default: 10).
        hidden_size: LSTM hidden dimension (default: 64).
        num_layers: Number of stacked LSTM layers (default: 2).
        dropout: LSTM inter-layer dropout (default: 0.2).
    """

    def __init__(
        self,
        input_size: int = 10,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )

        self.attention = Attention(hidden_size)

        self.fc1 = nn.Linear(hidden_size, 32)
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(32, 2)

        # Separate head for confidence
        self.confidence_head = nn.Linear(32, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: (batch, seq_len, input_size)

        Returns:
            direction_probs: (batch, 2) — softmax probabilities [P(short), P(long)]
            confidence: (batch, 1) — sigmoid confidence score
        """
        lstm_out, _ = self.lstm(x)  # (batch, seq, hidden)
        context = self.attention(lstm_out)  # (batch, hidden)

        h = F.relu(self.fc1(context))  # (batch, 32)
        h = self.dropout(h)

        direction_logits = self.fc2(h)  # (batch, 2)
        direction_probs = F.softmax(direction_logits, dim=1)

        confidence = torch.sigmoid(self.confidence_head(h))  # (batch, 1)

        return direction_probs, confidence
