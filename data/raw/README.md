# Raw Dataset Files

This folder contains the source CSV datasets used for the AtliQ Hardware Sales & Finance Analysis.

## Files in this folder

| File | Size | Status |
|------|------|--------|
| `dim_customer.csv` | ~10KB | ✅ Included |
| `dim_market.csv` | ~1KB | ✅ Included |
| `dim_product.csv` | ~20KB | ✅ Included |
| `ns_targets_2021.csv` | ~8KB | ✅ Included |
| `fact_sales_monthly.csv` | **37MB** | ⚠️ Large file — see below |
| `fact_sales_monthly_with_cost.csv` | **45MB** | ⚠️ Large file — see below |

## Downloading Large Files

The two fact tables exceed GitHub's file size limit for standard tracking.

**Option 1 — Codebasics Resource Centre:**
Download the original datasets from the [Codebasics Data Analytics Bootcamp](https://codebasics.io) resource centre where this project originates.

**Option 2 — Excel Workbook:**
The Excel workbook in `/excel/AtliQ_Hardware_Sales_Finance_Analysis.xlsx` already contains the data loaded via Power Query — you don't need the raw CSVs to use it.

**Option 3 — Git LFS:**
If you clone this repo and want to track large files, install [Git LFS](https://git-lfs.github.com/) and run:
```bash
git lfs install
git lfs track "*.csv"
```