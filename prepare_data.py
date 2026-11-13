"""Convert the raw Excel file into ``data/transactions.parquet`` for the dashboard.

Run once (takes about a minute):  python prepare_data.py
"""
from __future__ import annotations

import time

from src import config as C
from src.prep import build


def main() -> None:
    """Build the parquet file and print a short summary."""
    t0 = time.perf_counter()
    df = build()
    mem_mb = df.memory_usage(deep=True).sum() / 1024**2
    print(f"Wrote {C.PARQUET.relative_to(C.ROOT)} in {time.perf_counter() - t0:.0f}s")
    print(f"Rows: {len(df):,} | Revenue: {df['Revenue'].sum():,.0f} | "
          f"Customers: {df['CustomerID'].nunique():,} | In-memory size: {mem_mb:.0f} MB")
    print(f"Parquet size: {C.PARQUET.stat().st_size / 1024**2:.1f} MB")


if __name__ == "__main__":
    main()
