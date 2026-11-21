"""
Month-end reconciliation for Aarohan Large Cap Fund (October 2026).

Checks the fund accounting book against the broker and the custodian, the way a fund
services team does at month-end, and explains every difference:

  1. Trade matching        book trades vs broker confirmations (quantity, net amount, duplicates, missing)
  2. Settlement monitoring custodian settlement dates vs contractual T+1 (late and failed settlements)
  3. Corporate actions     dividend, bonus and split entitlements, book vs custodian
  4. Position recon        month-end holdings by stock, with each difference traced to its cause
  5. Cash recon            month-end cash, with each rupee of difference traced to its cause
  6. NAV impact            how much the book NAV is misstated by the open breaks, in basis points

Outputs: outputs/reconciliation_workbook.xlsx (one sheet per check plus an exception log),
outputs/REPORT.md, outputs/summary.json and three charts.
"""
import json
from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

D = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)
AMOUNT_TOLERANCE = 1.00  # ₹ difference allowed on net amounts
WINE, ROSE, GREY, DARK = "#701A3D", "#C77B9B", "#8A8A8A", "#2A0E1B"


def load():
    r = lambda f, **k: pd.read_csv(D / f, **k)
    dates = ["trade_date", "settle_date"]
    return dict(
        book=r("book_trades.csv", parse_dates=dates), broker=r("broker_confirmations.csv", parse_dates=dates),
        settle=r("custodian_settlements.csv", parse_dates=["settle_date", "custodian_settle_date"]),
        ca=r("corporate_actions.csv", parse_dates=["record_date", "pay_date"]),
        book_ca=r("book_corporate_actions.csv"), cust_ca=r("custodian_corporate_actions.csv"),
        book_pos=r("book_positions_month_end.csv"), cust_pos=r("custodian_positions_month_end.csv"),
        cash=r("cash_balances.csv").set_index("source"), cust_other=r("custodian_cash_other.csv"),
        prices=r("prices.csv", parse_dates=["date"]).set_index("date"), sec=r("securities.csv"),
    )


def trade_matching(book, broker):
    counts = book.trade_ref.value_counts()
    dup_refs = set(counts[counts > 1].index)
    b1 = book.drop_duplicates("trade_ref")
    m = broker.merge(b1, on="trade_ref", how="outer", suffixes=("_brk", "_book"), indicator=True)
    rows = []
    for _, x in m.iterrows():
        sym = x.symbol_brk if pd.notna(x.symbol_brk) else x.symbol_book
        if x._merge == "left_only":
            status, qd, ad = "Missing in book", -x.quantity_brk, None
        elif x._merge == "right_only":
            status, qd, ad = "Missing at broker", x.quantity_book, None
        else:
            qd = x.quantity_book - x.quantity_brk
            ad = round(x.net_amount_book - x.net_amount_brk, 2)
            if qd != 0:
                status = "Quantity mismatch"
            elif abs(ad) > AMOUNT_TOLERANCE:
                status = "Amount mismatch"
            else:
                status = "Matched"
        rows.append({"trade_ref": x.trade_ref, "symbol": sym, "side": x.side_brk if pd.notna(x.side_brk) else x.side_book,
                     "trade_date": x.trade_date_brk if pd.notna(x.trade_date_brk) else x.trade_date_book,
                     "qty_broker": x.quantity_brk, "qty_book": x.quantity_book, "qty_diff": qd,
                     "amount_broker": x.net_amount_brk, "amount_book": x.net_amount_book, "amount_diff": ad, "status": status})
    tm = pd.DataFrame(rows)
    for ref in dup_refs:
        r0 = book[book.trade_ref == ref].iloc[0]
        tm = pd.concat([tm, pd.DataFrame([{"trade_ref": ref, "symbol": r0.symbol, "side": r0.side, "trade_date": r0.trade_date,
                                           "qty_broker": 0, "qty_book": r0.quantity, "qty_diff": r0.quantity * (counts[ref] - 1),
                                           "amount_broker": 0, "amount_book": r0.net_amount, "amount_diff": r0.net_amount * (counts[ref] - 1),
                                           "status": "Duplicate in book"}])], ignore_index=True)
    return tm.sort_values(["status", "trade_ref"]).reset_index(drop=True)


def settlement_monitor(settle, month_end):
    s = settle.copy()
    s["days_late"] = (s.custodian_settle_date - s.settle_date).dt.days
    s["status"] = np.where(s.custodian_settle_date.isna(), "Failed - pending",
                           np.where(s.days_late > 0, "Settled late", "Settled on time"))
    s["age_days"] = np.where(s.status == "Failed - pending", (month_end - s.settle_date).dt.days, 0)
    return s


