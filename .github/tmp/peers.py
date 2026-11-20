import yfinance as yf, json, pandas as pd
cands=["NAM-INDIA.NS","HDFCAMC.NS","ICICIAMC.NS","ICICIPRAMC.NS","IPRUAMC.NS","ABSLAMC.NS","UTIAMC.NS","CRAMC.NS","CANARAROBE.NS","SBIFUNDS.NS","SBIAMC.NS","SBIMF.NS","360ONE.NS","^NSEI"]
keys=["shortName","currentPrice","previousClose","marketCap","sharesOutstanding","trailingPE","forwardPE","priceToBook","returnOnEquity","netIncomeToCommon","totalRevenue","profitMargins","dividendRate","trailingEps","beta","fiftyTwoWeekHigh","fiftyTwoWeekLow","bookValue"]
out={}
for t in cands:
    try:
        i=yf.Ticker(t).info
        if i and (i.get("currentPrice") or i.get("regularMarketPrice")):
            out[t]={k:i.get(k) for k in keys}
    except Exception as e: pass
print("PEERS_JSON="+json.dumps(out))
h=yf.Ticker("NAM-INDIA.NS").history(period="2y",auto_adjust=False)["Close"]
n=yf.Ticker("^NSEI").history(period="2y")["Close"]
w=pd.concat([h.rename("NAM"),n.rename("NIFTY")],axis=1).ffill().dropna().resample("W-FRI").last()
print("HIST_CSV_START"); print(w.round(2).to_csv()); print("HIST_CSV_END")
print("LAST", h.index[-1], h.iloc[-1])
