"""Nifty 50 constituents (NSE symbols for yfinance) with sectors. List as of late 2025; symbols
that yfinance cannot find are skipped and reported by each script."""

NIFTY50 = {
    "ADANIENT": "Metals & Mining", "ADANIPORTS": "Services", "APOLLOHOSP": "Healthcare", "ASIANPAINT": "Consumer",
    "AXISBANK": "Financials", "BAJAJ-AUTO": "Auto", "BAJFINANCE": "Financials", "BAJAJFINSV": "Financials",
    "BEL": "Capital Goods", "BHARTIARTL": "Telecom", "CIPLA": "Healthcare", "COALINDIA": "Energy",
    "DRREDDY": "Healthcare", "EICHERMOT": "Auto", "ETERNAL": "Consumer Services", "GRASIM": "Materials",
    "HCLTECH": "IT", "HDFCBANK": "Financials", "HDFCLIFE": "Financials", "HINDALCO": "Metals & Mining",
    "HINDUNILVR": "FMCG", "ICICIBANK": "Financials", "INDIGO": "Services", "INFY": "IT", "ITC": "FMCG",
    "JIOFIN": "Financials", "JSWSTEEL": "Metals & Mining", "KOTAKBANK": "Financials", "LT": "Capital Goods",
    "M&M": "Auto", "MARUTI": "Auto", "MAXHEALTH": "Healthcare", "NESTLEIND": "FMCG", "NTPC": "Energy",
    "ONGC": "Energy", "POWERGRID": "Energy", "RELIANCE": "Energy", "SBILIFE": "Financials", "SBIN": "Financials",
    "SHRIRAMFIN": "Financials", "SUNPHARMA": "Healthcare", "TATACONSUM": "FMCG", "TMPV": "Auto",
    "TATASTEEL": "Metals & Mining", "TCS": "IT", "TECHM": "IT", "TITAN": "Consumer", "TRENT": "Consumer",
    "ULTRACEMCO": "Materials", "WIPRO": "IT",
}
INDEX = "^NSEI"


def yf_symbol(s):
    return s + ".NS"
