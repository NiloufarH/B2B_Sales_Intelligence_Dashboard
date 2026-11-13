"""Tab 5 - Forecasting & models: back-test of four weekly revenue models, horizon slider, anomalies."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src import analytics as A
from src import config as C
from src import theme as T
from src.charts import (H_LG, H_MD, dec_col, explain, format_axis, hover_value, int_col, money, money_col,
                        show, table)
from src.data import Filters

# "Actual" is the accent blue; the models take the next pastels so no line repeats it.
MODEL_COLORS = dict(zip(A.MODELS, T.SERIES[1:]))


def _backtest(f: Filters) -> None:
    res = A.backtest(f)
    if res is None:
        st.info(f"Back-testing needs at least {C.TEST_WEEKS + 12} complete weeks — widen the date filter.")
        return
    metrics = res["metrics"].reset_index(drop=True)
    best = metrics.iloc[0]["Model"]
    for col, row in zip(st.columns(len(metrics)), metrics.itertuples()):
        col.metric(f"{'★ ' if row.Model == best else ''}{row.Model} · MAPE", f"{row.MAPE:.1%}",
                   help="MAPE = mean |error| ÷ actual (weeks with zero revenue skipped). Lower is better.")
        col.caption(f"RMSE {money(row.RMSE)} · lower is better")

    y, test = res["y"], res["test"]
    horizon = st.slider("Forecast horizon (weeks)", 1, 12, C.FORECAST_WEEKS, key="fc_horizon")
    fut = A.future_forecasts(f, horizon)
    fig = go.Figure()
    fig.add_scatter(x=y.index, y=y.values, name="Actual", mode="lines+markers", line=dict(color=T.ACCENT),
                    hovertemplate=f"Actual: {hover_value('money')}<extra></extra>")
    fig.add_vrect(x0=test.index[0], x1=test.index[-1], fillcolor=T.NEUTRAL, opacity=0.2, line_width=0,
                  annotation_text="Test window", annotation_position="top left",
                  annotation_font=dict(size=11, color=T.TEXT_2))
    for name, p in res["preds"].items():
        fig.add_scatter(x=p.index, y=p.values, name=f"{name} (test)", mode="lines", legendgroup=name,
                        line=dict(color=MODEL_COLORS[name], width=2, dash="dot"),
                        hovertemplate=f"{name} test: {hover_value('money')}<extra></extra>")
    if fut is not None:
        for name in fut.columns:
            fig.add_scatter(x=[y.index[-1], *fut.index], y=[y.iloc[-1], *fut[name]], name=f"{name} forecast",
                            mode="lines", legendgroup=name, line=dict(color=MODEL_COLORS[name]),
                            hovertemplate=f"{name}: {hover_value('money')}<extra></extra>")
    fig.update_layout(title=f"{best} has the lowest test error (MAPE {metrics.iloc[0]['MAPE']:.1%})",
                      height=H_LG, hovermode="x unified", yaxis_title="Weekly revenue")
    format_axis(fig, "money")
    show(fig)
    st.warning("Only one year of data is available, so 12-month (yearly) seasonality cannot be learned or "
               "validated. Treat these forecasts as short-term trend extrapolations.", icon=":material/info:")
    top, second, worst = metrics.iloc[0], metrics.iloc[1], metrics.iloc[-1]
    totals = fut.sum() if fut is not None else None
    explain(f"Four models trained on all but the last {C.TEST_WEEKS} complete weeks (grey) and scored on them "
            "(dotted). Solid lines are each model refitted on all weeks and forecast ahead.",
            f"{best} has the lowest test error (MAPE {top['MAPE']:.1%}, about {money(top['RMSE'])} a week), ahead "
            f"of {second['Model']} ({second['MAPE']:.1%}).",
            f"{worst['Model']} has the highest error ({worst['MAPE']:.1%})."
            + (f" Over the next {horizon} weeks the models' totals range from {money(totals.min())} to "
               f"{money(totals.max())}." if totals is not None else ""))


def _anomalies(f: Filters) -> None:
    c1, c2 = st.columns([1, 2])
    method = c1.radio("Method", ["Rolling z-score", "Isolation Forest"], horizontal=True, key="an_method")
    if method == "Rolling z-score":
        thr = c2.slider("Threshold (|z|)", 2.0, 4.0, 3.0, 0.25, key="an_thr")
        d = A.anomalies_zscore(f, thr)
    else:
        cont = c2.slider("Expected share of anomalies", 0.01, 0.10, 0.03, 0.01, key="an_cont")
        d = A.anomalies_iforest(f, cont)
    if d.empty:
        st.info("No trading days in the selection.")
        return
    flagged = d[d["Anomaly"]]
    fig = go.Figure()
    fig.add_scatter(x=d.index, y=d["Revenue"], mode="lines", name="Daily revenue", line=dict(color=T.ACCENT),
                    hovertemplate=f"%{{x|%a %d %b}}: {hover_value('money')}<extra></extra>")
    fig.add_scatter(x=d.index, y=d["Expected"], mode="lines", name="Rolling baseline",
                    line=dict(color=T.NEUTRAL, width=1.5, dash="dot"), hoverinfo="skip")
    fig.add_scatter(x=flagged.index, y=flagged["Revenue"], mode="markers", name="Anomaly",
                    marker=dict(size=10, color=T.NEGATIVE, symbol="diamond", line=dict(color=T.SURFACE, width=1.5)),
                    hovertemplate=f"Anomaly %{{x|%a %d %b}}: {hover_value('money')}<extra></extra>")
    fig.update_layout(title=f"{len(flagged)} unusual trading day{'s' if len(flagged) != 1 else ''} flagged",
                      height=H_MD, yaxis_title="Revenue")
    format_axis(fig, "money")
    show(fig)
    view = (flagged[["Revenue", "Expected", "Invoices", "Lines", "Score"]].sort_values("Revenue", ascending=False)
            .rename_axis("Date").reset_index())
    table(view, column_config={
        "Date": st.column_config.DateColumn("Date", format="ddd DD MMM YYYY"),
        "Revenue": money_col("Revenue (₺)"),
        "Expected": money_col("Expected (₺)"),
        "Invoices": int_col("Invoices"),
        "Lines": int_col("Lines"),
        "Score": dec_col("Score", 2)})
    shows = ("Daily revenue against a 21-day rolling baseline; diamonds are days whose |z| is above the threshold."
             if method == "Rolling z-score" else
             "Daily revenue; diamonds are the days Isolation Forest finds most unusual given revenue, invoice and "
             "line counts and weekday.")
    main = f"{len(flagged)} of {len(d)} trading days {'is' if len(flagged) == 1 else 'are'} flagged as unusual."
    if len(flagged):
        top = view.iloc[0]
        ratio = f" ({top['Revenue'] / top['Expected']:.1f}× normal)" if top["Expected"] > 0 else ""
        notable = (f"{top['Date']:%d %b} stands out with {money(top['Revenue'])} against about "
                   f"{money(top['Expected'])} expected{ratio}.")
    else:
        notable = "No day stands out at this setting."
    explain(shows, main, notable)


def render(f: Filters) -> None:
    """Draw the forecasting & models tab."""
    st.subheader("Weekly revenue forecast — model comparison")
    _backtest(f)
    st.subheader("Anomaly detection on daily revenue")
    _anomalies(f)
