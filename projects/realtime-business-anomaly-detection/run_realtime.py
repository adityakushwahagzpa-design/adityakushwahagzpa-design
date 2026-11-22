"""Replay the payment stream minute by minute through the detector, as a live feed would.

  python run_realtime.py            # full replay, writes outputs/
  python run_realtime.py --live 20  # print alerts as they fire, 20 minutes of data per second
"""
import argparse
import json
import os
import time
import numpy as np
import pandas as pd
from detector import StreamingDetector, group_incidents


def load():
    df = pd.read_csv("data/stream.csv", parse_dates=["ts"])
    planted = pd.read_csv("data/planted_incidents.csv", parse_dates=["start", "end"])
    cal = pd.read_csv("data/business_calendar.csv", parse_dates=["start", "end"])
    return df, planted, cal


def evaluate(incidents, planted, monitored_days, tolerance_min=30):
    rows, matched = [], set()
    for _, p in planted.iterrows():
        hit = incidents[(incidents.first_alert <= p.end + pd.Timedelta(minutes=tolerance_min)) &
                        (incidents.last_alert >= p.start)]
        if len(hit):
            first = hit.first_alert.min()
            matched.update(hit.incident_no)
            rows.append(dict(incident_id=p.incident_id, type=p.type, channel=p.channel, start=p.start,
                             detected="Yes", first_alert=first,
                             latency_min=int((first - p.start).total_seconds() / 60),
                             lead_metric=hit.iloc[0].lead_metric, likely_cause=hit.iloc[0].likely_cause))
        else:
            rows.append(dict(incident_id=p.incident_id, type=p.type, channel=p.channel, start=p.start,
                             detected="No", first_alert=pd.NaT, latency_min=np.nan, lead_metric="", likely_cause=""))
    ev = pd.DataFrame(rows)
    false_inc = incidents[~incidents.incident_no.isin(matched)]
    summary = dict(planted=len(planted), detected=int((ev.detected == "Yes").sum()),
                   recall=round(float((ev.detected == "Yes").mean()), 3),
                   detected_incidents=len(incidents), false_incidents=len(false_inc),
                   precision=round(1 - len(false_inc) / max(len(incidents), 1), 3),
                   false_incidents_per_day=round(len(false_inc) / monitored_days, 2),
                   median_latency_min=float(ev.latency_min.median()),
                   max_latency_min=float(ev.latency_min.max()))
    return ev, false_inc, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", type=float, default=0, help="minutes of data per second to print live")
    args = ap.parse_args()
    df, planted, cal = load()
    entities = ["UPI", "Card", "NetBanking", "Total"]
    tot = df.groupby("ts")[["txns", "failed", "refunds", "value_inr"]].sum()
    tot["channel"] = "Total"
    full = pd.concat([df.set_index("ts"), tot]).reset_index()
    stamps = np.sort(full.ts.unique())
    det = StreamingDetector(entities, len(stamps), warmup_days=2,
                            calendar=list(zip(cal.start, cal.end)))
    groups = {t: g for t, g in full.groupby("ts")}
    alerts = []
    t0 = time.time()
    for ts in stamps:
        g = groups[ts]
        minute = {r.channel: (r.txns, r.failed, r.refunds, r.value_inr) for r in g.itertuples()}
        new = det.update(pd.Timestamp(ts), minute)
        alerts += new
        if args.live and new:
            for a in new:
                print(f"[{a['ts']:%d-%b %H:%M}] ALERT {a['entity']:<10} {a['metric']:<11} z={a['z']:>7}  {a['cause']}")
        if args.live:
            time.sleep(1 / args.live)
    secs = time.time() - t0
    al = pd.DataFrame(alerts)
    inc = group_incidents(al)
    monitored_days = (len(stamps) - 2 * 1440) / 1440
    ev, false_inc, summary = evaluate(inc, planted, monitored_days)
    summary.update(minutes_processed=len(stamps), alerts=len(al), volume_alerts_suppressed_by_calendar=det.suppressed,
                   processing_ms_per_minute=round(secs / len(stamps) * 1000, 2))
    os.makedirs("outputs", exist_ok=True)
    al.to_csv("outputs/alerts.csv", index=False)
    inc.to_csv("outputs/incidents.csv", index=False)
    ev.to_csv("outputs/evaluation.csv", index=False)
    json.dump(summary, open("outputs/summary.json", "w"), indent=2, default=str)
    print(json.dumps(summary, indent=2, default=str))
    print(ev[["incident_id", "type", "detected", "latency_min", "lead_metric"]].to_string(index=False))
    if len(false_inc):
        print("\nFalse incidents:\n", false_inc[["first_alert", "channels", "lead_metric", "peak_z"]].to_string(index=False))


if __name__ == "__main__":
    main()
