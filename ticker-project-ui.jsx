import { useState, useEffect, useRef, useCallback } from "react";

// ── Mock Data ──────────────────────────────────────────────────────────────────
const SYMBOLS = ["AAPL", "GOOGL", "MSFT", "AMZN", "NVDA", "TSLA", "META", "JPM"];

function generatePrice(base) {
  return base + (Math.random() - 0.48) * base * 0.003;
}

function generateSparkline(length = 40, base = 100) {
  const pts = [base];
  for (let i = 1; i < length; i++) pts.push(generatePrice(pts[i - 1]));
  return pts;
}

const BASES = { AAPL: 189.2, GOOGL: 174.8, MSFT: 420.1, AMZN: 186.5, NVDA: 875.3, TSLA: 175.6, META: 505.2, JPM: 198.7 };

function initStocks() {
  return SYMBOLS.map((s) => {
    const spark = generateSparkline(40, BASES[s]);
    const price = spark[spark.length - 1];
    const open = spark[0];
    const change = ((price - open) / open) * 100;
    return {
      symbol: s,
      price,
      change,
      volume: Math.floor(Math.random() * 50 + 10) * 100000,
      sparkline: spark,
      prediction: Math.random() > 0.5 ? "LONG" : "SHORT",
      confidence: 0.6 + Math.random() * 0.35,
      signal_strength: Math.random(),
    };
  });
}

const MOCK_ALERTS = [
  { id: 1, time: "14:32:08", type: "signal", message: "NVDA momentum breakout detected — confidence 0.91", symbol: "NVDA" },
  { id: 2, time: "14:31:45", type: "anomaly", message: "TSLA volume spike 3.2σ above rolling mean", symbol: "TSLA" },
  { id: 3, time: "14:30:12", type: "signal", message: "AAPL mean-reversion signal triggered", symbol: "AAPL" },
  { id: 4, time: "14:28:55", type: "info", message: "Model retrained on latest 500 ticks — loss: 0.0034", symbol: null },
  { id: 5, time: "14:27:30", type: "signal", message: "MSFT bearish divergence on RSI — SHORT signal", symbol: "MSFT" },
];

const PIPELINE_STAGES = [
  { name: "Ingest", status: "active", throughput: "1.2k msgs/s", latency: "3ms" },
  { name: "Transform", status: "active", throughput: "1.2k msgs/s", latency: "8ms" },
  { name: "Feature Eng", status: "active", throughput: "850 feat/s", latency: "12ms" },
  { name: "Inference", status: "active", throughput: "200 pred/s", latency: "45ms" },
  { name: "Serve", status: "active", throughput: "180 req/s", latency: "5ms" },
];

const MODEL_STATS = {
  name: "TickerNet v0.3",
  architecture: "LSTM + Attention",
  parameters: "1.2M",
  last_trained: "2h ago",
  accuracy_1h: "67.3%",
  sharpe: "1.84",
  max_drawdown: "-4.2%",
  predictions_today: 2847,
};

// ── SVG Icons ──────────────────────────────────────────────────────────────────
const IconActivity = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
  </svg>
);
const IconTrendUp = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" /><polyline points="17 6 23 6 23 12" />
  </svg>
);
const IconTrendDown = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 18 13.5 8.5 8.5 13.5 1 6" /><polyline points="17 18 23 18 23 12" />
  </svg>
);
const IconZap = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>
);
const IconCpu = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="4" y="4" width="16" height="16" rx="2" /><rect x="9" y="9" width="6" height="6" /><line x1="9" y1="1" x2="9" y2="4" /><line x1="15" y1="1" x2="15" y2="4" /><line x1="9" y1="20" x2="9" y2="23" /><line x1="15" y1="20" x2="15" y2="23" /><line x1="20" y1="9" x2="23" y2="9" /><line x1="20" y1="14" x2="23" y2="14" /><line x1="1" y1="9" x2="4" y2="9" /><line x1="1" y1="14" x2="4" y2="14" />
  </svg>
);
const IconRadio = () => (
  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="2" /><path d="M16.24 7.76a6 6 0 0 1 0 8.49" /><path d="M7.76 16.24a6 6 0 0 1 0-8.49" />
  </svg>
);

