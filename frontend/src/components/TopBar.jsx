import { IconActivity } from "./Icons";

export default function TopBar({ tickCount, symbolCount, clock }) {
  return (
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
          symbols <span>{symbolCount}</span>
        </div>
        <div className="divider-v" />
        <div className="clock">{clock}</div>
      </div>
    </div>
  );
}
