"""Tab 4 - Supply chain: ABC×XYZ, category demand forecasts, slow movers, safety stock, provincial demand."""
from __future__ import annotations

from statistics import NormalDist

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import analytics as A
from src import config as C
from src import theme as T
from src.charts import (H_LG, H_MD, as_percent, dec_col, explain, format_axis, hbar, int_col,
                        money_col, pct, pct_col, province, show, table)
from src.data import Filters, filtered


def _abc_xyz(f: Filters) -> None:
    p = A.abc_xyz(f)
    if p.empty:
        st.info("ABC × XYZ needs at least two complete months in the selection.")
        return
    cnt = p.pivot_table(index="ABC", columns="XYZ", values="StockCode", aggfunc="count", fill_value=0)
    rev = p.pivot_table(index="ABC", columns="XYZ", values="Revenue", aggfunc="sum", fill_value=0)
    cnt = cnt.reindex(index=list("ABC"), columns=list("XYZ"), fill_value=0)
    share = (rev / rev.values.sum()).reindex(index=list("ABC"), columns=list("XYZ"), fill_value=0)
    a_share = len(p[p["ABC"] == "A"]) / len(p)
    left, right = st.columns([2, 3])
    with left:
        fig = go.Figure(go.Heatmap(
            z=share.values, x=["X (steady)", "Y (variable)", "Z (erratic)"], y=["A", "B", "C"],
            xgap=3, ygap=3, customdata=cnt.values, colorbar=dict(tickformat=".0%"),
            text=cnt.values, texttemplate="<b>%{z:.1%}</b><br>%{text:,} SKUs",
            hovertemplate="%{y}%{x}<br>%{customdata:,} products<br>%{z:.1%} of revenue<extra></extra>"))
        fig.update_layout(title=f"{pct(a_share)} of products (A) make 80% of revenue", height=H_MD)
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(autorange="reversed", showgrid=False)
        show(fig)
    with right:
        cells = list(C.ABC_XYZ_POLICY)
        busiest = p["Class"].value_counts().idxmax()   # default to the cell holding the most products
        cell = st.selectbox("Policy for cell", cells, index=cells.index(busiest), key="abc_cell")
        sub = p[p["Class"] == cell]
        st.markdown(f"**{cell}** · {len(sub):,} products · {pct(sub['Revenue'].sum() / p['Revenue'].sum())} of revenue")
        st.success(C.ABC_XYZ_POLICY[cell], icon=":material/inventory_2:")
        table(sub.head(200)[["StockCode", "Revenue", "Units", "CV"]], height=220, column_config={
            "StockCode": st.column_config.TextColumn("Product code"),
            "Revenue": money_col("Revenue (₺)"),
            "Units": int_col("Units"),
            "CV": dec_col("CV of monthly units", 2)})
    n_a = int((p["ABC"] == "A").sum())
    cz = p[p["Class"] == "CZ"]
    explain("ABC ranks products by revenue (A = top 80% of revenue, B = next 15%, C = last 5%). XYZ rates how "
            "steady monthly demand is (X steady, Y variable, Z erratic).",
            f"{pct(a_share)} of products ({n_a:,} A items) make 80% of revenue.",
            f"{pct((p['XYZ'] == 'Z').mean())} of products have erratic monthly demand (Z), and the {len(cz):,} CZ "
            f"products bring only {pct(cz['Revenue'].sum() / p['Revenue'].sum())} of revenue.")


