"""Raw Excel -> clean, feature-enriched parquet. Used by ``prepare_data.py``."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import config as C


def map_main_category(category: str) -> str:
    """Return the main category for a raw category using the first matching keyword rule."""
    for name, keywords in C.MAIN_CATEGORY_RULES:
        if any(k in category for k in keywords):
            return name
    return C.OTHER_CATEGORY


def assign_customer_groups(revenue_by_customer: pd.Series) -> pd.Series:
    """Label customers by their revenue rank (top 10% = Key account, ... rest = Small)."""
    rank_share = revenue_by_customer.rank(ascending=False, method="first") / len(revenue_by_customer)
    bins = [0.0] + [cut for _, cut in C.CUSTOMER_GROUPS]
    labels = [name for name, _ in C.CUSTOMER_GROUPS]
    return pd.cut(rank_share, bins=bins, labels=labels, include_lowest=True).astype(str)


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Apply the cleaning rules and return the clean frame plus a log of rows removed per rule."""
    df = raw.copy()
    log: list[dict] = [{"step": "Raw rows loaded", "removed": 0, "rows_after": len(df)}]

    rules: list[tuple[str, pd.Series]] = [
        ("Quantity missing", df["Quantity"].isna()),
        ("Quantity <= 0", df["Quantity"] <= 0),
        ("NetPrice <= 0", df["NetPrice"] <= 0),
        ("UnitPrice < 0.01", df["UnitPrice"] < 0.01),
    ]
    for name, mask in rules:
        mask = mask.reindex(df.index, fill_value=False)
        removed = int(mask.sum())
        df = df[~mask]
        log.append({"step": f"Drop: {name}", "removed": removed, "rows_after": len(df)})

    dup = df.duplicated()   # keep the first copy of each exact duplicate line
    df = df[~dup]
    log.append({"step": "Drop: exact duplicate lines", "removed": int(dup.sum()), "rows_after": len(df)})

    flags = {
        "Flag (kept): NetPrice > UnitPrice": int((df["NetPrice"] > df["UnitPrice"]).sum()),
        "Fill: City missing -> UNKNOWN": int(df["City"].isna().sum()),
        "Fill: Category missing -> UNKNOWN": int(df["Category"].isna().sum()),
    }
    log += [{"step": k, "removed": 0, "rows_after": len(df), "affected": v} for k, v in flags.items()]

    df["City"] = df["City"].fillna(C.UNKNOWN_CITY)
    df["Category"] = df["Category"].fillna("UNKNOWN").str.strip()
    df["Description"] = df["Description"].astype(str).str.strip()
    df["StockCode"] = df["StockCode"].astype(str)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])
    return df.reset_index(drop=True), log


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add revenue, discount, calendar, document-series, main-category and customer-group columns."""
    df["Revenue"] = df["Quantity"] * df["NetPrice"]
    df["ListValue"] = df["Quantity"] * df["UnitPrice"]
    df["DiscountPct"] = 1 - df["NetPrice"] / df["UnitPrice"]
    df["DocSeries"] = df["InvoiceNo"].str[:3]
    df["Week"] = df["InvoiceDate"].dt.to_period("W-SUN").dt.start_time
    df["Month"] = df["InvoiceDate"].dt.to_period("M").dt.to_timestamp()

    cat_map = {c: map_main_category(c) for c in df["Category"].unique()}
    df["MainCategory"] = df["Category"].map(cat_map)

    groups = assign_customer_groups(df.groupby("CustomerID")["Revenue"].sum())
    df["CustomerGroup"] = df["CustomerID"].map(groups)
    return df


def optimise_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Store repeated strings as categoricals and floats as float32 to cut memory."""
    for col in ["InvoiceNo", "CustomerID", "StockCode", "Description", "Category", "City",
                "DocSeries", "MainCategory", "CustomerGroup"]:
        df[col] = df[col].astype("category")
    for col in ["Quantity", "NetPrice", "UnitPrice", "DiscountPct"]:
        df[col] = df[col].astype(np.float32)
    return df


def build(xlsx: Path = C.RAW_XLSX, parquet: Path = C.PARQUET, log_path: Path = C.CLEANING_LOG) -> pd.DataFrame:
    """Read the Excel file, clean it, add features and write parquet + cleaning log."""
    raw = pd.read_excel(xlsx, sheet_name="Transaction")
    df, log = clean(raw)
    df = optimise_dtypes(add_features(df))
    parquet.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet, index=False)
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    return df
