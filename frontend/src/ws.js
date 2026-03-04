/**
 * WebSocket client with auto-reconnect.
 *
 * Usage:
 *   const ws = createWebSocket({ onMessage: (msg) => ... });
 *   ws.connect();
 *   // later: ws.close();
 */

export function createWebSocket({ onMessage, onStatusChange }) {
  let socket = null;
  let reconnectTimer = null;
  let intentionalClose = false;
  const RECONNECT_DELAY = 2000;

  function getUrl() {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/ws/stream`;
  }

  function connect() {
    intentionalClose = false;
    try {
      socket = new WebSocket(getUrl());
    } catch {
      scheduleReconnect();
      return;
    }

    socket.onopen = () => {
      onStatusChange?.("connected");
    };

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        onMessage?.(msg);
      } catch {
        // ignore malformed messages
      }
    };

    socket.onclose = () => {
      onStatusChange?.("disconnected");
      if (!intentionalClose) {
        scheduleReconnect();
      }
    };

    socket.onerror = () => {
      onStatusChange?.("disconnected");
      socket?.close();
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    onStatusChange?.("reconnecting");
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, RECONNECT_DELAY);
  }

  function close() {
    intentionalClose = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    socket?.close();
    socket = null;
  }

  return { connect, close };
}
