"""Tab 3 - Customers & marketing: RFM, K-Means, Pareto, market basket, cohorts, at-risk export."""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from src import analytics as A
from src import config as C
from src import theme as T
from src.charts import (H_LG, H_MD, as_percent, dec_col, explain, heatmap, hbar, hover_value,
                        int_col, money, money_col, pct, pct_col, share_col, show, table)
from src.data import Filters

SEGMENT_ORDER = list(C.RFM_SEGMENT_ACTIONS)


def _rfm(f: Filters) -> None:
    t = A.rfm(f)
    if t.empty:
        st.info("RFM needs at least 10 customers in the selection.")
        return
    seg = (t.groupby("Segment").agg(Customers=("CustomerID", "size"), Revenue=("Monetary", "sum"),
                                    AvgRecency=("Recency", "mean"), AvgFrequency=("Frequency", "mean"))
           .reindex(SEGMENT_ORDER).dropna(subset=["Customers"]).reset_index())
    seg["RevenueShare"] = seg["Revenue"] / seg["Revenue"].sum()
    seg["Action"] = seg["Segment"].map(C.RFM_SEGMENT_ACTIONS)
    champ = seg.set_index("Segment")["RevenueShare"].get("Champions", 0)
    ranked = seg.sort_values("Revenue", ascending=False)
    show(hbar(ranked, "Revenue", "Segment", f"Champions hold {pct(champ)} of revenue",
              text=ranked["RevenueShare"].map(pct), height=H_MD))
    table(as_percent(seg[["Segment", "Customers", "RevenueShare", "AvgRecency", "AvgFrequency", "Action"]],
                     "RevenueShare"), height=35 * (len(seg) + 1) + 3, column_config={
        "Segment": st.column_config.TextColumn("Segment", width=130),
        "Customers": int_col("Customers", width=80),
        "RevenueShare": share_col("Revenue share", width=110),
        "AvgRecency": dec_col("Avg days since order", 0, width=140),
        "AvgFrequency": dec_col("Avg invoices", 1, width=90),
        "Action": st.column_config.TextColumn("Recommended action"),
    })
    at_risk = t[t["Segment"].isin(C.AT_RISK_SEGMENTS)].sort_values("Monetary", ascending=False)
    counts = seg.set_index("Segment")["Customers"]
    n_champ, n_lost = int(counts.get("Champions", 0)), int(counts.get("Lost", 0))
    explain("Customers scored 1–5 on recency, order frequency and revenue, then grouped into segments.",
            f"Champions ({n_champ:,} customers, {pct(n_champ / len(t))} of the base) hold {pct(champ)} of revenue.",
            f"{len(at_risk):,} customers in at-risk segments still bring "
            f"{pct(at_risk['Monetary'].sum() / t['Monetary'].sum())} of revenue, and {n_lost:,} are already Lost.")
    cols = ["CustomerID", "Segment", "City", "Group", "Recency", "Frequency", "Monetary", "LastBuy", "Action"]
    st.download_button(
        f"Download {len(at_risk):,} at-risk customers (CSV)",
        data=lambda: at_risk[cols].to_csv(index=False).encode("utf-8-sig"),
        file_name="at_risk_customers.csv", mime="text/csv", on_click="ignore", icon=":material/download:",
        help="Segments: " + ", ".join(C.AT_RISK_SEGMENTS) + f" — worth {money(at_risk['Monetary'].sum())} "
             "in the selected period.")


def _kmeans(f: Filters) -> None:
    res = A.kmeans_rfm(f)
    if res is None:
        st.info("Clustering needs at least 30 customers in the selection.")
        return
    pts, prof = res["points"], res["profile"]
    left, right = st.columns([3, 2])
    with left:
        fig = go.Figure()
        for i, (name, g) in enumerate(pts.groupby("Cluster")):
            fig.add_scatter(x=g["PC1"], y=g["PC2"], mode="markers", name=name,
                            marker=dict(size=8, color=T.SERIES[i % len(T.SERIES)], opacity=0.85,
                                        line=dict(color=T.SURFACE, width=1)),
                            customdata=g[["CustomerID", "Recency", "Frequency", "Monetary"]],
                            hovertemplate="%{customdata[0]}<br>Recency %{customdata[1]} d · "
                                          f"%{{customdata[2]}} invoices<br>Revenue {hover_value('money', 'customdata[3]')}"
                                          "<extra></extra>")
        fig.update_layout(title=f"k = {res['k']} clusters chosen by silhouette ({res['scores'][res['k']]:.2f})",
                          height=H_LG, xaxis_title="PC1", yaxis_title="PC2")
        show(fig)
    with right:
        sil = go.Figure(go.Bar(x=list(res["scores"]), y=list(res["scores"].values()),
                               marker_color=[T.ACCENT if k == res["k"] else T.NEUTRAL for k in res["scores"]],
                               marker_line_color=[T.ACCENT if k == res["k"] else T.NEUTRAL for k in res["scores"]],
                               hovertemplate="k=%{x}: %{y:.3f}<extra></extra>"))
        sil.update_layout(title="Silhouette score by k", height=H_LG, xaxis_title="k")
        show(sil)
    table(as_percent(prof, "RevenueShare"), column_config={
        "Customers": int_col("Customers"),
        "AvgRecency": dec_col("Avg recency (d)", 0),
        "AvgFrequency": dec_col("Avg invoices", 1),
        "AvgMonetary": money_col("Avg revenue (₺)"),
        "Revenue": money_col("Revenue (₺)"),
        "RevenueShare": share_col("Revenue share"),
    })
    best, last = prof.iloc[0], prof.iloc[-1]
    explain(f"Customers grouped by recency, frequency and revenue; k = {res['k']} gave the clearest split. "
            "Cluster 1 is the most valuable; the scatter is a 2-D view of the three measures.",
            f"{best['Cluster']} ({best['Customers']:,} customers, about {best['AvgFrequency']:.0f} invoices each) "
            f"brings {pct(best['RevenueShare'])} of revenue.",
            f"{last['Cluster']} has {last['Customers']:,} customers who last ordered {last['AvgRecency']:.0f} days "
            f"ago on average and bring only {pct(last['RevenueShare'])}.")


