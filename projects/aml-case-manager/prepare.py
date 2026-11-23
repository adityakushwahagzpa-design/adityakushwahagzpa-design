"""
Prepares the raw transfers for the graph.

  - Checks the header has the 11 IBM columns, then renames them (the raw file has two columns called "Account").
  - Gives every account one ID made of bank + account number, because the same account number can exist at two banks.
  - Converts timestamps to ISO format and amounts to US dollars, so amounts in different currencies are never added up.

Writes data/accounts.csv and data/transfers.csv (one row per transfer, with transfer_id = row number in the raw file).
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
DATA = HERE / "data"
USD_RATE = {"US Dollar": 1.0, "Euro": 1.08, "UK Pound": 1.27, "Indian Rupee": 0.012, "Yuan": 0.14, "Yen": 0.0067,
            "Swiss Franc": 1.13, "Australian Dollar": 0.66, "Canadian Dollar": 0.73, "Saudi Riyal": 0.27,
            "Bitcoin": 60000.0, "Ruble": 0.011, "Mexican Peso": 0.055, "Brazil Real": 0.18, "Shekel": 0.27}


def main(path=DATA / "HI-Small-style_Trans.csv.gz"):
    df = pd.read_csv(path)
    assert len(df.columns) == 11, f"expected 11 columns, got {len(df.columns)}"     # check the header first
    df.columns = ["ts", "from_bank", "from_acc", "to_bank", "to_acc", "amount_rec",
                  "cur_rec", "amount_paid", "cur_paid", "format", "is_laundering"]
    df["src"] = df.from_bank.astype(str) + "_" + df.from_acc.astype(str)
    df["dst"] = df.to_bank.astype(str) + "_" + df.to_acc.astype(str)
    df["ts"] = pd.to_datetime(df.ts, format="%Y/%m/%d %H:%M").dt.strftime("%Y-%m-%dT%H:%M:%S")
    unknown = set(df.cur_paid) - set(USD_RATE)
    assert not unknown, f"no USD rate for {unknown}"
    df["amount_usd"] = (df.amount_paid * df.cur_paid.map(USD_RATE)).round(2)
    df["transfer_id"] = range(len(df))
    df = df[df.src != df.dst]                                          # self-transfers are not graph edges
    df[["transfer_id", "src", "dst", "ts", "amount_usd", "cur_paid", "format", "is_laundering"]].to_csv(DATA / "transfers.csv", index=False)
    accounts = pd.DataFrame({"id": pd.unique(pd.concat([df.src, df.dst]))})
    accounts["bank"] = accounts.id.str.split("_").str[0]
    accounts.to_csv(DATA / "accounts.csv", index=False)
    print(f"{len(df):,} transfers, {len(accounts):,} accounts, {int(df.is_laundering.sum())} laundering")


if __name__ == "__main__":
    main()
