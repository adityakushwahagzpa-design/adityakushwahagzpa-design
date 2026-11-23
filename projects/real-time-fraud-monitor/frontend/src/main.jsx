import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

const RULE_NAMES = { velocity: "Velocity", impossible_travel: "Impossible travel", unusual_amount: "Unusual amount" };
const RULE_COLORS = { velocity: "#d29922", impossible_travel: "#f85149", unusual_amount: "#58a6ff" };
const inr = (x) => "₹" + Number(x).toLocaleString("en-IN", { maximumFractionDigits: 0 });
const when = (t) => new Date(t * 1000).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
const card4 = (c) => "•••• " + String(c).slice(-4);

function usePoll(url, ms) {
  const [data, setData] = useState(null);
  useEffect(() => {
    let alive = true;
    const tick = () => fetch(url).then((r) => (r.ok ? r.json() : null)).then((d) => alive && setData(d)).catch(() => {});
    tick();
    const id = setInterval(tick, ms);
    return () => { alive = false; clearInterval(id); };
  }, [url, ms]);
  return data;
}

function Rule({ name }) {
  return <span className={`rule ${name}`}>{RULE_NAMES[name] || name}</span>;
}

function CardPanel({ cc }) {
  const data = usePoll(`/api/cards/${cc}`, 2000);
  if (!data) return <p className="muted">Card history needs PostgreSQL (start the server with DATABASE_URL).</p>;
  const flagged = new Set(data.alerts.map((a) => a.trans_num));
  return (
    <>
      <p className="muted">Card {card4(cc)} · last {data.history.length} transactions · {data.alerts.length} alerts</p>
      <table>
        <thead><tr><th>Time (UTC)</th><th>Merchant</th><th>Category</th><th className="num">Amount</th><th>Label</th></tr></thead>
        <tbody>
          {data.history.map((t) => (
            <tr key={t.trans_num} className={flagged.has(t.trans_num) ? "sel" : ""}>
              <td>{when(t.unix_time)}</td><td>{t.merchant}</td><td>{t.category}{t.channel === "online" ? " · online" : ""}</td>
              <td className="num">{inr(t.amt)}</td>
              <td>{t.is_fraud ? <span className="label fraud">fraud</span> : <span className="label ok">genuine</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="note">Highlighted rows raised an alert. Labels come from the dataset and are shown only to judge the rules.</p>
    </>
  );
}

function App() {
  const stats = usePoll("/api/stats", 1000);
  const alerts = usePoll("/api/alerts?limit=40", 1000) || [];
  const merchants = usePoll("/api/merchants/flagged", 4000) || [];
  const rules = usePoll("/api/rules", 30000);
  const [card, setCard] = useState(null);
  const s = stats || { transactions: 0, flagged_transactions: 0, by_rule: {}, flagged_fraud: 0, labelled_fraud: 0 };
  const active = card || (alerts[0] && alerts[0].cc_num);
  const maxRule = Math.max(1, ...Object.values(s.by_rule || {}));
  const precision = s.flagged_transactions ? (100 * s.flagged_fraud) / s.flagged_transactions : null;
  const recall = s.labelled_fraud ? (100 * s.flagged_fraud) / s.labelled_fraud : null;

  return (
    <>
      <header>
        <div>
          <h1>Real-Time Fraud Monitor</h1>
          <div className="sub">Every transaction checked against configurable rules · alerts go to a human for review</div>
        </div>
        <span className="badge">{s.storage || "connecting…"} · {s.avg_check_microseconds ?? "–"} µs per check</span>
      </header>

      <div className="kpis">
        <div className="kpi"><div className="l">Transactions checked</div><div className="v">{s.transactions.toLocaleString("en-IN")}</div></div>
        <div className="kpi"><div className="l">Flagged</div><div className="v">{s.flagged_transactions.toLocaleString("en-IN")}</div></div>
        <div className="kpi"><div className="l">Flag rate</div><div className="v">{s.transactions ? ((100 * s.flagged_transactions) / s.transactions).toFixed(2) + "%" : "–"}</div></div>
        <div className="kpi"><div className="l">Labelled fraud seen</div><div className="v">{s.labelled_fraud}</div></div>
        <div className="kpi"><div className="l">Precision</div><div className="v">{precision == null ? "–" : precision.toFixed(1) + "%"}</div></div>
        <div className="kpi"><div className="l">Recall</div><div className="v">{recall == null ? "–" : recall.toFixed(1) + "%"}</div></div>
      </div>

      <main>
        <div>
          <section className="panel">
            <h2>Live alerts</h2>
            <table>
              <thead><tr><th>Time (UTC)</th><th>Card</th><th>Rule</th><th className="num">Amount</th><th>Label</th></tr></thead>
              <tbody>
                {alerts.map((a, i) => (
                  <tr key={a.trans_num + a.rule + i} className={"click" + (active === a.cc_num ? " sel" : "")} onClick={() => setCard(a.cc_num)}>
                    <td>{when(a.unix_time)}</td>
                    <td>{card4(a.cc_num)}</td>
                    <td><Rule name={a.rule} /><div className="detail">{a.detail}</div></td>
                    <td className="num">{inr(a.amt)}<div className="detail">{a.category}</div></td>
                    <td>{a.is_fraud ? <span className="label fraud">fraud</span> : <span className="label ok">genuine</span>}</td>
                  </tr>
                ))}
                {!alerts.length && <tr><td colSpan="5" className="muted">No alerts yet. Start the replay: python replay.py</td></tr>}
              </tbody>
            </table>
          </section>
        </div>
        <div>
          <section className="panel">
            <h2>Alerts by rule</h2>
            <div className="bars">
              {Object.keys(RULE_NAMES).map((r) => (
                <div key={r}><span>{RULE_NAMES[r]}</span>
                  <span className="bar"><span style={{ width: `${(100 * (s.by_rule[r] || 0)) / maxRule}%`, background: RULE_COLORS[r] }} /></span>
                  <span className="num">{(s.by_rule[r] || 0).toLocaleString("en-IN")}</span></div>
              ))}
            </div>
            {rules && <p className="note">Thresholds (config/rules.json): {rules.velocity.max_tx_in_window} transactions in {rules.velocity.window_seconds / 60} min ·
              {" "}{rules.impossible_travel.max_speed_kmh} km/h, in-store only · z-score above {rules.unusual_amount.max_zscore} after {rules.unusual_amount.min_history} purchases</p>}
          </section>
          <section className="panel">
            <h2>Card history · click an alert</h2>
            {active ? <CardPanel cc={active} /> : <p className="muted">Select an alert to see the card's recent transactions.</p>}
          </section>
          <section className="panel">
            <h2>Merchants flagged on 2+ cards</h2>
            <table>
              <thead><tr><th>Merchant</th><th>Category</th><th className="num">Cards</th><th className="num">Alerts</th><th>Rules</th></tr></thead>
              <tbody>
                {merchants.slice(0, 8).map((m) => (
                  <tr key={m.merchant}><td>{m.merchant}</td><td>{m.category}</td><td className="num">{m.cards_flagged}</td><td className="num">{m.alerts}</td><td className="detail">{m.rules}</td></tr>
                ))}
                {!merchants.length && <tr><td colSpan="5" className="muted">None yet</td></tr>}
              </tbody>
            </table>
          </section>
        </div>
      </main>
    </>
  );
}

createRoot(document.getElementById("root")).render(<App />);
