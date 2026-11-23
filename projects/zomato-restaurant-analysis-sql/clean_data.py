"""
Cleans the raw Zomato file and splits it into three tables for PostgreSQL.

  data/raw/zomato.csv        9,551 restaurants (Kaggle "Zomato Restaurants Data")
  data/raw/Country-Code.xlsx country code -> country name

Output (data/):
  countries.csv            country_code, country, currency
  restaurants.csv          one row per restaurant
  restaurant_cuisines.csv  one row per restaurant and cuisine (the source keeps them in one text field)

Cleaning steps
  - Yes/No flags become booleans; column names become snake_case.
  - A rating of 0 means "Not rated" in the source. It is stored as NULL so averages are not dragged down.
  - An average cost of 0 is stored as NULL (18 restaurants, no price listed).
  - Cuisines are split on commas and trimmed; 9 restaurants with no cuisine get none.
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
RAW = HERE / "data" / "raw"
OUT = HERE / "data"


def main():
    df = pd.read_csv(RAW / "zomato.csv", encoding="latin-1")
    cc = pd.read_excel(RAW / "Country-Code.xlsx")

    flag = {"Yes": True, "No": False}
    r = pd.DataFrame({
        "restaurant_id": df["Restaurant ID"],
        "restaurant_name": df["Restaurant Name"].str.strip(),
        "country_code": df["Country Code"],
        "city": df["City"].str.strip(),
        "locality": df["Locality"].str.strip(),
        "longitude": df["Longitude"],
        "latitude": df["Latitude"],
        "avg_cost_for_two": df["Average Cost for two"].where(df["Average Cost for two"] > 0),
        "has_table_booking": df["Has Table booking"].map(flag),
        "has_online_delivery": df["Has Online delivery"].map(flag),
        "price_range": df["Price range"],
        "aggregate_rating": df["Aggregate rating"].where(df["Aggregate rating"] > 0),
        "rating_text": df["Rating text"],
        "votes": df["Votes"],
    })
    r["avg_cost_for_two"] = r["avg_cost_for_two"].astype("Int64")

    cur = df.groupby("Country Code")["Currency"].first().rename("currency").reset_index()
    countries = cc.rename(columns={"Country Code": "country_code", "Country": "country"}).merge(
        cur.rename(columns={"Country Code": "country_code"}), on="country_code", how="left")

    cuis = (df[["Restaurant ID", "Cuisines"]].dropna()
            .assign(cuisine=lambda d: d["Cuisines"].str.split(","))
            .explode("cuisine"))
    cuis["cuisine"] = cuis["cuisine"].str.strip()
    cuis = (cuis[cuis["cuisine"] != ""]
            .rename(columns={"Restaurant ID": "restaurant_id"})[["restaurant_id", "cuisine"]]
            .drop_duplicates())

    countries.to_csv(OUT / "countries.csv", index=False)
    r.to_csv(OUT / "restaurants.csv", index=False)
    cuis.to_csv(OUT / "restaurant_cuisines.csv", index=False)
    print(f"countries {len(countries)}, restaurants {len(r)}, restaurant_cuisines {len(cuis)}")
    print(f"not rated -> NULL: {r['aggregate_rating'].isna().sum()}, cost 0 -> NULL: {r['avg_cost_for_two'].isna().sum()}")


if __name__ == "__main__":
    main()