def _pareto(f: Filters) -> None:
    curve, top20, n80 = A.pareto(f)
    fig = go.Figure()
    fig.add_scatter(x=curve["x"], y=curve["y"], mode="lines", line=dict(color=T.ACCENT), name="Customers",
                    hovertemplate="Top %{x:.1%} of customers → %{y:.1%} of revenue<extra></extra>")
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=T.NEUTRAL, dash="dot", width=1.5),
                    name="Equal share", hoverinfo="skip")
    fig.add_scatter(x=[0.2], y=[top20], mode="markers+text", marker=dict(size=10, color=T.ACCENT,
                    line=dict(color=T.SURFACE, width=2)), text=[f"  20% → {pct(top20)}"], textposition="middle right",
                    textfont=dict(color=T.TEXT), showlegend=False, hoverinfo="skip")
    fig.update_layout(title=f"20% of customers bring {pct(top20)} of revenue", height=H_MD, showlegend=False,
                      xaxis=dict(tickformat=".0%", title="Share of customers (ranked)"),
                      yaxis=dict(tickformat=".0%", title="Cumulative revenue"))
    show(fig)
    n = max(int(A.kpis(f)["customers"]), 1)
    explain("Cumulative share of revenue with customers ranked from largest to smallest; the dotted line is an "
            "equal split.",
            f"Revenue is {'highly ' if top20 >= 0.6 else ''}concentrated: the top 20% of customers bring "
            f"{pct(top20)} of it.",
            f"Just {n80:,} customers ({pct(n80 / n)} of the base) make up 80% of revenue.")


def _basket(f: Filters) -> None:
    rules = A.basket_rules(f)
    if rules.empty:
        st.info("Not enough multi-category invoices for association rules in this selection.")
        return
    top = rules.head(10)
    table(as_percent(top, "support", "confidence"), column_config={
        "Antecedent": st.column_config.TextColumn("If the invoice has…", width=210),
        "Consequent": st.column_config.TextColumn("…it often also has", width=140),
        "support": pct_col("Support", width=68),
        "confidence": pct_col("Confidence", width=82),
        "lift": st.column_config.ProgressColumn("Lift", format="%.2f", min_value=1.0, color=T.BLUE, width=84,
                                                max_value=float(top["lift"].max())),
    })
    r = top.iloc[0]
    common = rules.sort_values("support").iloc[-1]
    n_pairs = len({frozenset(p) for p in zip(rules["Antecedent"], rules["Consequent"])})
    explain("Pairs of main categories bought on the same invoice more often than chance (lift > 1). Support = "
            "share of invoices with both; confidence = share of invoices with the first that also have the second.",
            f"The strongest pair is {r['Antecedent']} → {r['Consequent']} (lift {r['lift']:.2f}): "
            f"{pct(r['confidence'])} of invoices with {r['Antecedent']} also include {r['Consequent']}.",
            f"{n_pairs} category pairs sell together more often than chance; the most common is "
            f"{common['Antecedent']} + {common['Consequent']}, on {pct(common['support'])} of invoices.")


def _cohorts(f: Filters) -> None:
    ret = A.cohort_retention(f)
    if ret.shape[1] < 2:
        st.info("Cohorts need at least two months in the selection.")
        return
    m1 = ret[1].mean() if 1 in ret.columns else float("nan")
    z = ret.copy()
    z.columns = [f"+{c}" for c in z.columns]
    first = ret.iloc[0].dropna()
    show(heatmap(z, f"On average {pct(m1, 0)} of a cohort orders again the next month", kind="pct", text=True,
                 height=H_LG))
    explain("Each row is the customers whose first order fell in that month (n = count); cells show the share "
            "who ordered again 1, 2, … months later.",
            f"On average {pct(m1, 0)} of a cohort orders again the month after its first order." if m1 == m1 else None,
            f"The {ret.index[0]} cohort still has {pct(first.iloc[-1], 0)} of its customers ordering "
            f"{first.index[-1]} months later." if len(first) > 1 else None)


def render(f: Filters) -> None:
    """Draw the customers & marketing tab."""
    st.subheader("RFM segmentation")
    _rfm(f)
    st.subheader("K-Means clusters")
    _kmeans(f)
    left, right = st.columns([2, 3])
    with left:
        st.subheader("Revenue concentration")
        _pareto(f)
    with right:
        st.subheader("Market basket (main categories)")
        _basket(f)
    st.subheader("Monthly cohort retention")
    _cohorts(f)
