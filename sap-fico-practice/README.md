# SAP FICO Practice Workbook – GL, AP/AR & Cost Centre Accounting

A month of SAP FI and CO postings built in Excel to show how a document flows from entry to the ledger, subledgers and controlling reports.

**Practice company:** Kushwaha Industries Pvt Ltd (fictional) · Company code 1000 · Controlling area A000 · Period 7, October 2026 · INR

📥 [Download the workbook](SAP_FICO_Practice_Workbook.xlsx)

## What it covers

| Sheet | SAP equivalent | T-code |
|---|---|---|
| Org_Structure | Company code, controlling area, fiscal year variant V3 (Apr–Mar) | OX02 / OKKP / OB29 |
| GL_Master | Chart of accounts, GL master, cost elements | FS00 / KA01 |
| Posting_Keys | Keys 01, 15, 25, 31, 40, 50 – debit/credit and account type | OB41 |
| Vendors_Customers | Vendor and customer master with reconciliation accounts | XK01 / XD01 |
| Cost_Centres | 5 cost centres under a standard hierarchy | KS01 / OKEON |
| Journal | 19 documents: GL entries, vendor and customer invoices with 18% GST, payments, receipts, depreciation | FB50 / FB60 / FB70 / F-53 / F-28 / AFAB |
| Doc_Check | Debit = credit check for each document | FB03 |
| Trial_Balance | GL balances for the period | S_ALR_87012277 / FS10N |
| Vendor_Open_Items | Vendor invoices, payments, open balance; ties to AP recon account | FBL1N |
| Customer_Open_Items | Customer invoices, receipts, open balance; ties to AR recon account | FBL5N |
| CC_Plan_vs_Actual | Cost centre plan, actual and variance | KP06 / S_ALR_87013611 |
| Internal_Order | Diwali campaign order: budget vs actual | KO01 / S_ALR_87013019 |
| PL_GST | Profit & loss and net GST position | F.01 |

## How it works

- Each journal line carries a **posting key**. The key sets debit or credit and the account type (GL, vendor or customer), as in SAP.
- Vendor and customer lines post automatically to their **reconciliation accounts** (200000 Trade Payables, 110000 Trade Receivables), so the subledger and GL always agree.
- Expense lines carry a **cost centre** (and an internal order where relevant), which feeds the CO reports.
- All reports are formulas (764 in total). Add a journal line and every sheet updates.

## Results for October 2026

- **19 of 19 documents balanced**; trial balance totals ₹2,17,05,600 on both sides.
- **Subledger checks pass:** vendor open items ₹4,75,000 (BESCOM, Adfactors Media) and customer open items ₹16,78,000 (Urban Mart part paid, Apex Distributors open) both match their recon accounts.
- **Cost centres:** actual ₹34,65,000 vs plan ₹33,45,000, **3.6% over plan**. Production is ₹70,000 over (raw material +8.3%, power +15.4%); IT is ₹15,000 under.
- **Internal order 700001:** ₹2,90,000 spent against a ₹2,75,000 budget, **105% used**, so a budget supplement would be needed.
- **P&L:** revenue ₹36,00,000, net profit ₹1,35,000 (3.8% margin). **Net GST payable** ₹3,94,200 after ₹2,53,800 input credit.

## Colour code

Blue text = inputs and master data · black = formulas · green = links from another sheet.

> This is a practice model built in Excel to show how SAP FI and CO postings flow. It is not output from a live SAP system. Concepts are from the *SAP FICO for Finance Professionals* course (Great Learning, Nov 2026).
