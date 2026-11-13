"""B2B Sales Intelligence Dashboard — entry point.  Run:  streamlit run streamlit_app.py"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="B2B Sales Intelligence", page_icon=":material/insights:", layout="wide")

from src import config as C  # noqa: E402  (page config must come first)
from src import theme as T  # noqa: E402
from src.charts import province, turkish_sort_key  # noqa: E402
from src.data import Filters, date_bounds, filtered, load_data  # noqa: E402
from src.views import customers, executive, forecasting, quality, sales, supply  # noqa: E402

TABS = [
    ("Executive Summary", executive.render),
    ("Sales Performance", sales.render),
    ("Customers & Marketing", customers.render),
    ("Supply Chain", supply.render),
    ("Forecasting & Models", forecasting.render),
    ("Data & Quality", quality.render),
]


def sidebar_filters() -> Filters:
    """Draw the sidebar and return the current selection (empty multiselect = all)."""
    df = load_data()
    first, last = date_bounds()
    with st.sidebar:
        st.header("Filters")
        picked = st.date_input("Date range", (first, last), min_value=first, max_value=last, format="DD.MM.YYYY",
                               key="f_dates")
        start, end = (picked if isinstance(picked, tuple) and len(picked) == 2 else (first, last))
        cats = st.multiselect("Main category", C.MAIN_CATEGORIES, placeholder="All", key="f_cats")
        cities = st.multiselect("Province", sorted(df["City"].cat.categories, key=lambda c: turkish_sort_key(province(c))),
                                format_func=province, placeholder="All", key="f_cities")
        series = st.multiselect("Document series", C.DOC_SERIES, placeholder="All", key="f_series")
        groups = st.multiselect("Customer group", [g for g, _ in C.CUSTOMER_GROUPS], placeholder="All",
                                key="f_groups", help="Derived from full-year revenue rank (top 10% = Key account).")
        st.divider()
        st.caption("B2B book & puzzle distributor, Turkey · 2020 · 664K invoice lines")
    return Filters(start, end, tuple(cats), tuple(cities), tuple(series), tuple(groups))


def main() -> None:
    """Render the header, filters and tabs."""
    st.markdown(T.CSS, unsafe_allow_html=True)
    st.title("B2B Sales Intelligence Dashboard")
    f = sidebar_filters()
    rows = len(filtered(f))
    if rows == 0:
        st.warning("No transactions match these filters. Widen the date range or clear a filter.",
                   icon=":material/filter_alt_off:")
        st.stop()
    st.caption(f"{f.start:%d %b %Y} – {f.end:%d %b %Y} · {rows:,} invoice lines selected")
    for tab, (_, render) in zip(st.tabs([name for name, _ in TABS]), TABS):
        with tab:
            render(f)


main()
