export default function AlertItem({ alert, index }) {
  const time = alert.created_at
    ? new Date(alert.created_at).toLocaleTimeString("en-US", { hour12: false })
    : alert.time || "";

  return (
    <div
      className={`alert-item ${alert.type}`}
      style={{ animationDelay: `${index * 0.08}s` }}
    >
      <div className="alert-time">
        {time}
        <span className={`alert-type-tag ${alert.type}`}>{alert.type}</span>
      </div>
      <div className="alert-message">{alert.message}</div>
    </div>
  );
}
