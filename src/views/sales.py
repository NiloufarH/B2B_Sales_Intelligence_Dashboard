"""Tab 2 - Sales performance: geography, categories, best sellers, series/groups, discounts, calendar."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import analytics as A
from src import theme as T
from src.charts import (H_LG, H_SM, as_percent, explain, format_axis, heatmap, hbar, histogram, hover_value,
                        int_col, lines, money, money_col, pct, province, share_col, show, table)
from src.data import Filters, filtered


DAY_NAMES = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday",
             "Sat": "Saturday", "Sun": "Sunday"}


def _geography(f: Filters) -> None:
    city = A.city_summary(f)
    city = city.assign(Name=city["City"].map(province))
    mapped = city.dropna(subset=["lat"])
    left, right = st.columns([3, 2])
    with left:
        fig = go.Figure(go.Scattergeo(
            lat=mapped["lat"], lon=mapped["lon"], text=mapped["Name"],
            marker=dict(size=mapped["Revenue"], sizemode="area", sizeref=2 * mapped["Revenue"].max() / 55 ** 2,
                        sizemin=3, color=T.ACCENT, opacity=0.65, line=dict(color=T.SURFACE, width=1)),
            customdata=mapped[["Revenue", "Share", "Customers"]],
            hovertemplate=f"%{{text}}<br>Revenue: {hover_value('money', 'customdata[0]')} (%{{customdata[1]:.1%}})"
                          "<br>Customers: %{customdata[2]:,}<extra></extra>"))
        fig.update_geos(fitbounds="locations", showcountries=True, showland=True, showocean=True,
                        showframe=False, resolution=50, projection_type="mercator")
        top = city.iloc[0]
        fig.update_layout(title=f"{top['Name']} dominates with {pct(top['Share'])} of revenue",
                          height=H_LG, margin=dict(l=8, r=8, t=56, b=8))
        show(fig)
    with right:
        top15 = city.head(15)
        show(hbar(top15, "Revenue", "Name", f"Top 15 provinces = {pct(top15['Share'].sum())} of revenue",
                  text=top15["Share"].map(pct), height=H_LG))
    top, rest = city.iloc[0], city.iloc[1:]
    if rest["Share"].sum() < top["Share"]:
        main = f"{top['Name']} brings {pct(top['Share'])} of revenue, more than all other provinces combined."
    else:
        k = int((rest["Share"].cumsum() < top["Share"]).sum()) + 1
        main = f"{top['Name']} brings {pct(top['Share'])} of revenue, as much as the next {k} provinces combined."
    notable = (f"The top 15 provinces make {pct(top15['Share'].sum())} of revenue; the other {len(city) - 15} "
               f"share the remaining {pct(1 - top15['Share'].sum())}." if len(city) > 15 else None)
    explain("Net revenue by customer province; bubble area = revenue. Lines without a province are left off "
            "the map but counted in the shares.", main, notable)


def _categories(f: Filters) -> pd.DataFrame:
    cats = A.category_summary(f).head(20)
    colors = [T.CATEGORY_COLORS.get(str(m), T.NEUTRAL) for m in cats["MainCategory"]]
    fig = hbar(cats, "Revenue", "Category", f"Top 20 categories: '{cats.iloc[0]['Category']}' leads",
               color=colors, text=cats["Share"].map(pct))
    fig.update_traces(showlegend=False, selector=dict(type="bar"))   # no stray "trace 0" entry
    for m in [m for m in T.CATEGORY_COLORS if m in set(cats["MainCategory"].astype(str))]:
        fig.add_scatter(x=[None], y=[None], mode="markers", name=m, showlegend=True, hoverinfo="skip",
                        marker=dict(size=10, symbol="square", color=T.CATEGORY_COLORS[m]))
    fig.update_layout(showlegend=True)
    show(fig)
    return cats


def _best_sellers(f: Filters) -> pd.DataFrame:
    n = st.slider("Number of products", 10, 100, 20, step=5, key="best_n")
    top = A.best_sellers(f, n)
    view = as_percent(top[["Description", "Category", "Revenue", "Units", "Customers", "Share"]], "Share")
    table(view, height=min(35 * (n + 1) + 3, 563), column_config={
        # Pixel widths keep the table inside its half-width column at 1366px and up.
        "Description": st.column_config.TextColumn("Product", width=124),
        "Category": st.column_config.TextColumn("Category", width=88),
        "Revenue": money_col("Revenue (₺)", width=78),
        "Units": int_col("Units", width=52),
        "Customers": int_col("Customers", width=70),
        "Share": share_col("Share", float(view["Share"].max()) if len(view) else 100.0, width=72),
    })
    return top


def _series_and_groups(f: Filters) -> None:
    left, right = st.columns(2)
    with left:
        m = A.monthly_by(f, "DocSeries")
        ser = m.groupby("DocSeries", observed=True)["Revenue"].sum()
        lead = ser.idxmax() if len(ser) else ""
        show(lines(m, "Month", "Revenue", "DocSeries", f"Monthly revenue by document series — {lead} leads",
                   T.DOC_SERIES_COLORS))
    with right:
        m = A.monthly_by(f, "CustomerGroup")
        share = m.groupby("CustomerGroup", observed=True)["Revenue"].sum()
        title = (f"Key accounts bring {pct(share.get('Key account', 0) / share.sum())} of revenue"
                 if share.sum() else "Monthly revenue by customer group")
        show(lines(m, "Month", "Revenue", "CustomerGroup", title, T.GROUP_COLORS))
    df = filtered(f)
    n_key = df.loc[df["CustomerGroup"] == "Key account", "CustomerID"].nunique()
    main = notable = None
    if len(ser) and share.sum():
        main = (f"{lead} is the largest document series ({pct(ser.max() / ser.sum())} of revenue), and "
                f"{n_key:,} key-account customers bring {pct(share.get('Key account', 0) / share.sum())}.")
        tot = m.groupby("Month")["Revenue"].sum()
        notable = (f"Revenue is lowest in {tot.idxmin():%B} and highest in {tot.idxmax():%B} "
                   f"({money(tot.max())}).")
    explain("Monthly revenue by invoice document series (the prefixes' meaning isn't documented) and by customer "
            "group (Key account = top 10% of customers by full-year revenue, then Large 20%, Medium 30%, Small 40%).",
            main, notable)


def _discounts(f: Filters) -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        d = filtered(f)["DiscountPct"]
        show(histogram(d, f"Median line discount: {pct(d.median())}", bins=40, range_=(0, 0.8), x_fmt=".0%",
                       x_title="Discount"))
    with c2:
        g = A.discount_by(f, "MainCategory").sort_values("Discount", ascending=False)
        colors = [T.CATEGORY_COLORS.get(str(m), T.NEUTRAL) for m in g["MainCategory"]]
        show(hbar(g, "Discount", "MainCategory", "Discount by main category", color=colors,
                  text=g["Discount"].map(pct), kind="pct", height=H_SM))
    with c3:
        g = A.discount_by_order_size(f)
        fig = go.Figure(go.Bar(x=g["Band"].astype(str), y=g["Discount"], marker_color=T.BLUE,
                               marker_line_color=T.BLUE, text=g["Discount"].map(pct), textposition="outside",
                               cliponaxis=False, customdata=g["Invoices"],
                               hovertemplate="%{x} ₺: %{y:.1%} (%{customdata:,} invoices)<extra></extra>"))
        fig.update_layout(title="Discount by invoice value", height=H_SM, xaxis_title="Invoice net value (₺)")
        format_axis(fig, "pct")
        show(fig)
    cat = A.discount_by(f, "MainCategory").sort_values("Discount", ascending=False)
    small, large = (g["Discount"].iloc[0], g["Discount"].iloc[-1]) if len(g) else (0.0, 0.0)
    main = f"The median invoice line gets {pct(d.median())} off list price."
    if len(cat) >= 2:
        hi, lo = cat.iloc[0], cat.iloc[-1]
        main += (f" {hi['MainCategory']} gets the deepest discount ({pct(hi['Discount'])}) and "
                 f"{lo['MainCategory']} the lowest ({pct(lo['Discount'])}).")
    if abs(large - small) < 0.02:
        notable = (f"Invoice size barely changes the discount: {pct(small)} on the smallest invoices vs "
                   f"{pct(large)} on the largest.")
    else:
        notable = (f"Larger invoices get {'more' if large > small else 'less'} off: {pct(large)} on the largest "
                   f"vs {pct(small)} on the smallest.")
    explain("Discount = 1 − net price ÷ list price, per invoice line (left) and revenue-weighted by main category "
            "and invoice size.", main, notable)


def _calendar(f: Filters) -> None:
    p = A.weekday_month(f)
    if p.empty:
        return
    best = p.sum(axis=1).idxmax()
    show(heatmap(p, f"{best} is the strongest weekday", kind="money", height=H_SM))
    day = p.sum(axis=1)
    day = day[day > 0] / day.sum()
    weekend = day.reindex(["Sat", "Sun"]).fillna(0).sum()
    wd, month = p.stack().idxmax()
    explain("Net revenue for each weekday in each month; darker = more revenue.",
            f"{DAY_NAMES[best]} is the busiest day with {pct(day.max())} of revenue; weekends bring only "
            f"{pct(weekend)}.",
            f"The strongest single cell is {DAY_NAMES[wd]}s in {pd.Timestamp(f'1 {month} 2020'):%B} "
            f"({money(p.loc[wd, month])}).")


def render(f: Filters) -> None:
    """Draw the sales performance tab."""
    st.subheader("Where we sell")
    _geography(f)
    st.subheader("What sells")
    left, right = st.columns([1, 1])
    with left:
        cats = _categories(f)
    with right:
        st.markdown("**Best sellers**")
        top = _best_sellers(f)
    if len(top) and len(cats):
        counts = cats["MainCategory"].value_counts()
        spread = "spread thinly across titles" if top["Share"].sum() < 0.3 else "concentrated in a few titles"
        explain("The top 20 detailed categories by revenue (bar colour = main category) and the best-selling "
                "products.",
                f"{cats.iloc[0]['Category']} is the biggest detailed category ({pct(cats.iloc[0]['Share'])}), and "
                f"{counts.index[0]} fills {counts.iloc[0]} of the top {len(cats)} places.",
                f"Sales are {spread}: the top {len(top)} products bring {pct(top['Share'].sum())} of revenue, and "
                f"the #1 title, {top.iloc[0]['Description']}, brings {money(top.iloc[0]['Revenue'])}.")
    st.subheader("Document series & customer groups")
    _series_and_groups(f)
    st.subheader("Discounts")
    _discounts(f)
    st.subheader("Weekday × month")
    _calendar(f)