def corporate_actions(ca, book_ca, cust_ca):
    m = ca.merge(cust_ca[["ca_id", "eligible_quantity", "cash_credited", "shares_credited"]], on="ca_id", how="left") \
          .merge(book_ca[["ca_id", "eligible_quantity", "cash_booked", "shares_booked"]], on="ca_id", how="left", suffixes=("_cust", "_book"))
    m["cash_diff"] = (m.cash_booked.fillna(0) - m.cash_credited.fillna(0)).round(2)
    m["shares_diff"] = m.shares_booked.fillna(0) - m.shares_credited.fillna(0)
    m["status"] = np.where(m.cash_booked.isna(), "Not booked in book",
                  np.where((m.cash_diff.abs() > AMOUNT_TOLERANCE) | (m.shares_diff != 0), "Entitlement difference", "Matched"))
    return m


def main():
    x = load()
    month_end = x["prices"].index.max()
    tm = trade_matching(x["book"], x["broker"])
    sm = settlement_monitor(x["settle"], month_end)
    cam = corporate_actions(x["ca"], x["book_ca"], x["cust_ca"])

    # ---- position reconciliation with explanations
    pos = x["book_pos"].merge(x["cust_pos"], on="symbol", how="outer", suffixes=("_book", "_custodian")).fillna(0)
    pos["difference"] = pos.quantity_book - pos.quantity_custodian
    expl = pd.DataFrame(0.0, index=pos.symbol, columns=["trade_breaks", "failed_settlements", "corporate_actions"])
    for _, t in tm[tm.status != "Matched"].iterrows():
        sign = 1 if t.side == "BUY" else -1
        expl.at[t.symbol, "trade_breaks"] += sign * (t.qty_diff if pd.notna(t.qty_diff) else 0)
    for _, s in sm[sm.status == "Failed - pending"].iterrows():
        sign = 1 if s.side == "BUY" else -1
        expl.at[s.symbol, "failed_settlements"] += sign * s.quantity
    for _, c in cam.iterrows():
        expl.at[c.symbol, "corporate_actions"] += c.shares_diff
    pos = pos.merge(expl.reset_index(), on="symbol")
    pos["explained"] = pos[["trade_breaks", "failed_settlements", "corporate_actions"]].sum(axis=1)
    pos["unexplained"] = pos.difference - pos.explained
    pos["status"] = np.where(pos.difference == 0, "Matched", np.where(pos.unexplained.abs() < 1e-6, "Break - explained", "Break - UNEXPLAINED"))

    negative = pos[pos.quantity_book < 0]  # a long-only fund cannot hold fewer than zero shares

    # ---- cash reconciliation with explanations
    bc, cc = x["cash"].loc["book", "closing_cash"], x["cash"].loc["custodian", "closing_cash"]
    tb = tm[tm.status != "Matched"].copy()
    signed = lambda df, col: np.where(df.side == "BUY", -1, 1) * df[col].fillna(0)
    tb["cash_effect"] = signed(tb, "amount_book") - signed(tb, "amount_broker")
    fails = sm[sm.status == "Failed - pending"]
    cash_items = [
        ("Trade breaks (quantity, amount, duplicates, missing)", float(tb.cash_effect.sum())),
        ("Failed settlements booked as settled", float((np.where(fails.side == "BUY", -1, 1) * fails.net_amount).sum())),
        ("Corporate action cash differences", float(cam.cash_diff.sum())),
        ("Custodian charges not booked", float(-x["cust_other"].amount.sum())),
    ]
    cash_diff = round(bc - cc, 2)
    cash_unexplained = round(cash_diff - sum(v for _, v in cash_items), 2) + 0.0
    cash_unexplained = 0.0 if abs(cash_unexplained) < 0.005 else cash_unexplained

    # ---- exception log
    exc = []
    action = {"Quantity mismatch": "Correct book quantity to broker confirmation", "Amount mismatch": "Rebook commission at agreed rate",
              "Duplicate in book": "Reverse duplicate booking", "Missing in book": "Book trade from broker confirmation",
              "Missing at broker": "Confirm trade with broker"}
    for _, t in tm[tm.status != "Matched"].iterrows():
        exc.append({"area": "Trade", "reference": t.trade_ref, "symbol": t.symbol, "issue": t.status,
                    "quantity_impact": t.qty_diff, "cash_impact": round(float(tb.loc[tb.trade_ref.eq(t.trade_ref) & tb.status.eq(t.status), "cash_effect"].sum()), 2),
                    "age_days": (month_end - pd.Timestamp(t.trade_date)).days, "owner": "Fund accounting", "action": action[t.status], "status": "Open"})
    for _, s in sm[sm.status != "Settled on time"].iterrows():
        pending = s.status == "Failed - pending"
        exc.append({"area": "Settlement", "reference": s.trade_ref, "symbol": s.symbol, "issue": s.status,
                    "quantity_impact": s.quantity if pending else 0, "cash_impact": s.net_amount if pending else 0,
                    "age_days": int(s.age_days) if pending else int(s.days_late), "owner": "Settlements / custodian",
                    "action": "Chase counterparty; monitor for buy-in" if pending else "None (settled); log for broker scorecard",
                    "status": "Open" if pending else "Resolved"})
    for _, c in cam[cam.status != "Matched"].iterrows():
        exc.append({"area": "Corporate action", "reference": c.ca_id, "symbol": c.symbol, "issue": f"{c.event}: {c.status}",
                    "quantity_impact": c.shares_diff, "cash_impact": c.cash_diff, "age_days": (month_end - c.pay_date).days,
                    "owner": "Corporate actions", "action": "Book entitlement per custodian" if c.status == "Not booked in book" or c.event == "Split"
                    else "Recalculate after trade breaks are corrected", "status": "Open"})
    for _, o in x["cust_other"].iterrows():
        exc.append({"area": "Cash", "reference": "FEE-OCT", "symbol": "CASH", "issue": o.description + " not booked", "quantity_impact": 0,
                    "cash_impact": -o.amount, "age_days": 0, "owner": "Fund accounting", "action": "Book fee and accrue going forward", "status": "Open"})
    exc = pd.DataFrame(exc)
    exc.insert(0, "exception_id", [f"EX{n:03d}" for n in range(1, len(exc) + 1)])

    # ---- NAV impact of open book errors (book vs corrected book)
    last_px = x["prices"].loc[month_end]
    corr = pos.set_index("symbol").quantity_book.copy()
    for _, t in tm[tm.status != "Matched"].iterrows():  # undo book trade errors
        sign = 1 if t.side == "BUY" else -1
        corr[t.symbol] -= sign * (t.qty_diff if pd.notna(t.qty_diff) else 0)
    for _, c in cam.iterrows():
        corr[c.symbol] -= c.shares_diff
    mv_book = float((pos.set_index("symbol").quantity_book * last_px).sum())
    mv_corr = float((corr * last_px).sum())
    cash_corr = bc - float(tb.cash_effect.sum()) - float(cam.cash_diff.sum()) + float(x["cust_other"].amount.sum())
    nav_book, nav_corr = mv_book + bc, mv_corr + cash_corr
    nav_bps = (nav_book - nav_corr) / nav_corr * 1e4

    # ---- outputs
    total_records = len(x["broker"]) + len(sm) + len(cam) + len(pos) + 1
    n_exc = int((exc.status == "Open").sum())
    summary = {
        "month_end": f"{month_end:%d %b %Y}",
        "trades_checked": int(len(x["broker"])), "trades_matched": int((tm.status == "Matched").sum()),
        "trade_breaks": tm[tm.status != "Matched"].status.value_counts().to_dict(),
        "settlements": sm.status.value_counts().to_dict(),
        "corporate_actions": cam.status.value_counts().to_dict(),
        "positions_checked": int(len(pos)), "position_breaks": int((pos.status != "Matched").sum()),
        "position_breaks_unexplained": int((pos.status == "Break - UNEXPLAINED").sum()),
        "cash_book": round(bc, 2), "cash_custodian": round(cc, 2), "cash_difference": cash_diff,
        "cash_explained": {k: round(v, 2) for k, v in cash_items}, "cash_unexplained": cash_unexplained,
        "negative_book_holdings": {r.symbol: float(r.quantity_book) for r in negative.itertuples()},
        "records_reconciled": int(total_records), "open_exceptions": n_exc,
        "auto_cleared_pct": round(100 * (1 - len(exc) / total_records), 1),
        "nav_book": round(nav_book, 2), "nav_corrected": round(nav_corr, 2), "nav_misstatement_bps": round(nav_bps, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    with pd.ExcelWriter(OUT / "reconciliation_workbook.xlsx") as w:
        pd.DataFrame(list(summary.items()), columns=["metric", "value"]).astype(str).to_excel(w, "Summary", index=False)
        exc.to_excel(w, "Exception log", index=False)
        tm.to_excel(w, "Trade matching", index=False)
        sm.to_excel(w, "Settlements", index=False)
        cam.to_excel(w, "Corporate actions", index=False)
        pos.to_excel(w, "Position recon", index=False)
        pd.DataFrame([("Book closing cash", bc), ("Custodian closing cash", cc), ("Difference", cash_diff), *cash_items,
                      ("Unexplained", cash_unexplained)], columns=["item", "amount"]).to_excel(w, "Cash recon", index=False)

    # charts
    fig, ax = plt.subplots(figsize=(8, 4.2))
    vc = exc.issue.value_counts().sort_values()
    ax.barh(vc.index, vc.values, color=[WINE if "Failed" in i or "Not booked" in i else ROSE for i in vc.index])
    ax.set(xlabel="Exceptions", title="Exceptions by type, October 2026 month-end")
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(OUT / "chart_exceptions.png", dpi=130, bbox_inches="tight"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.2))
    labels = ["Book cash", *[k.split(" (")[0] for k, _ in cash_items], "Custodian cash"]
    vals = [bc, *[-v for _, v in cash_items]]
    base, bottoms, heights = bc, [], []
    for v in vals[1:]:
        bottoms.append(min(base, base + v)); heights.append(abs(v)); base += v
    ax.bar(0, bc / 1e7, color=GREY)
    for i, (b, h, v) in enumerate(zip(bottoms, heights, vals[1:]), start=1):
        ax.bar(i, h / 1e7, bottom=b / 1e7, color=WINE if v < 0 else ROSE)
    ax.bar(len(vals), cc / 1e7, color=DARK)
    ax.set_xticks(range(len(labels)), labels, rotation=25, ha="right", fontsize=8)
    ax.set(ylabel="₹ crore", title="Cash reconciliation: book to custodian", ylim=(min(bc, cc) / 1e7 * 0.9, max(bc, cc) / 1e7 * 1.05))
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(OUT / "chart_cash_bridge.png", dpi=130, bbox_inches="tight"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.2))
    p = pos[pos.difference != 0].sort_values("difference")
    ax.barh(p.symbol, p.difference, color=[WINE if s.endswith("UNEXPLAINED") else ROSE for s in p.status])
    ax.axvline(0, color=DARK, lw=0.8)
    ax.set(xlabel="Book minus custodian (shares)", title="Position breaks at month-end (all explained)" if summary["position_breaks_unexplained"] == 0 else "Position breaks at month-end")
    ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(OUT / "chart_position_breaks.png", dpi=130, bbox_inches="tight"); plt.close(fig)

    show = exc.copy()
    show["cash_impact"] = show.cash_impact.map(lambda v: f"{v:,.0f}")
    report = f"""# Month-End Reconciliation Report: Aarohan Large Cap Fund

Month-end {summary['month_end']}. {summary['records_reconciled']} records checked across trades, settlements, corporate actions, positions and cash; {len(exc)} exceptions raised ({n_exc} open), {summary['auto_cleared_pct']}% cleared automatically.

| Check | Result |
|:--|:--|
| Trade matching | {summary['trades_matched']} of {summary['trades_checked']} broker confirmations matched; breaks: {', '.join(f'{k} {v}' for k, v in summary['trade_breaks'].items())} |
| Settlements | {', '.join(f'{k} {v}' for k, v in summary['settlements'].items())} |
| Corporate actions | {', '.join(f'{k} {v}' for k, v in summary['corporate_actions'].items())} |
| Positions | {summary['position_breaks']} of {summary['positions_checked']} stocks break; {summary['position_breaks_unexplained']} unexplained |
| Negative holdings control | {', '.join(f'{k}: book shows {v:,.0f} shares' for k, v in summary['negative_book_holdings'].items()) or 'none'} |
| Cash | Book ₹{bc:,.2f} vs custodian ₹{cc:,.2f}; difference ₹{cash_diff:,.2f}; unexplained ₹{cash_unexplained:,.2f} |
| NAV | Book NAV ₹{nav_book:,.0f} vs corrected ₹{nav_corr:,.0f}: misstated by **{nav_bps:+.1f} bps** until the breaks are fixed |

## Cash bridge

| Item | ₹ |
|:--|--:|
| Book closing cash | {bc:,.2f} |
| Difference (book minus custodian) | {cash_diff:,.2f} |
""" + "".join(f"| Explained by: {k} | {v:,.2f} |\n" for k, v in cash_items) + f"""| Custodian closing cash | {cc:,.2f} |
| **Unexplained** | **{cash_unexplained:,.2f}** |

## Exception log

{show.to_markdown(index=False)}
"""
    (OUT / "REPORT.md").write_text(report)
    print(report[:3000])
    return summary, exc


if __name__ == "__main__":
    main()