// ── Sparkline Component ────────────────────────────────────────────────────────
function Sparkline({ data, width = 120, height = 32, color }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");

  const gradientId = `sg-${Math.random().toString(36).slice(2, 8)}`;
  const areaPath =
    `M0,${height} ` +
    data
      .map((v, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((v - min) / range) * (height - 4) - 2;
        return `L${x},${y}`;
      })
      .join(" ") +
    ` L${width},${height} Z`;

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.15" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradientId})`} />
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ── Confidence Bar ─────────────────────────────────────────────────────────────
function ConfidenceBar({ value, color }) {
  return (
    <div style={{ width: 48, height: 3, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden" }}>
      <div
        style={{
          width: `${value * 100}%`,
          height: "100%",
          background: color,
          borderRadius: 2,
          transition: "width 0.6s ease",
        }}
      />
    </div>
  );
}

// ── Pipeline Node ──────────────────────────────────────────────────────────────
function PipelineNode({ stage, index, total }) {
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
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: 2,
            background: "var(--cyan)",
            opacity: 0.6,
            animation: "scanline 2s linear infinite",
            animationDelay: `${index * 0.3}s`,
          }}
        />
        <div style={{ fontSize: 11, color: "var(--text-2)", fontFamily: "var(--mono)", marginBottom: 4 }}>{stage.name}</div>
        <div style={{ fontSize: 10, color: "var(--text-3)", fontFamily: "var(--mono)" }}>{stage.throughput}</div>
        <div style={{ fontSize: 10, color: "var(--text-3)", fontFamily: "var(--mono)" }}>p50: {stage.latency}</div>
      </div>
      {index < total - 1 && (
        <div style={{ display: "flex", alignItems: "center", padding: "0 2px" }}>
          <div style={{ width: 20, height: 1, background: "var(--border)" }} />
          <div
            style={{
              width: 0,
              height: 0,
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

// ── Styles ─────────────────────────────────────────────────────────────────────
const css = `
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

  @keyframes scanline {
    0% { transform: translateX(-100%); opacity: 0; }
    20% { opacity: 0.8; }
    100% { transform: translateX(200%); opacity: 0; }
  }
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes slideUp {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes slideRight {
    from { opacity: 0; transform: translateX(-12px); }
    to { opacity: 1; transform: translateX(0); }
  }
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }
  @keyframes pulse-ring {
    0% { box-shadow: 0 0 0 0 rgba(0, 220, 200, 0.3); }
    70% { box-shadow: 0 0 0 6px rgba(0, 220, 200, 0); }
    100% { box-shadow: 0 0 0 0 rgba(0, 220, 200, 0); }
  }
  @keyframes number-flash {
    0% { color: var(--text-1); }
    15% { color: var(--cyan); }
    100% { color: var(--text-1); }
  }
  @keyframes grain {
    0%, 100% { transform: translate(0, 0); }
    10% { transform: translate(-2%, -2%); }
    30% { transform: translate(1%, -1%); }
    50% { transform: translate(-1%, 2%); }
    70% { transform: translate(2%, 1%); }
    90% { transform: translate(-1%, -1%); }
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  :root {
    --bg-0: #07090D;
    --bg-1: #0B0E14;
    --surface-0: #0F1318;
    --surface-1: #141820;
    --surface-2: #1A1F2A;
    --border: #1E2430;
    --border-bright: #2A3140;
    --text-1: #CBD5E1;
    --text-2: #7A8BA0;
    --text-3: #4A5568;
    --cyan: #00DCC8;
    --cyan-dim: rgba(0, 220, 200, 0.12);
    --cyan-glow: rgba(0, 220, 200, 0.05);
    --green: #34D399;
    --green-dim: rgba(52, 211, 153, 0.10);
    --red: #F87171;
    --red-dim: rgba(248, 113, 113, 0.10);
    --amber: #FBBF24;
    --amber-dim: rgba(251, 191, 36, 0.10);
    --blue: #60A5FA;
    --mono: 'IBM Plex Mono', monospace;
    --sans: 'Outfit', -apple-system, sans-serif;
  }

  body {
    background: var(--bg-0);
    color: var(--text-1);
    font-family: var(--sans);
    font-size: 13px;
    -webkit-font-smoothing: antialiased;
  }

  .dashboard {
    display: grid;
    grid-template-columns: 1fr 320px;
    grid-template-rows: auto 1fr auto;
    height: 100vh;
    overflow: hidden;
    position: relative;
  }

  /* Grain overlay */
  .dashboard::before {
    content: '';
    position: fixed;
    top: -50%;
    left: -50%;
    right: -50%;
    bottom: -50%;
    width: 200%;
    height: 200%;
    background: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
    opacity: 0.025;
    pointer-events: none;
    z-index: 100;
    animation: grain 4s steps(8) infinite;
  }

  /* ─── Top Bar ─── */
  .topbar {
    grid-column: 1 / -1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 24px;
    background: var(--bg-1);
    border-bottom: 1px solid var(--border);
    z-index: 10;
  }

  .topbar-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .logo-mark {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--sans);
    font-weight: 600;
    font-size: 16px;
    letter-spacing: -0.03em;
    color: var(--text-1);
  }

  .logo-icon {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    background: linear-gradient(135deg, rgba(0,220,200,0.15), rgba(0,220,200,0.05));
    border: 1px solid rgba(0,220,200,0.2);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--cyan);
  }

  .divider-v {
    width: 1px;
    height: 20px;
    background: var(--border);
  }

  .status-live {
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--cyan);
  }

  .live-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--cyan);
    animation: pulse-ring 2s ease infinite;
  }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .topbar-stat {
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-3);
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .topbar-stat span { color: var(--text-2); }

  .clock {
    font-family: var(--mono);
    font-size: 12px;
    font-weight: 500;
    color: var(--text-2);
    letter-spacing: 0.05em;
    min-width: 72px;
    text-align: right;
  }

  /* ─── Main Panel ─── */
  .main-panel {
    grid-column: 1;
    grid-row: 2;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--bg-0);
  }

  .pipeline-strip {
    display: flex;
    align-items: center;
    gap: 0;
    padding: 16px 24px;
    background: var(--bg-1);
    border-bottom: 1px solid var(--border);
    overflow-x: auto;
  }

  .pipeline-strip::-webkit-scrollbar { height: 0; }

  .section-label {
    font-family: var(--mono);
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-3);
    padding: 16px 24px 8px;
  }

  /* ─── Table ─── */
  .table-container {
    flex: 1;
    overflow-y: auto;
    padding: 0 24px 24px;
  }

  .table-container::-webkit-scrollbar { width: 3px; }
  .table-container::-webkit-scrollbar-track { background: transparent; }
  .table-container::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .stock-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
  }

  .stock-table th {
    font-family: var(--mono);
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-3);
    text-align: left;
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    background: var(--bg-0);
    z-index: 2;
  }
  .stock-table th:last-child { text-align: right; }

  .stock-row {
    cursor: pointer;
    transition: background 0.12s;
    animation: slideUp 0.3s ease both;
  }
  .stock-row:hover { background: var(--surface-0); }

  .stock-row td {
    padding: 12px 12px;
    border-bottom: 1px solid var(--border);
    font-family: var(--mono);
    font-size: 13px;
    vertical-align: middle;
  }

  .symbol-cell {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 500;
    color: var(--text-1);
  }

  .symbol-dot {
    width: 4px;
    height: 16px;
    border-radius: 2px;
  }

  .price-cell {
    font-weight: 500;
    color: var(--text-1);
    font-variant-numeric: tabular-nums;
  }

  .change-cell {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 12px;
    font-weight: 500;
    padding: 2px 8px;
    border-radius: 4px;
  }
  .change-cell.up { color: var(--green); background: var(--green-dim); }
  .change-cell.down { color: var(--red); background: var(--red-dim); }

  .volume-cell {
    color: var(--text-2);
    font-size: 12px;
  }

  .prediction-cell {
    text-align: right;
  }

  .prediction-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 10px;
    font-weight: 500;
    font-family: var(--mono);
    letter-spacing: 0.06em;
    padding: 3px 10px;
    border-radius: 4px;
  }
  .prediction-badge.LONG { color: var(--green); background: var(--green-dim); }
  .prediction-badge.SHORT { color: var(--red); background: var(--red-dim); }

  /* ─── Right Sidebar ─── */
  .right-panel {
    grid-column: 2;
    grid-row: 2 / 4;
    background: var(--bg-1);
    border-left: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .model-card {
    padding: 20px;
    border-bottom: 1px solid var(--border);
  }

  .model-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
  }

  .model-name {
    font-family: var(--mono);
    font-size: 13px;
    font-weight: 500;
    color: var(--cyan);
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .model-arch {
    font-family: var(--mono);
    font-size: 10px;
    color: var(--text-3);
    background: var(--surface-1);
    padding: 3px 8px;
    border-radius: 4px;
    border: 1px solid var(--border);
  }

  .model-stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .model-stat {
    background: var(--surface-0);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 12px;
  }

  .model-stat-label {
    font-family: var(--mono);
    font-size: 9px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-3);
    margin-bottom: 4px;
  }

  .model-stat-value {
    font-family: var(--mono);
    font-size: 15px;
    font-weight: 500;
    color: var(--text-1);
  }
  .model-stat-value.positive { color: var(--green); }
  .model-stat-value.negative { color: var(--red); }
  .model-stat-value.highlight { color: var(--cyan); }

  /* ─── Alerts Feed ─── */
  .alerts-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .alerts-list {
    flex: 1;
    overflow-y: auto;
    padding: 0 12px 12px;
  }

  .alerts-list::-webkit-scrollbar { width: 3px; }
  .alerts-list::-webkit-scrollbar-track { background: transparent; }
  .alerts-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .alert-item {
    padding: 10px 12px;
    border-radius: 6px;
    margin-bottom: 4px;
    cursor: pointer;
    transition: background 0.12s;
    animation: slideRight 0.3s ease both;
    border-left: 2px solid transparent;
  }
  .alert-item:hover { background: var(--surface-1); }
  .alert-item.signal { border-left-color: var(--cyan); }
  .alert-item.anomaly { border-left-color: var(--amber); }
  .alert-item.info { border-left-color: var(--text-3); }

  .alert-time {
    font-family: var(--mono);
    font-size: 10px;
    color: var(--text-3);
    margin-bottom: 3px;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .alert-type-tag {
    font-size: 9px;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 1px 5px;
    border-radius: 3px;
  }
  .alert-type-tag.signal { color: var(--cyan); background: var(--cyan-dim); }
  .alert-type-tag.anomaly { color: var(--amber); background: var(--amber-dim); }
  .alert-type-tag.info { color: var(--text-3); background: var(--surface-2); }

  .alert-message {
    font-size: 12px;
    color: var(--text-2);
    line-height: 1.45;
  }

  .alert-symbol {
    font-family: var(--mono);
    font-weight: 500;
    color: var(--text-1);
  }

  /* ─── Bottom Bar ─── */
  .bottom-bar {
    grid-column: 1;
    grid-row: 3;
    display: flex;
    align-items: center;
    gap: 24px;
    padding: 10px 24px;
    background: var(--bg-1);
    border-top: 1px solid var(--border);
    font-family: var(--mono);
    font-size: 10px;
    color: var(--text-3);
  }

  .bottom-stat {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .bottom-stat .val { color: var(--text-2); }
  .bottom-stat .good { color: var(--green); }
`;

// ── Main Component ─────────────────────────────────────────────────────────────
export default function App() {
  const [stocks, setStocks] = useState(initStocks);
  const [alerts, setAlerts] = useState(MOCK_ALERTS);
  const [time, setTime] = useState(new Date());
  const [tickCount, setTickCount] = useState(48203);

  // Simulate live updates
  useEffect(() => {
    const interval = setInterval(() => {
      setTime(new Date());
      setTickCount((c) => c + Math.floor(Math.random() * 5 + 1));

      setStocks((prev) =>
        prev.map((s) => {
          const newPrice = generatePrice(s.price);
          const newSpark = [...s.sparkline.slice(1), newPrice];
          const open = s.sparkline[0];
          const change = ((newPrice - open) / open) * 100;
          return {
            ...s,
            price: newPrice,
            change,
            sparkline: newSpark,
            volume: s.volume + Math.floor(Math.random() * 5000),
            confidence: Math.min(0.99, Math.max(0.55, s.confidence + (Math.random() - 0.5) * 0.02)),
            signal_strength: Math.min(1, Math.max(0, s.signal_strength + (Math.random() - 0.5) * 0.05)),
          };
        })
      );
    }, 1500);
    return () => clearInterval(interval);
  }, []);

  const formatVol = (v) => {
    if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
    return (v / 1e3).toFixed(0) + "K";
  };

  const clockStr = time.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });

  return (
    <>
      <style>{css}</style>
      <div className="dashboard">
        {/* ── Top Bar ── */}
        <div className="topbar">
          <div className="topbar-left">
            <div className="logo-mark">
              <div className="logo-icon"><IconActivity /></div>
              Ticker
            </div>
            <div className="divider-v" />
            <div className="status-live">
              <div className="live-dot" />
              LIVE
            </div>
          </div>
          <div className="topbar-right">
            <div className="topbar-stat">
              ticks <span>{tickCount.toLocaleString()}</span>
            </div>
            <div className="topbar-stat">
              symbols <span>{SYMBOLS.length}</span>
            </div>
            <div className="divider-v" />
            <div className="clock">{clockStr}</div>
          </div>
        </div>

        {/* ── Main Panel ── */}
        <div className="main-panel">
          <div className="pipeline-strip">
            {PIPELINE_STAGES.map((stage, i) => (
              <PipelineNode key={stage.name} stage={stage} index={i} total={PIPELINE_STAGES.length} />
            ))}
          </div>

          <div className="section-label">Live Positions · Predictions</div>

          <div className="table-container">
            <table className="stock-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Price</th>
                  <th>Change</th>
                  <th>Volume</th>
                  <th style={{ textAlign: "center" }}>Trend</th>
                  <th>Confidence</th>
                  <th style={{ textAlign: "right" }}>Signal</th>
                </tr>
              </thead>
              <tbody>
                {stocks.map((s, i) => (
                  <tr className="stock-row" key={s.symbol} style={{ animationDelay: `${i * 0.05}s` }}>
                    <td>
                      <div className="symbol-cell">
                        <div
                          className="symbol-dot"
                          style={{ background: s.change >= 0 ? "var(--green)" : "var(--red)" }}
                        />
                        {s.symbol}
                      </div>
                    </td>
                    <td className="price-cell">${s.price.toFixed(2)}</td>
                    <td>
                      <span className={`change-cell ${s.change >= 0 ? "up" : "down"}`}>
                        {s.change >= 0 ? <IconTrendUp /> : <IconTrendDown />}
                        {s.change >= 0 ? "+" : ""}
                        {s.change.toFixed(2)}%
                      </span>
                    </td>
                    <td className="volume-cell">{formatVol(s.volume)}</td>
                    <td style={{ textAlign: "center" }}>
                      <Sparkline
                        data={s.sparkline}
                        width={100}
                        height={28}
                        color={s.change >= 0 ? "#34D399" : "#F87171"}
                      />
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <ConfidenceBar
                          value={s.confidence}
                          color={s.confidence > 0.8 ? "var(--cyan)" : s.confidence > 0.65 ? "var(--amber)" : "var(--text-3)"}
                        />
                        <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-2)" }}>
                          {(s.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="prediction-cell">
                      <span className={`prediction-badge ${s.prediction}`}>
                        <IconZap />
                        {s.prediction}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Right Sidebar ── */}
        <div className="right-panel">
          <div className="model-card">
            <div className="model-header">
              <div className="model-name">
                <IconCpu />
                {MODEL_STATS.name}
              </div>
              <div className="model-arch">{MODEL_STATS.architecture}</div>
            </div>
            <div className="model-stats-grid">
              <div className="model-stat">
                <div className="model-stat-label">Accuracy (1h)</div>
                <div className="model-stat-value highlight">{MODEL_STATS.accuracy_1h}</div>
              </div>
              <div className="model-stat">
                <div className="model-stat-label">Sharpe</div>
                <div className="model-stat-value positive">{MODEL_STATS.sharpe}</div>
              </div>
              <div className="model-stat">
                <div className="model-stat-label">Max Drawdown</div>
                <div className="model-stat-value negative">{MODEL_STATS.max_drawdown}</div>
              </div>
              <div className="model-stat">
                <div className="model-stat-label">Predictions</div>
                <div className="model-stat-value">{MODEL_STATS.predictions_today.toLocaleString()}</div>
              </div>
              <div className="model-stat">
                <div className="model-stat-label">Parameters</div>
                <div className="model-stat-value">{MODEL_STATS.parameters}</div>
              </div>
              <div className="model-stat">
                <div className="model-stat-label">Last Trained</div>
                <div className="model-stat-value">{MODEL_STATS.last_trained}</div>
              </div>
            </div>
          </div>

          <div className="alerts-section">
            <div className="section-label" style={{ padding: "16px 20px 8px" }}>Signal Feed</div>
            <div className="alerts-list">
              {alerts.map((a, i) => (
                <div
                  className={`alert-item ${a.type}`}
                  key={a.id}
                  style={{ animationDelay: `${i * 0.08}s` }}
                >
                  <div className="alert-time">
                    {a.time}
                    <span className={`alert-type-tag ${a.type}`}>{a.type}</span>
                  </div>
                  <div className="alert-message">{a.message}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Bottom Bar ── */}
        <div className="bottom-bar">
          <div className="bottom-stat">
            pipeline <span className="good">healthy</span>
          </div>
          <div className="bottom-stat">
            latency (e2e) <span className="val">73ms</span>
          </div>
          <div className="bottom-stat">
            model <span className="val">TickerNet v0.3</span>
          </div>
          <div className="bottom-stat">
            uptime <span className="val">99.97%</span>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 4, color: "var(--text-3)" }}>
            <IconRadio /> WebSocket connected
          </div>
        </div>
      </div>
    </>
  );
}
