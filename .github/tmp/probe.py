import pandas as pd
from huggingface_hub import hf_hub_download
for rid, f in [("kurry/sp500_earnings_transcripts","parquet_files/part-0.parquet"),("glopardo/sp500-earnings-transcripts","data/train-00000-of-00003.parquet")]:
    try:
        p=hf_hub_download(rid, f, repo_type="dataset"); d=pd.read_parquet(p)
        print("HF", rid, d.shape, list(d.columns))
        for c in d.columns:
            if any(k in c.lower() for k in ["date","year","quarter"]): print("HF", rid, c, d[c].min(), d[c].max())
        row=d.iloc[0]
        for c in d.columns:
            v=row[c]; s=str(v)[:300].replace("\n"," | "); print("HF", rid, "COL", c, type(v).__name__, s)
        if "symbol" in d.columns: print("HF", rid, "symbols", d["symbol"].nunique())
    except Exception as e: print("HF", rid, "ERR", str(e)[:200])
