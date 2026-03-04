import { useState, useEffect, useRef, useCallback } from "react";
import TopBar from "./components/TopBar";
import PipelineStrip from "./components/PipelineStrip";
import StockTable from "./components/StockTable";
import ModelCard from "./components/ModelCard";
import AlertFeed from "./components/AlertFeed";
import BottomBar from "./components/BottomBar";
import { createWebSocket } from "./ws";
import { fetchSymbols, fetchModelStats, fetchAlerts, fetchPipelineStatus } from "./api";

const DEFAULT_PIPELINE = {
  stages: [
    { name: "ingest", status: "idle", throughput: 0, latency_ms: 0 },
    { name: "transform", status: "idle", throughput: 0, latency_ms: 0 },
    { name: "feature", status: "idle", throughput: 0, latency_ms: 0 },
    { name: "inference", status: "idle", throughput: 0, latency_ms: 0 },
    { name: "serve", status: "idle", throughput: 0, latency_ms: 0 },
  ],
  uptime: null,
  total_ticks: 0,
};

export default function App() {
  const [stocks, setStocks] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [modelStats, setModelStats] = useState({});
  const [pipeline, setPipeline] = useState(DEFAULT_PIPELINE);
  const [wsStatus, setWsStatus] = useState("disconnected");
  const [time, setTime] = useState(new Date());
  const wsRef = useRef(null);

  // ── Clock ──
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  // ── WebSocket message handler ──
  const handleMessage = useCallback((msg) => {
    switch (msg.type) {
      case "tick":
        setStocks((prev) => {
          const idx = prev.findIndex((s) => s.symbol === msg.symbol);
          if (idx === -1) {
            // New symbol
            return [
              ...prev,
              {
                symbol: msg.symbol,
                price: msg.price,
                change: msg.change ?? 0,
                volume: msg.volume ?? 0,
                sparkline: msg.sparkline ?? [msg.price],
                prediction: null,
                confidence: 0,
              },
            ];
          }
          const updated = [...prev];
          updated[idx] = {
            ...updated[idx],
            price: msg.price,
            change: msg.change ?? updated[idx].change,
            volume: msg.volume ?? updated[idx].volume,
            sparkline: msg.sparkline ?? updated[idx].sparkline,
          };
          return updated;
        });
        break;

      case "prediction":
        setStocks((prev) => {
          const idx = prev.findIndex((s) => s.symbol === msg.symbol);
          if (idx === -1) return prev;
          const updated = [...prev];
          updated[idx] = {
            ...updated[idx],
            prediction: msg.direction,
            confidence: msg.confidence,
          };
          return updated;
        });
        break;

      case "alert":
        setAlerts((prev) => [
          {
            id: Date.now(),
            type: msg.alert_type,
            message: msg.message,
            symbol: msg.symbol,
            time: msg.timestamp
              ? new Date(msg.timestamp).toLocaleTimeString("en-US", { hour12: false })
              : new Date().toLocaleTimeString("en-US", { hour12: false }),
          },
          ...prev.slice(0, 99),
        ]);
        break;

      case "pipeline_status":
        setPipeline((prev) => ({
          ...prev,
          stages: msg.stages,
        }));
        break;
    }
  }, []);

  // ── Initial REST fetch + WebSocket connect ──
  useEffect(() => {
    // Fetch initial data from REST endpoints
    fetchSymbols()
      .then((data) => {
        if (data.symbols) {
          setStocks(
            data.symbols.map((s) => ({
              symbol: s.symbol,
              price: s.price ?? 0,
              change: s.change ?? 0,
              volume: s.volume ?? 0,
              sparkline: s.sparkline ?? [],
              prediction: s.prediction?.direction ?? null,
              confidence: s.prediction?.confidence ?? 0,
            }))
          );
        }
      })
      .catch(() => {});

    fetchModelStats()
      .then((data) => setModelStats(data))
      .catch(() => {});

    fetchAlerts()
      .then((data) => {
        if (data.alerts) {
          setAlerts(
            data.alerts.map((a) => ({
              id: a.id,
              type: a.type,
              message: a.message,
              symbol: a.symbol,
              time: a.created_at
                ? new Date(a.created_at).toLocaleTimeString("en-US", { hour12: false })
                : "",
            }))
          );
        }
      })
      .catch(() => {});

    fetchPipelineStatus()
      .then((data) => setPipeline(data))
      .catch(() => {});

    // Connect WebSocket
    const ws = createWebSocket({
      onMessage: handleMessage,
      onStatusChange: setWsStatus,
    });
    wsRef.current = ws;
    ws.connect();

    return () => ws.close();
  }, [handleMessage]);

  const clockStr = time.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <div className="dashboard">
      <TopBar
        tickCount={pipeline.total_ticks ?? 0}
        symbolCount={stocks.length}
        clock={clockStr}
      />

      <div className="main-panel">
        <PipelineStrip stages={pipeline.stages ?? DEFAULT_PIPELINE.stages} />
        <StockTable stocks={stocks} />
      </div>

      <div className="right-panel">
        <ModelCard stats={modelStats} />
        <AlertFeed alerts={alerts} />
      </div>

      <BottomBar
        pipeline={pipeline}
        modelVersion={modelStats.name}
        uptime={pipeline.uptime}
        wsStatus={wsStatus}
      />
    </div>
  );
}
