import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const rupees = (p) => (p == null ? "—" : (p / 100).toFixed(2));

// "100.25" -> 10025 paise, without floating point
function toPaise(text) {
  const m = /^\s*(\d+)(?:\.(\d{1,2}))?\s*$/.exec(text);
  if (!m) return null;
  return Number(m[1]) * 100 + Number((m[2] || "0").padEnd(2, "0"));
}

function useExchange() {
  const [state, setState] = useState(null);
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    let ws, stop = false, timer;
    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (e) => setState(JSON.parse(e.data));
      ws.onclose = () => {
        setConnected(false);
        if (!stop) timer = setTimeout(connect, 1000);   // reconnect if the server restarts
      };
    };
    connect();
    return () => { stop = true; clearTimeout(timer); ws && ws.close(); };
  }, []);
  return { state, connected };
}

function Ladder({ book }) {
  const asks = [...(book?.asks || [])].reverse();   // highest ask at the top, best ask next to the spread
  const bids = book?.bids || [];
  const maxQty = Math.max(1, ...asks.map((l) => l[1]), ...bids.map((l) => l[1]));
  const row = (side) => ([price, qty, count]) => (
    <tr key={side + price} className={side}>
      <td className="bar-cell">
        <div className="bar" style={{ width: `${(100 * qty) / maxQty}%` }} />
        <span>{qty.toLocaleString("en-IN")}</span>
      </td>
      <td className="price">{rupees(price)}</td>
      <td className="muted">{count}</td>
    </tr>
  );
  const spread = bids[0] && book.asks[0] ? book.asks[0][0] - bids[0][0] : null;
  return (
    <table className="ladder">
      <thead><tr><th>Quantity</th><th>Price (₹)</th><th>Orders</th></tr></thead>
      <tbody>
        {asks.map(row("ask"))}
        <tr className="spread"><td colSpan={3}>Spread {spread == null ? "—" : `₹${rupees(spread)}`}</td></tr>
        {bids.map(row("bid"))}
      </tbody>
    </table>
  );
}

function OrderForm({ onResult }) {
  const [side, setSide] = useState("buy");
  const [type, setType] = useState("limit");
  const [qty, setQty] = useState("100");
  const [price, setPrice] = useState("100.00");
  const [cancelId, setCancelId] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    const pricePaise = type === "market" ? null : toPaise(price);
    if (type === "limit" && !pricePaise) return onResult("Enter a price like 100.25");
    const res = await fetch("/api/orders", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ side, qty: Number(qty), price_paise: pricePaise }),
    });
    const body = await res.json();
    if (!res.ok) return onResult("Rejected: check side, quantity and price");
    const filled = body.trades.reduce((s, t) => s + t.qty, 0);
    onResult(`Order #${body.order_id}: ${filled} filled in ${body.trades.length} trade(s), ${body.resting_qty} resting`);
  };
  const cancel = async () => {
    const res = await fetch(`/api/orders/${Number(cancelId)}`, { method: "DELETE" });
    onResult(res.ok ? `Order #${cancelId} cancelled` : `Order #${cancelId} not found or already filled`);
  };
  return (
    <form className="card form" onSubmit={submit}>
      <h2>Place an order</h2>
      <div className="seg">
        {["buy", "sell"].map((s) => (
          <button type="button" key={s} className={side === s ? `on ${s}` : ""} onClick={() => setSide(s)}>{s}</button>
        ))}
      </div>
      <div className="seg">
        {["limit", "market"].map((t) => (
          <button type="button" key={t} className={type === t ? "on" : ""} onClick={() => setType(t)}>{t}</button>
        ))}
      </div>
      <label>Quantity<input value={qty} onChange={(e) => setQty(e.target.value)} inputMode="numeric" /></label>
      {type === "limit" && <label>Price (₹)<input value={price} onChange={(e) => setPrice(e.target.value)} inputMode="decimal" /></label>}
      <button className={`submit ${side}`} type="submit">{side === "buy" ? "Buy" : "Sell"} {qty}</button>
      <div className="cancel">
        <input placeholder="Order #" value={cancelId} onChange={(e) => setCancelId(e.target.value)} />
        <button type="button" onClick={cancel} disabled={!cancelId}>Cancel</button>
      </div>
    </form>
  );
}

function App() {
  const { state, connected } = useExchange();
  const [msg, setMsg] = useState("");
  const last = state?.trades?.[0];
  const prev = useRef(null);
  const tick = last && prev.current != null ? Math.sign(last.price_paise - prev.current) : 0;
  useEffect(() => { if (last) prev.current = last.price_paise; }, [last?.price_paise]);
  return (
    <div className="app">
      <header>
        <div>
          <h1>Mini Stock Exchange</h1>
          <p className="muted">Price-time priority matching · live over WebSockets</p>
        </div>
        <div className={`status ${connected ? "ok" : ""}`}>{connected ? "● Live" : "○ Connecting…"}</div>
      </header>
      <section className="kpis">
        <div className="card"><span>Last price</span><b className={tick > 0 ? "up" : tick < 0 ? "down" : ""}>₹{rupees(last?.price_paise)}</b></div>
        <div className="card"><span>Best bid</span><b className="up">₹{rupees(state?.best_bid)}</b></div>
        <div className="card"><span>Best ask</span><b className="down">₹{rupees(state?.best_ask)}</b></div>
        <div className="card"><span>Orders</span><b>{(state?.stats.orders ?? 0).toLocaleString("en-IN")}</b></div>
        <div className="card"><span>Trades</span><b>{(state?.stats.trades ?? 0).toLocaleString("en-IN")}</b></div>
        <div className="card"><span>Volume</span><b>{(state?.stats.volume ?? 0).toLocaleString("en-IN")}</b></div>
      </section>
      <main>
        <div className="card"><h2>Order book · top 10 levels</h2><Ladder book={state?.book} /></div>
        <div className="card">
          <h2>Recent trades</h2>
          <table className="trades">
            <thead><tr><th>Time</th><th>Price (₹)</th><th>Qty</th><th>Aggressor</th></tr></thead>
            <tbody>
              {(state?.trades || []).map((t, i) => (
                <tr key={i}>
                  <td className="muted">{new Date(t.time * 1000).toLocaleTimeString("en-IN")}</td>
                  <td className={t.side === "buy" ? "up" : "down"}>{rupees(t.price_paise)}</td>
                  <td>{t.qty}</td>
                  <td className="muted">{t.side} #{t.taker}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <OrderForm onResult={setMsg} />
          {msg && <div className="card note">{msg}</div>}
          {state?.db_trades_written != null && <div className="card note muted">PostgreSQL: {state.db_trades_written.toLocaleString("en-IN")} trades stored</div>}
        </div>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
