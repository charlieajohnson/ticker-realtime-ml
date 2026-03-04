function PipelineNode({ stage, index, total }) {
  const throughputStr = stage.throughput != null ? `${stage.throughput}` : "—";
  const latencyStr = stage.latency_ms != null ? `p50: ${stage.latency_ms}ms` : "p50: —";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0 }}>
      <div
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border)",
          borderRadius: 6,
          padding: "10px 14px",
          minWidth: 110,
          position: "relative",
          overflow: "hidden",
          opacity: stage.status === "idle" ? 0.5 : 1,
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 0, left: 0, width: "100%", height: 2,
            background: "var(--cyan)",
            opacity: stage.status === "active" ? 0.6 : 0,
            animation: stage.status === "active" ? "scanline 2s linear infinite" : "none",
            animationDelay: `${index * 0.3}s`,
          }}
        />
        <div style={{ fontSize: 11, color: "var(--text-2)", fontFamily: "var(--mono)", marginBottom: 4 }}>
          {stage.name}
        </div>
        <div style={{ fontSize: 10, color: "var(--text-3)", fontFamily: "var(--mono)" }}>
          {throughputStr}
        </div>
        <div style={{ fontSize: 10, color: "var(--text-3)", fontFamily: "var(--mono)" }}>
          {latencyStr}
        </div>
      </div>
      {index < total - 1 && (
        <div style={{ display: "flex", alignItems: "center", padding: "0 2px" }}>
          <div style={{ width: 20, height: 1, background: "var(--border)" }} />
          <div
            style={{
              width: 0, height: 0,
              borderTop: "4px solid transparent",
              borderBottom: "4px solid transparent",
              borderLeft: "5px solid var(--border)",
            }}
          />
        </div>
      )}
    </div>
  );
}

const STAGE_LABELS = {
  ingest: "Ingest",
  transform: "Transform",
  feature: "Feature Eng",
  inference: "Inference",
  serve: "Serve",
};

export default function PipelineStrip({ stages }) {
  const displayStages = stages.map((s) => ({
    ...s,
    name: STAGE_LABELS[s.name] || s.name,
  }));

  return (
    <div className="pipeline-strip">
      {displayStages.map((stage, i) => (
        <PipelineNode key={stage.name} stage={stage} index={i} total={displayStages.length} />
      ))}
    </div>
  );
}
