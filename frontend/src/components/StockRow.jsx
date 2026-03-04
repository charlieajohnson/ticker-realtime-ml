import Sparkline from "./Sparkline";
import ConfidenceBar from "./ConfidenceBar";
import { IconTrendUp, IconTrendDown, IconZap } from "./Icons";

function formatVolume(v) {
  if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
  return (v / 1e3).toFixed(0) + "K";
}

export default function StockRow({ stock, index }) {
  const { symbol, price, change, volume, sparkline, prediction, confidence } = stock;
  const isUp = change >= 0;

  const confColor =
    confidence > 0.8 ? "var(--cyan)" : confidence > 0.65 ? "var(--amber)" : "var(--text-3)";

  return (
    <tr className="stock-row" style={{ animationDelay: `${index * 0.05}s` }}>
      <td>
        <div className="symbol-cell">
          <div className="symbol-dot" style={{ background: isUp ? "var(--green)" : "var(--red)" }} />
          {symbol}
        </div>
      </td>
      <td className="price-cell">${price.toFixed(2)}</td>
      <td>
        <span className={`change-cell ${isUp ? "up" : "down"}`}>
          {isUp ? <IconTrendUp /> : <IconTrendDown />}
          {isUp ? "+" : ""}{change.toFixed(2)}%
        </span>
      </td>
      <td className="volume-cell">{formatVolume(volume)}</td>
      <td style={{ textAlign: "center" }}>
        <Sparkline data={sparkline} width={100} height={28} color={isUp ? "#34D399" : "#F87171"} />
      </td>
      <td>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <ConfidenceBar value={confidence} color={confColor} />
          <span style={{ fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-2)" }}>
            {(confidence * 100).toFixed(0)}%
          </span>
        </div>
      </td>
      <td className="prediction-cell">
        {prediction && (
          <span className={`prediction-badge ${prediction}`}>
            <IconZap />
            {prediction}
          </span>
        )}
      </td>
    </tr>
  );
}
