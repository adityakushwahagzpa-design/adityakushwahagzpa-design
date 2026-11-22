"""Charts for the README: stream overview, four incident close-ups, detection latency."""
import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

C = {"line": "#1F3864", "alert": "#C00000", "band": "#F4B183", "event": "#A9D18E", "grey": "#7F7F7F"}
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})

df = pd.read_csv("data/stream.csv", parse_dates=["ts"])
al = pd.read_csv("outputs/alerts.csv", parse_dates=["ts"])
pl = pd.read_csv("data/planted_incidents.csv", parse_dates=["start", "end"])
cal = pd.read_csv("data/business_calendar.csv", parse_dates=["start", "end"])
ev = pd.read_csv("outputs/evaluation.csv")
summ = json.load(open("outputs/summary.json"))

# 1. overview: total transactions per 15 minutes, incidents and the festival shaded
tot = df.groupby("ts").txns.sum().resample("15min").sum()
fig, ax = plt.subplots(figsize=(11, 3.6))
ax.plot(tot.index, tot.values / 1000, color=C["line"], lw=0.8)
for _, p in pl.iterrows():
    ax.axvspan(p.start, p.end, color=C["band"], alpha=0.8)
    ax.text(p.start, ax.get_ylim()[1] * 0.97 if False else tot.max() / 1000 * 1.02, p.incident_id, fontsize=7, color=C["alert"])
for _, e in cal.iterrows():
    ax.axvspan(e.start, e.end, color=C["event"], alpha=0.9)
ax.axvspan(df.ts.min(), df.ts.min() + pd.Timedelta(days=2), color="#EEEEEE", zorder=0)
ax.text(df.ts.min() + pd.Timedelta(hours=6), tot.max() / 1000 * 0.9, "warm-up\n(no alerts)", fontsize=8, color=C["grey"])
ax.set_ylabel("Transactions per 15 min ('000)")
ax.set_title("14 days of payment traffic: planted incidents (orange) and a planned festival sale (green, should not alert)")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
fig.tight_layout()
fig.savefig("outputs/chart_stream_overview.png", dpi=150)

# 2. close-ups of four incidents with the alerts that fired
def channel_series(ch, metric):
    d = df[df.channel == ch].set_index("ts")
    ok = d.txns - d.failed
    return {"volume": d.txns, "fail_rate": d.failed / d.txns * 100,
            "refund_rate": d.refunds / ok * 100, "avg_ticket": d.value_inr / ok}[metric]

panels = [("INC1", "Card", "fail_rate", "Card failure rate (%)"),
          ("INC3", "Card", "avg_ticket", "Card average ticket (Rs)"),
          ("INC2", "UPI", "volume", "UPI transactions per minute"),
          ("INC6", "NetBanking", "fail_rate", "NetBanking failure rate (%), 15-min average")]
fig, axes = plt.subplots(2, 2, figsize=(11, 6.4))
for axx, (inc, ch, m, lab) in zip(axes.flat, panels):
    p = pl[pl.incident_id == inc].iloc[0]
    pad = pd.Timedelta(hours=6 if inc == "INC6" else 2)
    s = channel_series(ch, m)
    s = s[(s.index >= p.start - pad) & (s.index <= p.end + pad)]
    if inc == "INC6":
        s = s.rolling(15).mean()
    axx.plot(s.index, s.values, color=C["line"], lw=0.9)
    axx.axvspan(p.start, p.end, color=C["band"], alpha=0.5, label="planted incident")
    a = al[(al.entity == ch) & (al.metric == m) & (al.ts >= p.start - pad) & (al.ts <= p.end + pad)]
    if len(a):
        axx.scatter(a.ts, s.reindex(a.ts).values, color=C["alert"], s=12, zorder=3, label="alert")
        first = a.ts.min()
        axx.axvline(first, color=C["alert"], ls="--", lw=0.8)
        lat = int((first - p.start).total_seconds() / 60)
        axx.set_title(f"{inc} {p.type}: first alert after {lat} min", fontsize=9)
    axx.set_ylabel(lab)
    axx.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    axx.legend(fontsize=7, loc="upper left", frameon=False)
fig.tight_layout()
fig.savefig("outputs/chart_incident_closeups.png", dpi=150)

# 3. latency per incident
fig, ax = plt.subplots(figsize=(8, 3.2))
lab = ev.incident_id + " " + ev.type
ax.barh(lab, ev.latency_min, color=[C["alert"] if x > 30 else C["line"] for x in ev.latency_min])
for i, v in enumerate(ev.latency_min):
    ax.text(v + 1, i, f"{int(v)} min", va="center", fontsize=8)
ax.invert_yaxis()
ax.set_xlabel("Minutes from incident start to first alert")
ax.set_title(f"Detection latency: {summ['detected']} of {summ['planted']} incidents caught, "
             f"{summ['false_incidents']} false alarms in {int((summ['minutes_processed'] - 2880) / 1440)} monitored days")
fig.tight_layout()
fig.savefig("outputs/chart_latency.png", dpi=150)
print("charts saved")
