"""Chart builders, number formatting and table helpers shared by every page. Colours come from src.theme."""
from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import config as C
from src import theme as T

PLOTLY_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}

# One height per row size, so charts placed side by side line up.
H_SM, H_MD, H_LG = 340, 400, 440

Kind = Literal["money", "int", "pct"]


# --------------------------------------------------------------------------- number formatting
def compact(x: float) -> str:
    """Three significant digits with a suffix: 29_580_000 -> '29.6M', 1_890_000 -> '1.89M', 664_133 -> '664K'."""
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(x) >= div * 0.9995:   # 999_999 -> '1.00M', never '1,000K'
            v = x / div
            digits = 0 if abs(v) >= 99.95 else 1 if abs(v) >= 9.995 else 2
            return f"{v:,.{digits}f}{suffix}"
    return f"{x:,.0f}"


def money(x: float) -> str:
    """Compact Turkish-lira amount: '₺29.6M'."""
    return f"{'-' if x < 0 else ''}₺{compact(abs(x))}"


def count(x: float) -> str:
    """Counts: full number up to 9,999, compact above ('1,201', '47.5K')."""
    return f"{x:,.0f}" if abs(x) < 10_000 else compact(x)


def pct(x: float, digits: int = 1) -> str:
    """0.736 -> '73.6%' (always dot decimals, whatever the browser locale)."""
    return f"{x:.{digits}%}"


def province(name: str) -> str:
    """Data spelling -> display name with Turkish characters: 'ISTANBUL' -> 'İstanbul'."""
    return C.PROVINCE_NAMES.get(str(name), str(name).title())


_TR_ORDER = {ch: i for i, ch in enumerate("abcçdefgğhıijklmnoöprsştuüvyz")}


def turkish_sort_key(text: str) -> list[int]:
    """Sort key that follows the Turkish alphabet (Çanakkale after Bursa, İstanbul after Iğdır)."""
    low = text.replace("I", "ı").replace("İ", "i").lower()
    return [_TR_ORDER.get(ch, 100 + ord(ch)) for ch in low]


# d3 formats for Plotly hover templates and axes
MONEY_D3 = ",.3~s"   # 693k, 1.12M
HOVER: dict[str, str] = {"money": "₺%{{{v}:" + MONEY_D3 + "}}", "int": "%{{{v}:,.0f}}", "pct": "%{{{v}:.1%}}"}


def hover_value(kind: Kind, var: str = "y") -> str:
    """Hover snippet for one value: hover_value('money', 'x') -> '₺%{x:,.3~s}'."""
    return HOVER[kind].format(v=var)


def format_axis(fig: go.Figure, kind: Kind, axis: Literal["x", "y"] = "y") -> None:
    """₺ + compact suffix for money, thousands separators for counts, '73%' for shares."""
    spec = {"money": dict(tickprefix="₺", tickformat="~s"), "int": dict(tickformat=",~s"),
            "pct": dict(tickformat=".0%")}[kind]
    (fig.update_xaxes if axis == "x" else fig.update_yaxes)(**spec)


# --------------------------------------------------------------------------- tables
def as_percent(df: pd.DataFrame, *cols: str) -> pd.DataFrame:
    """Copy with share columns × 100, so printf formats show '73.6%' (Streamlit's own 'percent'
    format follows the browser locale and can render '%73,6')."""
    return df.assign(**{c: df[c] * 100 for c in cols})


def int_col(label: str | None = None, **kw) -> dict:
    """Whole numbers with comma separators, independent of browser locale."""
    return st.column_config.NumberColumn(label, format="accounting", step=1, **kw)


def money_col(label: str | None = None, decimals: int = 0, **kw) -> dict:
    """Lira amounts: '1,234' (put ₺ in the label)."""
    return st.column_config.NumberColumn(label, format="accounting", step=10 ** -decimals if decimals else 1, **kw)


def dec_col(label: str | None = None, decimals: int = 1, **kw) -> dict:
    """Small decimals such as averages, CV or scores."""
    return st.column_config.NumberColumn(label, format=f"%.{decimals}f", **kw)


def pct_col(label: str | None = None, decimals: int = 1, signed: bool = False, **kw) -> dict:
    """Column already scaled by as_percent(): '73.6%' or '+4.2%'."""
    return st.column_config.NumberColumn(label, format=f"%{'+' if signed else ''}.{decimals}f%%", **kw)


def share_col(label: str | None = None, max_value: float = 100.0, **kw) -> dict:
    """Pastel progress bar for a share column already scaled by as_percent()."""
    return st.column_config.ProgressColumn(label, format="%.1f%%", min_value=0.0, max_value=max(max_value, 1e-9),
                                           color=T.BLUE, **kw)


def table(df: pd.DataFrame, column_config: dict | None = None, **kw) -> None:
    """st.dataframe with the shared defaults: no index, full width."""
    st.dataframe(df, hide_index=True, width="stretch", column_config=column_config, **kw)


# --------------------------------------------------------------------------- streamlit wrappers
def _tidy_legend(fig: go.Figure) -> None:
    """Drop unnamed legend entries ('trace 0') and hide the legend when only one series remains."""
    legend_traces = [tr for tr in fig.data if hasattr(type(tr), "showlegend")]   # treemaps etc. have no legend
    for tr in legend_traces:
        if not tr.name:
            tr.showlegend = False
    shown = [tr for tr in legend_traces if tr.showlegend is not False and tr.type != "heatmap"]
    if len(shown) <= 1 or fig.layout.showlegend is False:
        fig.update_layout(showlegend=False)


