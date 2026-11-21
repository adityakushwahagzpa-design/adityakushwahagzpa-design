"""Price download with yfinance, plus an offline test mode.

Set OFFLINE=1 to replace downloads with simulated prices (used only to test the
code without internet). Published results always come from real Yahoo Finance data.
"""
import os

import numpy as np
import pandas as pd

OFFLINE = os.environ.get("OFFLINE") == "1"


def _simulated(tickers, start, end, freq="B"):
    idx = pd.bdate_range(start or "2015-01-01", end or pd.Timestamp.today().normalize(), freq=freq)
    rng = np.random.default_rng(42)
    common = rng.normal(0.0004, 0.010, len(idx))
    out = {}
    for i, t in enumerate(tickers):
        beta = 0.6 + 0.08 * i
        r = beta * common + rng.normal(0.0001 * (i % 5), 0.012, len(idx))
        out[t] = 100 * np.exp(np.cumsum(r))
    return pd.DataFrame(out, index=idx)


def prices(tickers, start=None, end=None, period=None, min_obs=200):
    """Adjusted close prices, one column per ticker. Retries failed tickers one by one."""
    tickers = list(tickers)
    if OFFLINE:
        return _simulated(tickers, start, end)
    import yfinance as yf

    kw = dict(auto_adjust=True, progress=False)
    kw.update({"period": period} if period else {"start": start, "end": end})
    px = yf.download(tickers, threads=True, **kw)["Close"]
    if isinstance(px, pd.Series):
        px = px.to_frame(tickers[0])
    px.index = pd.to_datetime(px.index).tz_localize(None)
    for t in tickers:
        if t not in px or px[t].dropna().shape[0] < min_obs:
            one = yf.download(t, **kw)["Close"].squeeze()
            if len(one.dropna()) >= min_obs:
                one.index = pd.to_datetime(one.index).tz_localize(None)
                px[t] = one
    keep = [t for t in tickers if t in px and px[t].dropna().shape[0] >= min_obs]
    return px[keep].dropna(how="all")
