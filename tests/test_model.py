"""Tests for TickerNet model."""

import tempfile
from pathlib import Path

import numpy as np
import torch
import pytest

from backend.models.tickernet import TickerNet, Attention
from backend.pipeline.inference import InferenceService, store_prediction


# ── Attention ──


class TestAttention:
    def test_output_shape(self):
        attn = Attention(hidden_size=64)
        x = torch.randn(4, 20, 64)  # batch=4, seq=20, hidden=64
        out = attn(x)
        assert out.shape == (4, 64)

    def test_attention_weights_sum_to_one(self):
        attn = Attention(hidden_size=32)
        x = torch.randn(2, 10, 32)
        energy = torch.tanh(attn.attn(x))
        scores = attn.v(energy).squeeze(-1)
        weights = torch.softmax(scores, dim=1)
        sums = weights.sum(dim=1)
        assert torch.allclose(sums, torch.ones(2), atol=1e-5)


# ── TickerNet ──


class TestTickerNet:
    def test_forward_shapes(self):
        model = TickerNet(input_size=10, hidden_size=64, num_layers=2)
        x = torch.randn(8, 30, 10)  # batch=8, seq=30, features=10
        dir_probs, confidence = model(x)
        assert dir_probs.shape == (8, 2)
        assert confidence.shape == (8, 1)

    def test_direction_probs_sum_to_one(self):
        model = TickerNet()
        x = torch.randn(4, 20, 10)
        dir_probs, _ = model(x)
        sums = dir_probs.sum(dim=1)
        assert torch.allclose(sums, torch.ones(4), atol=1e-5)

    def test_confidence_in_0_1(self):
        model = TickerNet()
        x = torch.randn(4, 20, 10)
        _, confidence = model(x)
        assert (confidence >= 0).all()
        assert (confidence <= 1).all()

    def test_parameter_count(self):
        model = TickerNet()
        count = sum(p.numel() for p in model.parameters())
        # Should be ~59K params
        assert 50_000 < count < 70_000

    def test_batch_size_one(self):
        model = TickerNet()
        x = torch.randn(1, 15, 10)
        dir_probs, confidence = model(x)
        assert dir_probs.shape == (1, 2)
        assert confidence.shape == (1, 1)

    def test_eval_mode_deterministic(self):
        model = TickerNet()
        model.eval()
        x = torch.randn(2, 20, 10)
        with torch.no_grad():
            out1 = model(x)
            out2 = model(x)
        assert torch.allclose(out1[0], out2[0])
        assert torch.allclose(out1[1], out2[1])


# ── InferenceService ──


class TestInferenceService:
    def test_not_ready_without_checkpoint(self):
        svc = InferenceService(checkpoint_path=Path("/nonexistent/model.pt"))
        assert not svc.is_ready
        assert svc.predict(np.zeros((20, 10))) is None

    def test_load_and_predict(self, tmp_path):
        # Create a dummy checkpoint
        model = TickerNet()
        ckpt_path = tmp_path / "test_model.pt"
        torch.save({
            "model_state_dict": model.state_dict(),
            "model_version": "test-v1",
            "val_loss": 0.5,
            "accuracy": 0.65,
        }, ckpt_path)

        svc = InferenceService(checkpoint_path=ckpt_path)
        assert svc.is_ready

        vec = np.random.randn(20, 10).astype(np.float32)
        result = svc.predict(vec)
        assert result is not None
        assert result["direction"] in ("LONG", "SHORT")
        assert 0 <= result["confidence"] <= 1
        assert result["model_version"] == "test-v1"


# ── store_prediction ──


class TestStorePrediction:
    def test_store_and_retrieve(self, db):
        pred = {"direction": "LONG", "confidence": 0.87, "model_version": "v0.1"}
        pred_id = store_prediction("AAPL", pred, price_at=150.0)

        row = db.execute("SELECT * FROM predictions WHERE id = ?", [pred_id]).fetchone()
        assert row is not None
        assert row[2] == "LONG"  # direction
        assert row[3] == pytest.approx(0.87)  # confidence
