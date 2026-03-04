import { IconRadio } from "./Icons";

export default function BottomBar({ pipeline, modelVersion, uptime, wsStatus }) {
  // Compute e2e latency as sum of stage latencies
  const e2eLatency = pipeline.stages
    ? pipeline.stages.reduce((sum, s) => sum + (s.latency_ms || 0), 0)
    : 0;

  const allActive = pipeline.stages?.every((s) => s.status === "active");

  return (
    <div className="bottom-bar">
      <div className="bottom-stat">
        pipeline{" "}
        <span className={allActive ? "good" : "val"}>
          {allActive ? "healthy" : "degraded"}
        </span>
      </div>
      <div className="bottom-stat">
        latency (e2e) <span className="val">{Math.round(e2eLatency)}ms</span>
      </div>
      <div className="bottom-stat">
        model <span className="val">{modelVersion || "—"}</span>
      </div>
      <div className="bottom-stat">
        uptime{" "}
        <span className="val">
          {uptime != null ? `${(uptime * 100).toFixed(2)}%` : "—"}
        </span>
      </div>
      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4, color: "var(--text-3)" }}>
        <IconRadio />{" "}
        {wsStatus === "connected" ? "WebSocket connected" : wsStatus === "reconnecting" ? "Reconnecting..." : "Disconnected"}
      </div>
    </div>
  );
}
