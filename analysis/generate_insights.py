"""
AtliQ Hardware — Sales & Finance Analysis
==========================================
Rebuilds `data/processed/dashboard_summary.json` from the raw tables in
`data/raw/`. Run this whenever the raw data changes, to refresh every
number used in the README and the interactive dashboard (docs/index.html).

Usage:
    pip install pandas
    python analysis/generate_insights.py

Notes on the source data
-------------------------
- AtliQ's fiscal year runs September -> August and is labeled by the year
  it ENDS in (FY2021 = Sep 2020 - Aug 2021). All year-over-year figures
  below use fiscal year, matching the two source reports in /reports.
- dim_market.csv leaves `region` blank for Canada and USA. Both are
  mapped to region "NA" (North America) here so every market rolls up
  into a region; this is the only enrichment made to the source data.
- `Target%` in the comparison table follows the same convention used in
  the original pivot reports: variance as a percentage of ACTUAL sales
  (actual - target) / actual, not of the target.
- dim_customer.csv and dim_product.csv are Windows-1252 encoded (a few
  customer names use accented characters, e.g. "Elkjøp"); read with
  encoding="cp1252" rather than the pandas default.
"""

import json
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT = Path(__file__).resolve().parent.parent / "data" / "processed" / "dashboard_summary.json"

DIVISION_NAMES = {
    "PC": "Personal Computers",
    "P & A": "Peripherals & Accessories",
    "N & S": "Networking & Storage",
}


def fiscal_year(date_series: pd.Series) -> pd.Series:
    """AtliQ's FY runs Sep-Aug, labeled by the calendar year it ends in."""
    return date_series.dt.year.where(date_series.dt.month <= 8, date_series.dt.year + 1)


def load_raw():
    fact = pd.read_csv(RAW / "fact_sales_monthly.csv")
    cost = pd.read_csv(RAW / "fact_sales_monthly_with_cost.csv", encoding="utf-8-sig")
    cust = pd.read_csv(RAW / "dim_customer.csv", encoding="cp1252")
    mkt = pd.read_csv(RAW / "dim_market.csv")
    prod = pd.read_csv(RAW / "dim_product.csv", encoding="cp1252")
    tgt = pd.read_csv(RAW / "ns_targets_2021.csv")

    for df in (fact, cost, tgt):
        df["date"] = pd.to_datetime(df["date"], dayfirst=True)

    mkt["region"] = mkt["region"].replace("nan", pd.NA)
    mkt.loc[mkt["market"].isin(["Canada", "USA"]), "region"] = "NA"

    return fact, cost, cust, mkt, prod, tgt


