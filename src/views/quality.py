"""Tab 6 - Data & quality: cleaning log, data dictionary, filtered preview and CSV export."""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src import config as C
from src.charts import as_percent, int_col, money_col, pct_col, table
from src.data import Filters, filtered, load_data

PREVIEW_ROWS = 1_000
EXPORT_COLS = ["InvoiceNo", "CustomerID", "InvoiceDate", "StockCode", "Description", "Category", "MainCategory",
               "City", "DocSeries", "CustomerGroup", "Quantity", "NetPrice", "UnitPrice", "Revenue", "DiscountPct"]
# Pixel widths keep all 15 columns on screen at 1440px without horizontal scrolling.
PREVIEW_CONFIG = {
    "InvoiceNo": st.column_config.TextColumn("Invoice", width=74),
    "CustomerID": st.column_config.TextColumn("Customer", width=66),
    "InvoiceDate": st.column_config.DateColumn("Date", format="DD MMM YY", width=72),
    "StockCode": st.column_config.TextColumn("Code", width=92),
    "Description": st.column_config.TextColumn("Product", width=92),
    "Category": st.column_config.TextColumn("Category", width=70),
    "MainCategory": st.column_config.TextColumn("Main category", width=80),
    "City": st.column_config.TextColumn("Province", width=70),
    "DocSeries": st.column_config.TextColumn("Series", width=46),
    "CustomerGroup": st.column_config.TextColumn("Group", width=64),
    "Quantity": int_col("Qty", width=40),
    "NetPrice": money_col("Net ₺", decimals=2, width=56),
    "UnitPrice": money_col("List ₺", decimals=2, width=56),
    "Revenue": money_col("Revenue ₺", decimals=2, width=68),
    "DiscountPct": pct_col("Disc.", width=48),
}


def _cleaning_log() -> None:
    if not C.CLEANING_LOG.exists():
        st.info("Run `python prepare_data.py` to generate the cleaning log.")
        return
    log = pd.DataFrame(json.loads(C.CLEANING_LOG.read_text(encoding="utf-8")))
    raw, final = log["rows_after"].iloc[0], log["rows_after"].iloc[-1]
    c = st.columns(3)
    c[0].metric("Rows in Excel", f"{raw:,}")
    c[1].metric("Rows removed", f"{raw - final:,}")
    c[2].metric("Rows after cleaning", f"{final:,}")
    log["affected"] = log.get("affected", pd.Series(dtype=float)).fillna(log["removed"])
    table(log[["step", "affected", "rows_after"]], column_config={
        "step": st.column_config.TextColumn("Rule", width=250),
        "affected": int_col("Rows affected", width=100),
        "rows_after": int_col("Rows after", width=100)})
    st.caption("Exact duplicate lines (same invoice, customer, product, date, quantity and prices) are removed, "
               "keeping the first copy.")


def render(f: Filters) -> None:
    """Draw the data & quality tab."""
    left, right = st.columns(2)
    with left:
        st.subheader("Cleaning steps")
        _cleaning_log()
    with right:
        st.subheader("Data dictionary")
        table(pd.DataFrame(C.DATA_DICTIONARY, columns=["Column", "Type", "Description"]), height=420,
              column_config={"Column": st.column_config.TextColumn(width=110),
                             "Type": st.column_config.TextColumn(width=64),
                             "Description": st.column_config.TextColumn(width=300)})

    df = filtered(f)
    mem = load_data().memory_usage(deep=True).sum() / 1024**2
    st.subheader("Filtered data")
    st.caption(f"{len(df):,} rows match the filters · full dataset uses {mem:,.0f} MB in memory. "
               f"Preview shows the first {PREVIEW_ROWS:,} rows.")
    table(as_percent(df[EXPORT_COLS].head(PREVIEW_ROWS), "DiscountPct"), height=360, column_config=PREVIEW_CONFIG)
    st.download_button(f"Download {len(df):,} filtered rows (CSV)",
                       data=lambda: df[EXPORT_COLS].to_csv(index=False).encode("utf-8-sig"),
                       file_name="b2b_transactions_filtered.csv", mime="text/csv", on_click="ignore",
                       icon=":material/download:", help="The file is generated only when you click.")
