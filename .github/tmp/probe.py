import requests
UA={"User-Agent":"Insider Radar Research Project research@example.org"}
r=requests.head("https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/2026q3_form345.zip",headers=UA,timeout=60); print("SEC zip 2026q3", r.status_code, r.headers.get("content-length"))
r=requests.head("https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/2025q4_form345.zip",headers=UA,timeout=60); print("SEC zip 2025q4", r.status_code)
r=requests.get("https://data.sec.gov/submissions/CIK0000320193.json",headers=UA,timeout=60); print("SEC submissions", r.status_code, r.json().get("name") if r.ok else r.text[:200])
r=requests.post("https://api.bls.gov/publicAPI/v1/timeseries/data/",json={"seriesid":["CUUR0000SAF11"],"startyear":"2024","endyear":"2026"},timeout=60)
j=r.json(); print("BLS", j.get("status"), [(d["year"],d["period"],d["value"]) for d in j["Results"]["series"][0]["data"][:3]] if j.get("status")=="REQUEST_SUCCEEDED" else j)
from huggingface_hub import HfApi
api=HfApi()
for rid in ["jlh-ibm/earnings_call","kurry/sp500_earnings_transcripts","Bose345/sp500_earnings_transcripts","lamini/earnings-calls-qa","glopardo/sp500-earnings-transcripts"]:
    try:
        fs=api.list_repo_files(rid, repo_type="dataset"); print("HF", rid, len(fs), fs[:12])
    except Exception as e: print("HF", rid, "ERR", str(e)[:120])
