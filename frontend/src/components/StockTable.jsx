import StockRow from "./StockRow";

export default function StockTable({ stocks }) {
  return (
    <>
      <div className="section-label">Live Positions &middot; Predictions</div>
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
              <StockRow key={s.symbol} stock={s} index={i} />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
