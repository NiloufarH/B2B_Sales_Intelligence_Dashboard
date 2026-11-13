"""Design tokens for the whole dashboard: the pastel palette, the shared Plotly template and the page CSS.

Every colour in the app comes from this module. Streamlit reads `.streamlit/config.toml` before any Python
runs, so that file repeats the base tokens; `tests/test_app.py` checks the two stay in sync.
"""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

from src import config as C

# --------------------------------------------------------------------------- surfaces & text
BG = "#FAF8F5"            # page background (warm off-white)
SURFACE = "#FFFFFF"       # cards, charts, tables
BORDER = "#ECE8E1"
GRID = "#F0EDE8"
TEXT = "#2F2E2B"
TEXT_2 = "#77736B"        # secondary text: labels, axis ticks, captions
WIDGET_BG = "#F4F1EC"     # Streamlit secondaryBackgroundColor (inputs, expander headers)
TABLE_HEADER = "#F7F5F1"
SIDEBAR_BG = "#F2F6FA"    # very light pastel-blue tint
LAND = "#F4F1EC"          # map land fill

# --------------------------------------------------------------------------- signal colours
ACCENT = "#6C9BCF"        # highlights, selected tab, "actual" lines
ACCENT_SOFT = "#DCE7F4"   # header underline, light highlight
POSITIVE = "#6DBE8B"
NEGATIVE = "#E58C8A"
NEUTRAL = "#CFC9BF"       # baselines, unselected bars, shaded gaps

# --------------------------------------------------------------------------- categorical pastels
BLUE, PEACH, MINT, BUTTER, LAVENDER, PINK, TEAL, SAND = PASTEL = [
    "#8FB8DE", "#F4B6A6", "#A8D5BA", "#F7D79B", "#C9B6E4", "#F2A7C3", "#B5D8D6", "#D9C7A7",
]
# Butter and sand are too faint as thin lines on white, so multi-line charts that are not
# about main categories cycle through the stronger pastels first.
SERIES = [BLUE, PEACH, MINT, LAVENDER, PINK, TEAL, BUTTER, SAND]

# Fixed: each main category keeps its colour in every chart, whatever the filters.
CATEGORY_COLORS: dict[str, str] = dict(zip(C.MAIN_CATEGORIES, PASTEL))
DOC_SERIES_COLORS: dict[str, str] = dict(zip(C.DOC_SERIES, SERIES))
GROUP_COLORS: dict[str, str] = dict(zip([g for g, _ in C.CUSTOMER_GROUPS], SERIES))

# Light → medium pastel blue for heatmaps, ABC × XYZ and cohorts. Dark text stays readable on both ends.
SEQUENTIAL = [[0.0, "#F1F6FB"], [1.0, ACCENT]]

FONT = '"Source Sans 3", "Source Sans Pro", -apple-system, "Segoe UI", Roboto, Arial, sans-serif'


def rgba(hex_color: str, alpha: float) -> str:
    """'#6C9BCF', 0.2 -> 'rgba(108,155,207,0.2)' for translucent fills."""
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


# --------------------------------------------------------------------------- Plotly template
_AXIS = dict(gridcolor=GRID, gridwidth=1, showline=False, zeroline=False, ticks="", automargin=True,
             separatethousands=True, tickfont=dict(color=TEXT_2, size=11),
             title=dict(font=dict(color=TEXT_2, size=12)))

pio.templates["pastel"] = go.layout.Template(
    layout=dict(
        font=dict(family=FONT, size=12, color=TEXT),
        # Titles align to the card edge (not the plot area), so long axis labels can't push them out of line.
        title=dict(font=dict(size=15, color=TEXT, weight=600), x=0, xanchor="left", xref="container",
                   pad=dict(l=14, b=6)),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, colorway=SERIES,
        xaxis=_AXIS, yaxis=_AXIS,
        # Anchored to the bottom edge of the figure (not the plot area), so it never sits on the tick labels;
        # Plotly grows the bottom margin to fit however many rows the legend wraps to.
        legend=dict(orientation="h", x=0, xref="container", y=0, yref="container", yanchor="bottom",
                    title_text="", bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_2, size=11),
                    indentation=10),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=BORDER, align="left", showarrow=False,
                        font=dict(family=FONT, size=12, color=TEXT)),
        colorscale=dict(sequential=SEQUENTIAL, sequentialminus=SEQUENTIAL),
        geo=dict(bgcolor=SURFACE, landcolor=LAND, countrycolor=BORDER, coastlinecolor=BORDER,
                 oceancolor=SURFACE, lakecolor=SURFACE, subunitcolor=BORDER),
        separators=".,", margin=dict(l=8, r=16, t=56, b=40), bargap=0.28, barcornerradius=4,
    ),
    data=dict(
        scatter=[go.Scatter(mode="lines", line=dict(width=2.5), marker=dict(size=5))],
        bar=[go.Bar(marker=dict(line=dict(width=1)), textfont=dict(color=TEXT_2))],
        heatmap=[go.Heatmap(colorscale=SEQUENTIAL, xgap=2, ygap=2, textfont=dict(color=TEXT),
                            colorbar=dict(thickness=10, outlinewidth=0, tickfont=dict(color=TEXT_2)))],
        treemap=[go.Treemap(textfont=dict(color=TEXT), marker=dict(line=dict(color=SURFACE, width=2)))],
    ),
)
pio.templates.default = "pastel"

# --------------------------------------------------------------------------- page CSS
CSS = f"""
<style>
.stApp {{ background: {BG}; }}
.block-container {{ padding-top: 2.5rem; padding-left: 2rem; padding-right: 2rem; }}
section[data-testid="stSidebar"] {{ background: {SIDEBAR_BG}; border-right: 1px solid {BORDER}; }}

/* KPI cards */
div[data-testid="stMetric"] {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; padding: 14px 16px;
    box-shadow: 0 1px 2px rgba(47, 46, 43, 0.04), 0 4px 14px rgba(47, 46, 43, 0.05);
}}
/* Labels wrap onto a second line instead of ending in "…" on narrow cards (the label is a <label>). */
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * {{
    color: {TEXT_2}; font-size: 0.85rem; white-space: normal !important; overflow: visible !important;
    text-overflow: clip !important;
}}
div[data-testid="stMetricValue"] {{ color: {TEXT}; font-size: 1.75rem; font-weight: 700; }}
div[data-testid="stMetricValue"] > div {{ overflow: visible; text-overflow: clip; }}

/* Section headers */
div[data-testid="stHeading"] h1 {{ color: {TEXT}; font-weight: 700; }}
div[data-testid="stHeading"] h3 {{
    color: {TEXT}; font-size: 1.2rem; font-weight: 600; margin-top: 1.25rem;
    padding-bottom: 0.4rem; border-bottom: 2px solid {ACCENT_SOFT};
}}

/* Charts, tables and expanders sit on white cards */
div[data-testid="stPlotlyChart"] {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; overflow: hidden;
}}
div[data-testid="stDataFrame"] {{ border-radius: 10px; overflow: hidden; }}
div[data-testid="stExpander"] details {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}

/* Tabs */
div[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap: 0.25rem; border-bottom: 1px solid {BORDER}; }}
div[data-testid="stTabs"] [data-baseweb="tab"] {{ padding: 0.5rem 0.9rem; color: {TEXT_2}; }}
div[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {{ color: {ACCENT}; font-weight: 600; }}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{ background-color: {ACCENT}; }}

/* Callouts */
div[data-testid="stAlert"] {{ border-radius: 10px; }}
</style>
"""