def _category_forecast(f: Filters) -> None:
    m = A.weekly_units_matrix(f, "MainCategory")
    fcs = A.category_forecasts(f)
    if not fcs:
        st.info("Forecasts need at least 10 complete weeks in the selection.")
        return
    options = [c for c in C.MAIN_CATEGORIES if c in fcs]
    picked = st.multiselect("Main categories", options, default=options[:3], key="fc_cats")
    fig = go.Figure()
    for c in picked:
        color, fc = T.CATEGORY_COLORS[c], fcs[c]
        fig.add_scatter(x=m.index, y=m[c], name=c, mode="lines", line=dict(color=color),
                        legendgroup=c, hovertemplate=f"{c}: %{{y:,.0f}}<extra></extra>")
        fig.add_scatter(x=[m.index[-1], *fc.index], y=[m[c].iloc[-1], *fc["mean"]], mode="lines",
                        line=dict(color=color, dash="dash"), legendgroup=c, showlegend=False,
                        hovertemplate=f"{c} forecast: %{{y:,.0f}}<extra></extra>")
    fig.update_layout(title=f"Weekly units with {C.FORECAST_WEEKS}-week Holt forecast (dashed)", height=H_LG,
                      hovermode="x unified", yaxis_title="Units")
    format_axis(fig, "int")
    show(fig)
    rows = [{"Main category": c, "Last 8 wk avg": m[c].iloc[-8:].mean(), "Forecast avg": fcs[c]["mean"].mean()}
            for c in options]
    tbl = pd.DataFrame(rows)
    tbl["Change"] = tbl["Forecast avg"] / tbl["Last 8 wk avg"].replace(0, np.nan) - 1
    table(as_percent(tbl, "Change"), column_config={
        "Last 8 wk avg": int_col("Last 8 wk avg (units/wk)"),
        "Forecast avg": int_col("Forecast avg (units/wk)"),
        "Change": pct_col("Change", signed=True)})
    ch = tbl.dropna(subset=["Change"]).sort_values("Change")
    big = tbl.sort_values("Last 8 wk avg").iloc[-1]
    move = ("is flat" if abs(big["Change"]) < 0.01 else f"changes by {big['Change']:+.0%}")
    main = (f"{big['Main category']} sells the most, about {big['Last 8 wk avg']:,.0f} units a week, and its "
            f"forecast {move}." if big["Change"] == big["Change"] else None)
    notable = None
    if len(ch) >= 2:
        up, down = ch.iloc[-1], ch.iloc[0]
        notable = (f"The largest expected moves are {up['Main category']} ({up['Change']:+.0%}) and "
                   f"{down['Main category']} ({down['Change']:+.0%}).")
    explain(f"Weekly units by main category (solid) with an {C.FORECAST_WEEKS}-week Holt forecast (dashed); the "
            "table compares the forecast with the last 8 weeks.", main, notable)


def _slow_movers(f: Filters) -> None:
    single, stale = A.slow_movers(f)
    c1, c2 = st.columns(2)
    c1.metric("Products sold on a single line", f"{len(single):,}",
              help="Products that appear on exactly one invoice line in the selection.")
    c2.metric(f"No sale in the last {C.SLOW_MOVER_DAYS} days", f"{len(stale):,}",
              help=f"Last sale earlier than {C.SLOW_MOVER_DAYS} days before the end of the selected range.")
    cols = ["StockCode", "Description", "Category", "Units", "Revenue", "LastSale", "DaysSinceSale"]
    cfg = {"StockCode": st.column_config.TextColumn("Code", width=104),
           "Description": st.column_config.TextColumn("Product", width=126),
           "Category": st.column_config.TextColumn("Category", width=86),
           "Units": int_col("Units", width=50),
           "Revenue": money_col("Revenue (₺)", width=78),
           "LastSale": st.column_config.DateColumn("Last sale", format="DD MMM YY", width=72),
           "DaysSinceSale": int_col("Days", width=46)}
    t1, t2 = st.tabs(["Single-line products", f"Stale > {C.SLOW_MOVER_DAYS} days"])
    with t1:
        table(single[cols].head(500), height=300, column_config=cfg)
    with t2:
        table(stale[cols].head(500), height=300, column_config=cfg)
    n_prod = max(filtered(f)["StockCode"].nunique(), 1)
    explain(f"Products that sold on just one invoice line, and products with no sale in the last "
            f"{C.SLOW_MOVER_DAYS} days of the selection (tables show up to 500, highest revenue first).",
            f"{len(single):,} products sold on only one invoice line, and {len(stale):,} haven't sold in the last "
            f"{C.SLOW_MOVER_DAYS} days.",
            f"The stale products are {pct(len(stale) / n_prod)} of the {n_prod:,} products sold in the selection.")