def show(fig: go.Figure, key: str | None = None) -> None:
    """Render a figure at container width with the shared config and tidy legend."""
    _tidy_legend(fig)
    st.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG, key=key)


def explain(shows: str, main: str | None = None, notable: str | None = None) -> None:
    """Short block under a chart or section: what it shows, its main point and what stands out.

    The main point and the notable item are computed from the filtered data, so they change with the filters.
    """
    st.caption(f"**What it shows:** {shows}")
    parts = [f"**Main point:** {main}" if main else "", f"**What stands out:** {notable}" if notable else ""]
    body = "  \n".join(p for p in parts if p)
    if body:
        st.info(body, icon=":material/insights:")


# --------------------------------------------------------------------------- chart builders
def hbar(data: pd.DataFrame, x: str, y: str, title: str, *, color: str | list[str] = T.BLUE,
         text: pd.Series | None = None, kind: Kind = "money", hover: str | None = None,
         height: int | None = None) -> go.Figure:
    """Horizontal bar chart sorted top-down in the order given."""
    d = data.iloc[::-1]
    colors = color[::-1] if isinstance(color, list) else color
    fig = go.Figure(go.Bar(x=d[x], y=d[y].astype(str), orientation="h", marker_color=colors,
                           marker_line_color=colors, text=None if text is None else text.iloc[::-1],
                           textposition="outside", cliponaxis=False,
                           hovertemplate=(hover or f"%{{y}}: {hover_value(kind, 'x')}") + "<extra></extra>"))
    fig.update_layout(title=title, height=height or max(H_SM, 26 * len(d) + 110), showlegend=False)
    fig.update_yaxes(showgrid=False)
    format_axis(fig, kind, "x")
    if text is not None and len(d):
        fig.update_xaxes(range=[0, float(d[x].max()) * 1.18])   # room for the outside labels
    return fig


def lines(data: pd.DataFrame, x: str, y: str, series: str, title: str, colors: dict[str, str],
          kind: Kind = "money", height: int = H_MD) -> go.Figure:
    """Multi-series line chart with fixed colours per series and a unified hover."""
    fig = go.Figure()
    for name, g in data.groupby(series, observed=True, sort=False):
        fig.add_scatter(x=g[x], y=g[y], name=str(name), mode="lines+markers",
                        line=dict(color=colors.get(str(name), T.NEUTRAL)),
                        hovertemplate=f"{name}: {hover_value(kind)}<extra></extra>")
    fig.update_layout(title=title, hovermode="x unified", height=height)
    format_axis(fig, kind)
    return fig


def heatmap(z: pd.DataFrame, title: str, *, kind: Kind = "money", text: bool = False,
            height: int = H_SM) -> go.Figure:
    """Pastel heatmap with 2px cell gaps; optional in-cell text (dark on every pastel)."""
    cell = {"money": "₺%{z:" + MONEY_D3 + "}", "int": "%{z:,.0f}", "pct": "%{z:.0%}"}[kind]
    bar = {"money": dict(tickprefix="₺", tickformat="~s"), "int": dict(tickformat=",~s"),
           "pct": dict(tickformat=".0%")}[kind]
    fig = go.Figure(go.Heatmap(z=z.values, x=[str(c) for c in z.columns], y=[str(i) for i in z.index],
                               texttemplate=cell if text else None, colorbar=bar,
                               hovertemplate=f"%{{y}} · %{{x}}<br>{cell}<extra></extra>"))
    fig.update_layout(title=title, height=height)
    fig.update_xaxes(showgrid=False, type="category")   # labels like "+1" stay labels, not numbers
    fig.update_yaxes(showgrid=False, autorange="reversed", type="category")
    return fig


def histogram(values: pd.Series, title: str, *, bins: int = 40, range_: tuple[float, float] | None = None,
              x_fmt: str = ",.2f", x_title: str = "", height: int = H_SM) -> go.Figure:
    """Histogram from pre-binned counts (raw rows never reach Plotly)."""
    counts, edges = np.histogram(values.dropna(), bins=bins, range=range_)
    centers = (edges[:-1] + edges[1:]) / 2
    fig = go.Figure(go.Bar(x=centers, y=counts, width=np.diff(edges) * 0.9, marker_color=T.BLUE,
                           marker_line_color=T.BLUE, customdata=np.c_[edges[:-1], edges[1:]],
                           hovertemplate=f"%{{customdata[0]:{x_fmt}}} – %{{customdata[1]:{x_fmt}}}"
                                         "<br>%{y:,} lines<extra></extra>"))
    fig.update_layout(title=title, height=height, xaxis_title=x_title, yaxis_title="Lines")
    format_axis(fig, "int")
    return fig


def shade_gaps(fig: go.Figure, gaps: list[tuple[pd.Timestamp, pd.Timestamp]]) -> None:
    """Neutral band labelled with its dates over each period with no invoices."""
    for a, b in gaps:
        fig.add_vrect(x0=a, x1=b, fillcolor=T.NEUTRAL, opacity=0.25, line_width=0,
                      annotation_text=f"No invoices {a:%d %b}–{b:%d %b}", annotation_position="top left",
                      annotation_font=dict(size=11, color=T.TEXT_2))
