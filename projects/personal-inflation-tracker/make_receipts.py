"""
Creates 24 monthly SAMPLE grocery receipts (Nov 2024 - Oct 2026) as images.

These are clearly labelled demo receipts from a fictional store, used to test the OCR pipeline.
Swap in photos of your own receipts (receipts/*.png or *.jpg) to track your real basket.
Prices start near typical US supermarket levels and drift at item-specific rates with noise.
"""
import random
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).parent
RECEIPTS = ROOT / "receipts"
DATA = ROOT / "data"
RECEIPTS.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)
random.seed(11)

# item, category, unit, starting price ($), annual drift, quantity bought each month
BASKET = [
    ("EGGS LARGE 12CT", "Dairy & eggs", "dozen", 4.10, -0.10, 2),
    ("WHOLE MILK 1GAL", "Dairy & eggs", "gallon", 4.05, 0.02, 2),
    ("BUTTER 1LB", "Dairy & eggs", "lb", 4.80, 0.04, 1),
    ("CHEDDAR 8OZ", "Dairy & eggs", "8 oz", 3.20, 0.03, 1),
    ("GROUND BEEF 1LB", "Meat", "lb", 5.60, 0.10, 2),
    ("CHICKEN BREAST 1LB", "Meat", "lb", 4.10, 0.03, 3),
    ("BANANAS 1LB", "Fruit & veg", "lb", 0.62, 0.02, 3),
    ("APPLES 1LB", "Fruit & veg", "lb", 1.75, 0.01, 2),
    ("TOMATOES 1LB", "Fruit & veg", "lb", 2.15, 0.06, 2),
    ("WHITE BREAD", "Bakery & grains", "loaf", 1.98, 0.02, 2),
    ("RICE 2LB", "Bakery & grains", "2 lb", 2.40, 0.01, 1),
    ("PASTA 1LB", "Bakery & grains", "lb", 1.45, 0.00, 2),
    ("GROUND COFFEE 12OZ", "Drinks", "12 oz", 7.20, 0.18, 1),
    ("ORANGE JUICE 52OZ", "Drinks", "52 oz", 4.40, 0.05, 1),
]
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 22)
FONT_B = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 24)
TAX_RATE = 0.0


def receipt_lines(date, items):
    lines = [("SAMPLE MART (FICTIONAL STORE)", FONT_B), ("*** SAMPLE RECEIPT - DEMO DATA ***", FONT),
             ("NOT A REAL PURCHASE", FONT), ("", FONT), (f"DATE {date:%Y-%m-%d}   STORE 0042", FONT), ("-" * 44, FONT)]
    subtotal = 0.0
    for name, qty, unit in items:
        total = round(qty * unit, 2)
        subtotal += total
        lines.append((f"{name:<20}{qty:>2} X {unit:>6.2f}{total:>10.2f}", FONT))
    lines += [("-" * 44, FONT), (f"{'SUBTOTAL':<34}{subtotal:>10.2f}", FONT),
              (f"{'TAX':<34}{subtotal * TAX_RATE:>10.2f}", FONT), (f"{'TOTAL':<34}{subtotal:>10.2f}", FONT_B),
              ("", FONT), ("THANK YOU - SAMPLE DATA ONLY", FONT)]
    return lines, round(subtotal, 2)


def render(lines, path):
    w, lh = 640, 34
    img = Image.new("L", (w, 60 + lh * len(lines)), 250)
    d = ImageDraw.Draw(img)
    for i, (text, font) in enumerate(lines):
        d.text((24, 30 + i * lh), text, fill=random.randint(10, 45), font=font)
    img = img.rotate(random.uniform(-1.2, 1.2), expand=True, fillcolor=250, resample=Image.BICUBIC)
    img = img.filter(ImageFilter.GaussianBlur(random.uniform(0.3, 0.7)))
    img.save(path)


def main():
    months = pd.date_range("2024-11-01", "2026-10-01", freq="MS")
    truth = []
    for m, month in enumerate(months):
        date = month + pd.Timedelta(days=random.randint(3, 25))
        items = []
        for name, cat, unit_label, p0, drift, qty in BASKET:
            seasonal = 0.04 if name.startswith(("TOMATOES", "APPLES")) and month.month in (1, 2, 3) else 0.0
            price = p0 * (1 + drift) ** (m / 12) * (1 + seasonal) * random.uniform(0.97, 1.03)
            if name.startswith("EGGS") and m < 5:
                price *= 1.35 - 0.07 * m  # early-2025 egg price spike, then normalising
            price = round(price, 2)
            items.append((name, qty, price))
            truth.append({"date": date.date(), "item": name, "category": cat, "unit": unit_label,
                          "qty": qty, "unit_price": price})
        lines, total = receipt_lines(date, items)
        render(lines, RECEIPTS / f"SAMPLE_receipt_{date:%Y_%m_%d}.png")
    pd.DataFrame(truth).to_csv(DATA / "sample_ground_truth.csv", index=False)
    pd.DataFrame([(n, c, u) for n, c, u, *_ in BASKET], columns=["item", "category", "unit"]).to_csv(DATA / "catalog.csv", index=False)
    print(f"{len(months)} sample receipts written to receipts/")


if __name__ == "__main__":
    main()
