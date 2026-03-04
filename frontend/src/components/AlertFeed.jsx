import AlertItem from "./AlertItem";

export default function AlertFeed({ alerts }) {
  return (
    <div className="alerts-section">
      <div className="section-label" style={{ padding: "16px 20px 8px" }}>Signal Feed</div>
      <div className="alerts-list">
        {alerts.map((a, i) => (
          <AlertItem key={a.id} alert={a} index={i} />
        ))}
      </div>
    </div>
  );
}
