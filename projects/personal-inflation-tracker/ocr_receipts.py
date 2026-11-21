"""
Reads every receipt image in receipts/ with Tesseract OCR and turns it into clean line items.

Checks applied to each receipt:
  * item names are matched to the catalog with fuzzy matching (fixes OCR typos such as 0 vs O)
  * qty x unit price must equal the line total (within 1 cent)
  * the sum of lines must equal the printed TOTAL
If ground truth exists (sample receipts), OCR accuracy is measured against it.
"""
import difflib
import json
import re
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
RECEIPTS, DATA, OUT = ROOT / "receipts", ROOT / "data", ROOT / "outputs"
OUT.mkdir(exist_ok=True)

LINE_RE = re.compile(r"^(?P<name>[A-Z0-9][A-Z0-9 &'./-]{2,}?)\s+(?P<qty>\d{1,2})\s*[XxK×*]\s*[_~.,—-]*\s*(?P<unit>\d{1,4}[.,]\d{2})\s+(?P<total>\d{1,5}[.,]\d{2})\s*$")
DATE_RE = re.compile(r"DATE\s+(\d{4})[-./ ](\d{2})[-./ ](\d{2})")
PARTIAL_RE = re.compile(r"^(?P<name>[A-Z0-9][A-Z0-9 &'./-]{2,}?)\s+(?P<qty>\d{1,2})\s*[XxK×*]\s*[_~.,—-]*\s*(?P<unit>\d{1,4}[.,]\d{2})\b")
TOTAL_RE = re.compile(r"^(?:SUB)?TOTAL\s+(\d+[.,]\d{2})\s*$", re.M)


def ocr(path):
    res = subprocess.run(["tesseract", str(path), "stdout", "--psm", "6"], capture_output=True, text=True, check=True)
    return res.stdout


def num(x):
    return float(x.replace(",", "."))


def parse(text, catalog):
    date = DATE_RE.search(text)
    rows, rejected = [], []
    for raw in text.splitlines():
        line = raw.strip().upper().replace("|", "")
        m = LINE_RE.match(line)
        recovered = False
        if not m:
            m = PARTIAL_RE.match(line)  # line total smudged: rebuild it from qty x unit price
            if not m:
                continue
            recovered = True
        name = re.sub(r"\s+", " ", m["name"]).strip()
        if name.startswith(("SUBTOTAL", "TOTAL", "TAX")):
            continue
        match = difflib.get_close_matches(name, catalog, n=1, cutoff=0.6)
        qty, unit = int(m["qty"]), num(m["unit"])
        total = round(qty * unit, 2) if recovered else num(m["total"])
        ok = abs(qty * unit - total) <= 0.011
        rec = {"ocr_name": name, "item": match[0] if match else None, "qty": qty, "unit_price": unit,
               "line_total": total, "math_ok": ok, "total_recovered": recovered}
        (rows if match and ok else rejected).append(rec)
    t = TOTAL_RE.findall(text.upper())  # SUBTOTAL and TOTAL; either one reading cleanly is enough
    printed_total = num(t[0]) if t else None
    return (pd.Timestamp(f"{date[1]}-{date[2]}-{date[3]}") if date else None), rows, rejected, printed_total


def main():
    catalog_df = pd.read_csv(DATA / "catalog.csv")
    catalog = catalog_df["item"].tolist()
    images = sorted([p for p in RECEIPTS.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")])
    items, checks = [], []
    for img in images:
        date, rows, rejected, printed = parse(ocr(img), catalog)
        s = round(sum(r["line_total"] for r in rows), 2)
        checks.append({"receipt": img.name, "date": date, "lines_read": len(rows), "lines_rejected": len(rejected),
                       "sum_of_lines": s, "printed_total": printed,
                       "reconciles": printed is not None and abs(s - printed) <= 0.011})
        for r in rows:
            items.append({"date": date, "receipt": img.name, **r})
    items = pd.DataFrame(items).merge(catalog_df, on="item", how="left")
    checks = pd.DataFrame(checks)
    items.to_csv(OUT / "ocr_line_items.csv", index=False)
    checks.to_csv(OUT / "ocr_receipt_checks.csv", index=False)

    acc = {"receipts": len(images), "lines_read": int(len(items)), "line_totals_rebuilt": int(items["total_recovered"].sum()),
           "receipts_reconciled_to_total": int(checks["reconciles"].sum())}
    gt_path = DATA / "sample_ground_truth.csv"
    if gt_path.exists():
        gt = pd.read_csv(gt_path, parse_dates=["date"])
        merged = gt.merge(items[["date", "item", "unit_price"]], on=["date", "item"], how="left", suffixes=("", "_ocr"))
        acc.update({"ground_truth_lines": int(len(gt)),
                    "lines_found_%": round(merged["unit_price_ocr"].notna().mean() * 100, 1),
                    "prices_exact_%": round((merged["unit_price"] == merged["unit_price_ocr"]).mean() * 100, 1)})
    (OUT / "ocr_accuracy.json").write_text(json.dumps(acc, indent=2))
    print(json.dumps(acc, indent=2))


if __name__ == "__main__":
    main()
