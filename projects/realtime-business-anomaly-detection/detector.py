"""Streaming anomaly detector for minute-level payment metrics.

update() takes one minute of data at a time and returns any alerts, so the same code can
sit behind a live feed. For every channel and for the total it tracks four metrics:

  volume       transactions a minute, vs a seasonal baseline (median of the same time of day,
               +/-15 minutes, over the previous 7 days), with Poisson noise plus 10% dispersion
  fail_rate    failed / attempted, vs the trailing 24-hour rate (exact Poisson tail, so
               small night-time counts do not set off alarms)
  refund_rate  refunds / successful, vs the trailing 24-hour rate (exact Poisson tail)
  avg_ticket   value / successful, vs the trailing 24-hour average, z-score from the
               spread of individual payment sizes

Rules: a point alert at |z| >= 5, a sustained alert when 3 of the last 5 minutes have
|z| >= 3.5, and a CUSUM alarm for slow drifts in failure and refund rates. Minutes that
raised an alert are kept out of the baselines, and volume alerts are suppressed during
events in the business calendar (planned sales).
"""
from collections import deque
import numpy as np
from scipy.stats import norm, poisson

METRICS = ["volume", "fail_rate", "refund_rate", "avg_ticket"]
CAUSE = {("volume", "down"): "Traffic drop: partner, app or network outage",
         ("volume", "up"): "Traffic spike: duplicate charges, bots or an unplanned campaign",
         ("fail_rate", "up"): "Payment failures: gateway or bank outage",
         ("refund_rate", "up"): "Refund surge: fulfilment or merchant problem",
         ("avg_ticket", "up"): "Unusually large payments: possible fraud",
         ("avg_ticket", "down"): "Low ticket size: pricing or discount bug"}
TICKET_CV = np.sqrt(np.exp(0.9 ** 2) - 1)  # spread of single payment sizes (lognormal sigma 0.9)


def count_z(x, lam):
    """Signed z-score for an observed count x against an expected count lam, using the
    Poisson mid-p value, so that small counts at night do not set off false alarms."""
    lam = max(lam, 1e-6)
    f_mid = (poisson.cdf(x - 1, lam) if x > 0 else 0.0) + 0.5 * poisson.pmf(x, lam)
    return float(np.clip(norm.ppf(np.clip(f_mid, 1e-300, 1 - 1e-16)), -40, 40))


class SeriesState:
    def __init__(self, n_minutes):
        self.txns = np.full(n_minutes, np.nan)
        self.failed = np.zeros(n_minutes)
        self.refunds = np.zeros(n_minutes)
        self.value = np.zeros(n_minutes)
        self.clean = np.zeros(n_minutes, dtype=bool)  # usable for baselines
        self.recent = {m: deque(maxlen=5) for m in METRICS}
        self.cusum = {"fail_rate": 0.0, "refund_rate": 0.0}


class StreamingDetector:
    def __init__(self, entities, n_minutes, warmup_days=2, calendar=None,
                 z_point=5.0, z_sustained=3.5, cusum_k=0.5, cusum_h=10.0):
        self.s = {e: SeriesState(n_minutes) for e in entities}
        self.t = -1
        self.warmup = warmup_days * 1440
        self.calendar = calendar or []
        self.zp, self.zs, self.k, self.h = z_point, z_sustained, cusum_k, cusum_h
        self.suppressed = 0
        self.offsets = np.array([k * 1440 + o for k in range(1, 8) for o in range(-15, 16, 5)])

    def _in_event(self, ts):
        return any(s <= ts <= e for s, e in self.calendar)

    def _trailing(self, st, t):
        lo = max(0, t - 1440)
        m = st.clean[lo:t]
        if m.sum() < 120:
            return None
        n = st.txns[lo:t][m].sum()
        f = st.failed[lo:t][m].sum()
        ok = n - f
        return dict(p_fail=f / n, p_refund=st.refunds[lo:t][m].sum() / ok, ticket=st.value[lo:t][m].sum() / ok)

    def update(self, ts, minute):
        """minute: dict entity -> (txns, failed, refunds, value). Returns a list of alerts."""
        self.t += 1
        t = self.t
        alerts = []
        event = self._in_event(ts)
        for e, (n, f, r, v) in minute.items():
            st = self.s[e]
            st.txns[t], st.failed[t], st.refunds[t], st.value[t] = n, f, r, v
            st.clean[t] = True
            if t < self.warmup:
                continue
            z = {}
            idx = t - self.offsets
            idx = idx[idx >= 0]
            hist = st.txns[idx][st.clean[idx]]
            if len(hist) >= 14:
                exp = float(np.median(hist))
                z["volume"] = (n - exp) / np.sqrt(exp + (0.10 * exp) ** 2 + 1)
            base = self._trailing(st, t)
            ok = n - f
            if base and n > 0:
                z["fail_rate"] = count_z(f, n * base["p_fail"])
            if base and ok > 0:
                z["refund_rate"] = count_z(r, ok * base["p_refund"])
                if e != "Total":  # channel mix makes a blended ticket size meaningless
                    m0 = base["ticket"]
                    z["avg_ticket"] = (v / ok - m0) / (m0 * TICKET_CV / np.sqrt(ok))
            hit = False
            for m, zv in z.items():
                if m == "volume" and event:  # planned event: expected surge, do not score it
                    st.recent[m].clear()
                    if max(abs(zv), 0) >= self.zs:
                        self.suppressed += 1
                    continue
                st.recent[m].append(abs(zv))
                one_sided = m in ("fail_rate", "refund_rate")
                score = zv if one_sided else abs(zv)
                rule = None
                if score >= self.zp:
                    rule = "point"
                elif sum(x >= self.zs for x in st.recent[m]) >= 3 and (not one_sided or zv > 0):
                    rule = "sustained"
                if m in st.cusum:
                    st.cusum[m] = max(0.0, st.cusum[m] + zv - self.k)
                    if rule is None and st.cusum[m] >= self.h:
                        rule = "cusum"
                    if rule:
                        st.cusum[m] = 0.0
                if rule is None:
                    continue
                direction = "up" if zv > 0 else "down"
                alerts.append(dict(ts=ts, entity=e, metric=m, z=round(float(zv), 2), rule=rule,
                                   direction=direction, cause=CAUSE[(m, direction)]))
                hit = True
            if hit:
                st.clean[t] = False
        return alerts


def group_incidents(alerts, gap_minutes=15):
    """Merge alerts that are close in time into incidents with a root-cause hint."""
    import pandas as pd
    if not len(alerts):
        return pd.DataFrame()
    a = alerts.sort_values("ts").reset_index(drop=True)
    new = a.ts.diff().dt.total_seconds().div(60).fillna(1e9) > gap_minutes
    a["incident"] = new.cumsum()
    out = []
    for i, g in a.groupby("incident"):
        top = g.loc[g.z.abs().idxmax()]
        chans = sorted(set(g.entity) - {"Total"})
        out.append(dict(incident_no=int(i), first_alert=g.ts.min(), last_alert=g.ts.max(),
                        duration_min=int((g.ts.max() - g.ts.min()).total_seconds() / 60) + 1,
                        alerts=len(g), channels=", ".join(chans) if chans else "Total",
                        lead_metric=f"{top.entity} {top.metric} ({top.direction})",
                        peak_z=float(top.z), rules=", ".join(sorted(set(g.rule))), likely_cause=top.cause))
    return pd.DataFrame(out)