def main():
    fact, cost, cust, mkt, prod, tgt = load_raw()

    f = (
        fact.merge(cust, on="customer_code", how="left")
        .merge(prod, on="product_code", how="left")
        .merge(mkt, on="market", how="left")
    )
    f["fiscal_year"] = fiscal_year(f["date"])
    f["ym"] = f["date"].dt.to_period("M").astype(str)
    f21, f20 = f[f.fiscal_year == 2021], f[f.fiscal_year == 2020]

    c = cost.merge(cust, on="customer_code", how="left").merge(prod, on="product_code", how="left")
    c["fiscal_year"] = fiscal_year(c["date"])
    c["gross_profit"] = c["net_sales_amount"] - c["freight_cost"] - c["manufacturing_cost"]
    c21 = c[c.fiscal_year == 2021]

    data = {}
    yearly = f.groupby("fiscal_year")["net_sales_amount"].sum()

    data["kpis"] = {
        "fy21_net_sales": round(yearly[2021], 0),
        "fy20_net_sales": round(yearly[2020], 0),
        "fy19_net_sales": round(yearly[2019], 0),
        "yoy_growth_fy21": round((yearly[2021] / yearly[2020] - 1) * 100, 1),
        "yoy_growth_fy20": round((yearly[2020] / yearly[2019] - 1) * 100, 1),
        "cagr_fy19_fy21": round(((yearly[2021] / yearly[2019]) ** (1 / 2) - 1) * 100, 1),
        "gross_margin_fy21": round(c21.gross_profit.sum() / c21.net_sales_amount.sum() * 100, 1),
        "gross_profit_fy21": round(c21.gross_profit.sum(), 0),
        "markets": int(f.market.nunique()),
        "customers": int(f.customer_code.nunique()),
        "products_sold": int(f.product_code.nunique()),
        "products_catalog": int(prod.product_code.nunique()),
        "transactions": int(len(f)),
    }
    # FY2021 target coverage is added below, once `comp` (actual vs. target) exists.

    data["yearly"] = [{"fy": int(y), "net_sales": round(v, 0)} for y, v in yearly.items()]

    mt = f.groupby(["ym", "platform"])["net_sales_amount"].sum().unstack(fill_value=0).round(0)
    data["monthly"] = [
        {"ym": ym, "brick": row.get("Brick & Mortar", 0), "ecom": row.get("E-Commerce", 0)}
        for ym, row in mt.iterrows()
    ]

    reg = f21.groupby("region")["net_sales_amount"].sum().sort_values(ascending=False)
    data["region_fy21"] = [
        {"region": r, "net_sales": round(v, 0), "share_pct": round(v / reg.sum() * 100, 1)}
        for r, v in reg.items()
    ]

    div = f21.groupby("division")["net_sales_amount"].sum().sort_values(ascending=False)
    divm = c21.groupby("division").apply(lambda x: x.gross_profit.sum() / x.net_sales_amount.sum() * 100)
    data["division_fy21"] = [
        {
            "division": DIVISION_NAMES.get(d, d),
            "net_sales": round(v, 0),
            "share_pct": round(v / div.sum() * 100, 1),
            "margin_pct": round(divm[d], 1),
        }
        for d, v in div.items()
    ]

    catg = f21.groupby("category")["net_sales_amount"].sum().sort_values(ascending=False).head(8)
    data["category_fy21"] = [{"category": cat, "net_sales": round(v, 0)} for cat, v in catg.items()]

    tc = f21.groupby("market")["net_sales_amount"].sum().sort_values(ascending=False).head(10)
    data["top_countries_fy21"] = [{"market": m, "net_sales": round(v, 0)} for m, v in tc.items()]

    cust20 = f20.groupby("customer")["net_sales_amount"].sum()
    top10c = f21.groupby("customer")["net_sales_amount"].sum().sort_values(ascending=False).head(10)
    data["top_customers_fy21"] = [
        {
            "customer": cu,
            "net_sales": round(v, 0),
            "growth_pct": round((v / cust20[cu] - 1) * 100, 1) if cust20.get(cu, 0) > 0 else None,
        }
        for cu, v in top10c.items()
    ]

    plat = f21.groupby("platform")["net_sales_amount"].sum().sort_values(ascending=False)
    data["platform_fy21"] = [
        {"name": p, "net_sales": round(v, 0), "share_pct": round(v / plat.sum() * 100, 1)} for p, v in plat.items()
    ]
    chan = f21.groupby("channel")["net_sales_amount"].sum().sort_values(ascending=False)
    data["channel_fy21"] = [
        {"name": c_, "net_sales": round(v, 0), "share_pct": round(v / chan.sum() * 100, 1)} for c_, v in chan.items()
    ]

    actual21 = f21.groupby("market")["net_sales_amount"].sum()
    tgt_sum = tgt.groupby("market")["ns_target"].sum()
    comp = pd.DataFrame({"actual": actual21, "target": tgt_sum}).dropna()
    comp["variance_pct"] = (comp.actual - comp.target) / comp.actual * 100
    comp = comp.join(mkt.set_index("market")["region"]).sort_values("variance_pct")
    data["target_comp"] = [
        {
            "market": m,
            "actual": round(r.actual, 0),
            "target": round(r.target, 0),
            "variance_pct": round(r.variance_pct, 2),
            "region": r.region,
        }
        for m, r in comp.iterrows()
    ]

    my = c.groupby("fiscal_year").apply(lambda x: x.gross_profit.sum() / x.net_sales_amount.sum() * 100)
    data["margin_by_year"] = [{"fy": int(y), "margin_pct": round(v, 1)} for y, v in my.items()]

    data["kpis"]["markets_vs_target"] = int(len(comp))
    data["kpis"]["markets_below_target"] = int((comp.variance_pct < 0).sum())
    data["kpis"]["target_variance_pct"] = round((comp.actual.sum() - comp.target.sum()) / comp.actual.sum() * 100, 2)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, default=str))
    print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes)")
    print(f"FY2021 net sales: ${data['kpis']['fy21_net_sales']:,.0f}  "
          f"| YoY growth: {data['kpis']['yoy_growth_fy21']}%  "
          f"| Gross margin: {data['kpis']['gross_margin_fy21']}%")


if __name__ == "__main__":
    main()
