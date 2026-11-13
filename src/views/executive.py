"""Tab 1 - Executive summary: KPIs vs previous period, weekly trend + forecast, category mix, insights."""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import analytics as A
from src import config as C
from src import theme as T
from src.charts import (H_LG, count, explain, format_axis, hover_value, money, pct, province,
                        shade_gaps, show)
from src.data import Filters, previous_period

KPI_SPECS: list[tuple[str, str, str, str]] = [  # key, label, format, help
    ("revenue", "Net revenue", "money", "Sum of Quantity × NetPrice for the selection."),
    ("invoices", "Invoices", "int", "Number of distinct invoices."),
    ("customers", "Active customers", "int", "Customers with at least one invoice in the selection."),
    ("aov", "Avg invoice value", "money", "Net revenue ÷ invoices."),
    ("units", "Units sold", "int", "Total quantity on all invoice lines."),
    ("discount", "Avg discount", "pct", "Revenue-weighted trade discount: 1 − net revenue ÷ list value. Lower is better."),
]


def _fmt(value: float, kind: str) -> str:
    return {"money": money(value), "int": count(value), "pct": pct(value)}[kind]


def _kpi_row(f: Filters) -> None:
    now = A.kpis(f)
    prev_f = previous_period(f)
    prev = A.kpis(prev_f) if prev_f else None
    caption = (f"Δ vs {prev_f.start:%d %b} – {prev_f.end:%d %b %Y} (same length, immediately before)"
               if prev_f else "No earlier data for a comparison period — deltas hidden.")
    for col, (key, label, kind, help_) in zip(st.columns(len(KPI_SPECS)), KPI_SPECS):
        delta = None
        if prev and prev[key]:
            delta = (f"{(now[key] - prev[key]) * 100:+.1f} pp" if kind == "pct"
                     else f"{now[key] / prev[key] - 1:+.1%}")
        col.metric(label, _fmt(now[key], kind), delta, help=help_,
                   delta_color="inverse" if key == "discount" else "normal")
    st.caption(caption)


def _trend(f: Filters) -> None:
    y = A.weekly_series(f)
    fc = A.weekly_forecast(f)
    if y.empty:
        st.info("The selected range contains no complete week — widen the date filter to see the trend.")
        return
    direction = ""
    if fc is not None:
        change = fc["mean"].mean() / max(y.iloc[-8:].mean(), 1) - 1
        trend = "flat" if abs(change) < 0.01 else f"{change:+.0%}"
        direction = f": next {C.FORECAST_WEEKS} weeks forecast {trend} vs the last 8"
    fig = go.Figure()
    fig.add_scatter(x=y.index, y=y.values, name="Actual", mode="lines+markers", line=dict(color=T.ACCENT),
                    hovertemplate=f"Week of %{{x|%d %b}}: {hover_value('money')}<extra></extra>")
    if fc is not None:
        fig.add_scatter(x=list(fc.index) + list(fc.index[::-1]), y=list(fc["hi"]) + list(fc["lo"][::-1]),
                        mode="lines", fill="toself", fillcolor=T.rgba(T.ACCENT, 0.16), line=dict(width=0),
                        name="≈95% band", hoverinfo="skip")
        fig.add_scatter(x=[y.index[-1], *fc.index], y=[y.iloc[-1], *fc["mean"]], name="Holt forecast",
                        mode="lines", line=dict(color=T.ACCENT, dash="dash"),
                        hovertemplate=f"Forecast %{{x|%d %b}}: {hover_value('money')}<extra></extra>")
    shade_gaps(fig, A.data_gaps(f))
    fig.update_layout(title=f"Weekly net revenue{direction}", height=H_LG, hovermode="x unified",
                      yaxis_title="Revenue")
    format_axis(fig, "money")
    show(fig)
    main = f"Revenue averaged {money(y.mean())} a week, and {money(y.iloc[-8:].mean())} over the last 8 weeks."
    notable = f"The best week was {y.idxmax():%d %b} with {money(y.max())}."
    gaps = A.data_gaps(f)
    if gaps:
        notable += f" Revenue fell to almost nothing during the {gaps[0][0]:%d %b}–{gaps[0][1]:%d %b} pause."
    if fc is not None:
        trend_txt = "flat" if trend == "flat" else f"{trend} vs the last 8 weeks"
        main += f" The forecast is {trend_txt}, at about {money(fc['mean'].mean())} a week."
        notable += (f" The forecast range is wide: {money(fc['lo'].iloc[-1])} to {money(fc['hi'].iloc[-1])} "
                    f"by week {C.FORECAST_WEEKS}.")
    explain("Weekly net revenue for complete weeks, with an 8-week Holt forecast (dashed) and its ≈95% range. "
            "The grey strip is the late-July pause with no invoices.", main, notable)


def _treemap(f: Filters) -> None:
    mc = A.main_category_summary(f)
    top = mc.iloc[0]
    fig = px.treemap(mc, path=["MainCategory"], values="Revenue", color="MainCategory",
                     color_discrete_map=T.CATEGORY_COLORS)
    fig.update_traces(texttemplate="%{label}<br><b>%{percentRoot:.1%}</b>", root_color=T.SURFACE,
                      hovertemplate=f"%{{label}}<br>Revenue: {hover_value('money', 'value')}"
                                    "<br>%{percentRoot:.1%} of total<extra></extra>")
    fig.update_layout(title=f"{top['MainCategory']} earns {pct(top['Share'])} of revenue", height=H_LG,
                      margin=dict(l=8, r=8, t=56, b=8), uniformtext=dict(minsize=10, mode="hide"))
    show(fig)
    low = mc.iloc[-1]
    explain("Share of net revenue by main category.",
            f"{top['MainCategory']} alone earns {pct(top['Share'])} of revenue, and the top 3 categories make "
            f"{pct(mc['Share'].head(3).sum())}.",
            f"The smallest, {low['MainCategory']}, brings only {pct(low['Share'])}." if len(mc) > 1 else None)


def _insights(f: Filters) -> list[str]:
    now = A.kpis(f)
    out = [f"Net revenue is **{money(now['revenue'])}** from **{now['invoices']:,}** invoices "
           f"and **{now['customers']:,}** customers, at an average **{pct(now['discount'])}** below list price."]
    prev_f = previous_period(f)
    if prev_f and (prev := A.kpis(prev_f))["revenue"]:
        out.append(f"That is **{now['revenue'] / prev['revenue'] - 1:+.1%}** versus the previous period of the same length.")
    mc = A.main_category_summary(f)
    out.append(f"**{mc.iloc[0]['MainCategory']}** leads with **{pct(mc.iloc[0]['Share'])}** of revenue; "
               f"the top 3 main categories make **{pct(mc['Share'].head(3).sum())}**.")
    city = A.city_summary(f)
    out.append(f"**{province(city.iloc[0]['City'])}** alone brings **{pct(city.iloc[0]['Share'])}** of revenue.")
    _, top20, n80 = A.pareto(f)
    if now["customers"] >= 10:
        out.append(f"The top 20% of customers produce **{pct(top20)}** of revenue — **{n80:,}** customers make up 80%.")
    y = A.weekly_series(f)
    if not y.empty and y.max() > 0:
        out.append(f"Best week: **{y.idxmax():%d %b}** with **{money(y.max())}**.")
    return out[:5]


def render(f: Filters) -> None:
    """Draw the executive summary tab."""
    _kpi_row(f)
    left, right = st.columns([3, 2])
    with left:
        _trend(f)
    with right:
        _treemap(f)
    st.subheader("Key insights")
    st.markdown("\n".join(f"- {s}" for s in _insights(f)))
