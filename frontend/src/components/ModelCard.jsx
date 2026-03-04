import { IconCpu } from "./Icons";

export default function ModelCard({ stats }) {
  return (
    <div className="model-card">
      <div className="model-header">
        <div className="model-name">
          <IconCpu />
          {stats.name || "TickerNet"}
        </div>
        <div className="model-arch">{stats.architecture || "LSTM + Attention"}</div>
      </div>
      <div className="model-stats-grid">
        <div className="model-stat">
          <div className="model-stat-label">Accuracy (1h)</div>
          <div className="model-stat-value highlight">
            {stats.accuracy_1h != null ? `${stats.accuracy_1h}%` : "—"}
          </div>
        </div>
        <div className="model-stat">
          <div className="model-stat-label">Sharpe</div>
          <div className="model-stat-value positive">{stats.sharpe ?? "—"}</div>
        </div>
        <div className="model-stat">
          <div className="model-stat-label">Max Drawdown</div>
          <div className="model-stat-value negative">{stats.max_drawdown ?? "—"}</div>
        </div>
        <div className="model-stat">
          <div className="model-stat-label">Predictions</div>
          <div className="model-stat-value">
            {stats.predictions_today != null ? stats.predictions_today.toLocaleString() : "—"}
          </div>
        </div>
        <div className="model-stat">
          <div className="model-stat-label">Parameters</div>
          <div className="model-stat-value">{stats.parameters || "—"}</div>
        </div>
        <div className="model-stat">
          <div className="model-stat-label">Last Trained</div>
          <div className="model-stat-value">{stats.last_trained || "—"}</div>
        </div>
      </div>
    </div>
  );
}
