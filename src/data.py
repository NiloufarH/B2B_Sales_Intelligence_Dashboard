"""Data loading and filtering. The base frame and filtered views are cached as shared resources."""
from __future__ import annotations

from datetime import date, timedelta
from typing import NamedTuple

import pandas as pd
import streamlit as st

from src import config as C


class Filters(NamedTuple):
    """Hashable sidebar selection. Empty tuples mean 'all'."""
    start: date
    end: date
    categories: tuple[str, ...] = ()
    cities: tuple[str, ...] = ()
    series: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()


@st.cache_resource(show_spinner="Loading transactions…")
def load_data() -> pd.DataFrame:
    """Load the prepared parquet (building it from the Excel file on first run if missing).

    ``cache_resource`` keeps one shared copy in memory instead of unpickling ~50 MB on every
    rerun, which is what makes filter changes feel instant. Callers must not mutate it.
    """
    if not C.PARQUET.exists():
        from src.prep import build
        build()
    return pd.read_parquet(C.PARQUET)


@st.cache_resource(max_entries=16, show_spinner=False)
def filtered(f: Filters) -> pd.DataFrame:
    """Return the rows matching the filters (read-only view shared across reruns)."""
    df = load_data()
    mask = df["InvoiceDate"].between(pd.Timestamp(f.start), pd.Timestamp(f.end))
    for col, values in (("MainCategory", f.categories), ("City", f.cities),
                        ("DocSeries", f.series), ("CustomerGroup", f.groups)):
        if values:
            mask &= df[col].isin(values)
    return df.loc[mask]


def date_bounds() -> tuple[date, date]:
    """First and last invoice date in the data."""
    d = load_data()["InvoiceDate"]
    return d.min().date(), d.max().date()


def previous_period(f: Filters) -> Filters | None:
    """Same-length window immediately before the selected one, or None if it is outside the data."""
    first, _ = date_bounds()
    length = (f.end - f.start).days + 1
    prev_end = f.start - timedelta(days=1)
    if prev_end < first:
        return None
    return f._replace(start=max(first, prev_end - timedelta(days=length - 1)), end=prev_end)


def full_week_range(f: Filters) -> pd.DatetimeIndex:
    """Mondays of the weeks that lie completely inside the selected date range."""
    start = pd.Timestamp(f.start)
    first_monday = start + pd.Timedelta(days=(7 - start.weekday()) % 7)
    last_monday = pd.Timestamp(f.end) - pd.Timedelta(days=6)
    return pd.date_range(first_monday, last_monday, freq="W-MON")