def _safety_stock(f: Filters) -> None:
    prods = A.top_products_by_units(f)
    if prods.empty:
        st.info("No products in the selection.")
        return
    labels = dict(zip(prods["StockCode"].astype(str), prods["Description"].astype(str)))
    c1, c2, c3 = st.columns([3, 1, 1])
    code = c1.selectbox("Product (top 200 by units)", list(labels), format_func=lambda s: f"{labels[s]} · {s}",
                        key="ss_product")
    service = c2.slider("Service level", 0.80, 0.995, 0.95, 0.005, format="%.3f", key="ss_service")
    lead = c3.slider("Lead time (weeks)", 1, 12, 2, key="ss_lead")
    y = A.product_weekly_units(f, code)
    if y.empty:
        st.info("No complete weeks in the selection.")
        return
    d, sigma, z = y.mean(), y.std(ddof=1) if len(y) > 1 else 0.0, NormalDist().inv_cdf(service)
    ss = z * sigma * np.sqrt(lead)
    rop = d * lead + ss
    k = st.columns(4)
    k[0].metric("Avg weekly demand (d)", f"{d:,.1f}")
    k[1].metric("Demand σ (weekly)", f"{sigma:,.1f}")
    k[2].metric("Safety stock", f"{np.ceil(ss):,.0f} units", help="SS = z · σ · √L")
    k[3].metric("Reorder point", f"{np.ceil(rop):,.0f} units", help="ROP = d · L + SS")
    fig = go.Figure(go.Bar(x=y.index, y=y.values, marker_color=T.BLUE, marker_line_color=T.BLUE,
                           name="Weekly units", hovertemplate="Week of %{x|%d %b}: %{y:,.0f}<extra></extra>"))
    fig.add_hline(y=d, line=dict(color=T.ACCENT, dash="dot", width=1.5), annotation_text=f"mean {d:,.1f}",
                  annotation_font=dict(color=T.TEXT_2))
    fig.update_layout(title=f"Weekly demand — reorder when stock falls to {np.ceil(rop):,.0f} units",
                      height=H_MD, yaxis_title="Units")
    format_axis(fig, "int")
    show(fig)
    explain(f"Weekly units for this product. Safety stock = z·σ·√L (z = {z:.2f} for a {service:.1%} service level) "
            f"covers demand swings during the {lead}-week lead time; reorder point = d·L + safety stock.",
            f"This product sells about {d:,.0f} units a week, but demand swings a lot (σ = {sigma:,.0f}, "
            f"{sigma / d:.0%} of the average)." if d > 0 else "This product had no sales in these weeks.",
            f"The busiest week (week of {y.idxmax():%d %b}) sold {y.max():,.0f} units; with this much variation, "
            f"safety stock of {np.ceil(ss):,.0f} units covers {ss / d:.1f} weeks of average demand." if d > 0 else None)


def _province_demand(f: Filters) -> None:
    city = A.city_summary(f).sort_values("Units", ascending=False)
    top = city.head(15)
    show(hbar(top.assign(City=top["City"].map(province)), "Units", "City",
              f"Top 15 provinces take {pct(top['UnitShare'].sum())} of units shipped",
              text=top["UnitShare"].map(pct), kind="int", height=520))
    lead = top.iloc[0]
    explain("Units shipped to customers in each province (top 15).",
            f"{province(lead['City'])} takes {pct(lead['UnitShare'])} of units, followed by "
            + " and ".join(f"{province(c)} ({pct(s)})" for c, s in zip(top["City"].iloc[1:3], top["UnitShare"].iloc[1:3]))
            + ".",
            f"The top 15 provinces take {pct(top['UnitShare'].sum())} of units. {province(lead['City'])}'s unit share "
            f"is {'close to' if abs(lead['UnitShare'] - lead['Share']) < 0.03 else 'different from'} its revenue "
            f"share ({pct(lead['Share'])}).")


TERMS = f"""
- **ABC analysis** sorts products by how much revenue they bring. A products are the small group that together make
  the first 80% of revenue, B products make the next 15%, and C products, usually the long tail, make the last 5%.
- **XYZ analysis** looks at how predictable a product's demand is. It compares the month-to-month swings in units sold
  with the average (the coefficient of variation, CV). X products sell steadily (CV below 0.5), Y products vary
  (0.5 to 1), and Z products are erratic (above 1).
- **ABC × XYZ** combines the two into nine groups. AX products are valuable and easy to plan, so they can be restocked
  almost automatically. CZ products bring little revenue and sell unpredictably, so they're candidates for dropping
  or ordering only on demand.
- **Slow movers** are products that sold on just one invoice line, or haven't sold at all in the last
  {C.SLOW_MOVER_DAYS} days of the selected period.
- **Lead time** is how many weeks pass between placing an order with a supplier and the books arriving.
- **Service level** is how often you want to have the product in stock when a customer asks for it, for example 95%
  of the time.
- **Safety stock** is the extra stock kept on top of normal demand to cover unexpected spikes during the lead time.
  The more demand swings and the longer the lead time, the more you need.
- **Reorder point** is the stock level at which you should place a new order: the demand you expect during the lead
  time plus the safety stock.
"""


def render(f: Filters) -> None:
    """Draw the supply chain tab."""
    st.caption("The data has sales only (no stock, receipts or lead times), so this tab is demand-side planning.")
    with st.expander("Terms used on this page", icon=":material/menu_book:"):
        st.markdown(TERMS)
    st.subheader("ABC × XYZ classification")
    _abc_xyz(f)
    st.subheader("Weekly demand forecast by main category")
    _category_forecast(f)
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Slow movers")
        _slow_movers(f)
    with right:
        st.subheader("Demand by province")
        _province_demand(f)
    st.subheader("Safety-stock calculator")
    _safety_stock(f)
