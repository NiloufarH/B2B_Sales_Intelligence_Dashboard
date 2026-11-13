"""All aggregations and models. Every public function takes the hashable ``Filters`` and is cached,
so a page rerun only recomputes what a filter change actually touched."""
from __future__ import annotations

import warnings
from collections.abc import Callable

import numpy as np
import pandas as pd
import streamlit as st
from mlxtend.frequent_patterns import apriori, association_rules
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from src import config as C
from src.data import Filters, filtered, full_week_range, load_data

warnings.filterwarnings("ignore", module="statsmodels")
OBS = dict(observed=True)  # groupby on categoricals: skip empty categories


def _plain(df: pd.DataFrame) -> pd.DataFrame:
    """Turn categorical columns of an aggregate into plain strings so charts/tables sort and compare freely."""
    cats = df.select_dtypes("category").columns
    return df.astype({c: str for c in cats}) if len(cats) else df


# =========================================================================== shared
@st.cache_data(show_spinner=False)
def kpis(f: Filters) -> dict[str, float]:
    """Headline numbers for the selection."""
    df = filtered(f)
    revenue = float(df["Revenue"].sum())
    invoices = df["InvoiceNo"].nunique()
    list_value = float(df["ListValue"].sum())
    return {
        "revenue": revenue,
        "invoices": invoices,
        "customers": df["CustomerID"].nunique(),
        "aov": revenue / invoices if invoices else 0.0,
        "units": float(df["Quantity"].sum()),
        "discount": 1 - revenue / list_value if list_value else 0.0,
    }


@st.cache_data(show_spinner=False)
def weekly_series(f: Filters, value: str = "Revenue") -> pd.Series:
    """Weekly totals over complete weeks only, with zero for weeks without invoices."""
    df = filtered(f)
    return df.groupby("Week")[value].sum().reindex(full_week_range(f), fill_value=0.0).astype(float)


@st.cache_data(show_spinner=False)
def data_gaps(f: Filters) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Periods longer than ``DATA_GAP_DAYS`` without any invoice."""
    days = pd.Series(filtered(f)["InvoiceDate"].unique()).sort_values()
    gaps = days.diff().dt.days
    return [(days.iloc[i - 1] + pd.Timedelta(days=1), days.iloc[i] - pd.Timedelta(days=1))
            for i in np.flatnonzero(gaps > C.DATA_GAP_DAYS)]


@st.cache_data(show_spinner=False)
def shutdown_weeks() -> pd.DatetimeIndex:
    """Mondays of the weeks that overlap a pause with no invoices in the full data (20 and 27 Jul 2020)."""
    days = pd.Series(load_data()["InvoiceDate"].unique()).sort_values()
    gaps = days.diff().dt.days
    weeks: list[pd.Timestamp] = []
    for i in np.flatnonzero(gaps > C.DATA_GAP_DAYS):
        start, end = days.iloc[i - 1] + pd.Timedelta(days=1), days.iloc[i] - pd.Timedelta(days=1)
        weeks += list(pd.date_range(start - pd.Timedelta(days=start.weekday()), end, freq="W-MON"))
    return pd.DatetimeIndex(weeks)


HOLT_SIGMA_WEEKS = 16  # residual window for the band: recent errors, not the whole year


def holt(y: pd.Series, horizon: int) -> pd.DataFrame | None:
    """Holt additive-trend forecast with an approximate 95% band (±1.96·σ·√h).

    The shutdown weeks are interpolated before fitting so the July pause does not distort the trend,
    and σ comes from the last 16 weeks of residuals.
    """
    if len(y) < 10 or y.sum() == 0:
        return None
    gap = y.index.isin(shutdown_weeks())
    if gap.any() and not gap.all():
        y = y.mask(gap).interpolate(limit_direction="both")
    fit = ExponentialSmoothing(y.values, trend="add", initialization_method="estimated").fit()
    idx = pd.date_range(y.index[-1] + pd.Timedelta(weeks=1), periods=horizon, freq="W-MON")
    mean = np.clip(fit.forecast(horizon), 0, None)
    band = 1.96 * np.std(fit.resid[-HOLT_SIGMA_WEEKS:]) * np.sqrt(np.arange(1, horizon + 1))
    return pd.DataFrame({"mean": mean, "lo": np.clip(mean - band, 0, None), "hi": mean + band}, index=idx)


@st.cache_data(show_spinner=False)
def weekly_forecast(f: Filters, value: str = "Revenue", horizon: int = C.FORECAST_WEEKS) -> pd.DataFrame | None:
    """Cached Holt forecast of a weekly total."""
    return holt(weekly_series(f, value), horizon)


@st.cache_data(show_spinner=False)
def main_category_summary(f: Filters) -> pd.DataFrame:
    """Revenue, units and share per main category."""
    g = filtered(f).groupby("MainCategory", **OBS).agg(Revenue=("Revenue", "sum"), Units=("Quantity", "sum"),
                                                       Lines=("Revenue", "size"))
    g["Share"] = g["Revenue"] / g["Revenue"].sum()
    return _plain(g.sort_values("Revenue", ascending=False).reset_index())


# =========================================================================== sales
@st.cache_data(show_spinner=False)
def city_summary(f: Filters) -> pd.DataFrame:
    """Revenue, customers and units per province with coordinates."""
    g = filtered(f).groupby("City", **OBS).agg(Revenue=("Revenue", "sum"), Units=("Quantity", "sum"),
                                                Customers=("CustomerID", "nunique")).reset_index()
    g = _plain(g)
    g["Share"] = g["Revenue"] / g["Revenue"].sum()
    g["UnitShare"] = g["Units"] / g["Units"].sum()
    g["lat"] = g["City"].map(lambda c: C.PROVINCE_COORDS.get(c, (np.nan, np.nan))[0])
    g["lon"] = g["City"].map(lambda c: C.PROVINCE_COORDS.get(c, (np.nan, np.nan))[1])
    return g.sort_values("Revenue", ascending=False).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def category_summary(f: Filters) -> pd.DataFrame:
    """Revenue per detailed category with its main category."""
    g = filtered(f).groupby(["Category", "MainCategory"], **OBS).agg(
        Revenue=("Revenue", "sum"), Units=("Quantity", "sum"), Products=("StockCode", "nunique")).reset_index()
    g["Share"] = g["Revenue"] / g["Revenue"].sum()
    return _plain(g.sort_values("Revenue", ascending=False).reset_index(drop=True))


@st.cache_data(show_spinner=False)
def best_sellers(f: Filters, n: int) -> pd.DataFrame:
    """Top-n products by revenue."""
    df = filtered(f)
    g = df.groupby("StockCode", **OBS).agg(Revenue=("Revenue", "sum"), Units=("Quantity", "sum"),
                                            Customers=("CustomerID", "nunique"))
    top = g.nlargest(n, "Revenue")
    info = (df[df["StockCode"].isin(top.index)].drop_duplicates("StockCode")
            .set_index("StockCode")[["Description", "Category", "MainCategory"]])
    top = top.join(info)
    top["Share"] = top["Revenue"] / g["Revenue"].sum()
    return _plain(top.reset_index())


@st.cache_data(show_spinner=False)
def monthly_by(f: Filters, col: str) -> pd.DataFrame:
    """Monthly revenue split by a column (long format)."""
    return _plain(filtered(f).groupby(["Month", col], **OBS)["Revenue"].sum().reset_index())


@st.cache_data(show_spinner=False)
def discount_by(f: Filters, col: str) -> pd.DataFrame:
    """Revenue-weighted discount per group."""
    g = filtered(f).groupby(col, **OBS).agg(Revenue=("Revenue", "sum"), ListValue=("ListValue", "sum"))
    g["Discount"] = 1 - g["Revenue"] / g["ListValue"]
    return _plain(g.reset_index())


@st.cache_data(show_spinner=False)
def discount_by_order_size(f: Filters) -> pd.DataFrame:
    """Revenue-weighted discount by invoice-value band."""
    inv = filtered(f).groupby("InvoiceNo", **OBS).agg(Revenue=("Revenue", "sum"), ListValue=("ListValue", "sum"))
    bands = [0, 250, 1_000, 5_000, 20_000, np.inf]
    labels = ["< 250", "250–1K", "1K–5K", "5K–20K", "20K +"]
    inv["Band"] = pd.cut(inv["Revenue"], bands, labels=labels, right=False)
    g = inv.groupby("Band", **OBS).agg(Invoices=("Revenue", "size"), Revenue=("Revenue", "sum"),
                                        ListValue=("ListValue", "sum"))
    g["Discount"] = 1 - g["Revenue"] / g["ListValue"]
    return g.reset_index()


@st.cache_data(show_spinner=False)
def weekday_month(f: Filters) -> pd.DataFrame:
    """Revenue pivot: weekday rows × month columns."""
    df = filtered(f)
    p = df.pivot_table(index=df["InvoiceDate"].dt.day_of_week, columns=df["Month"].dt.strftime("%b"),
                       values="Revenue", aggfunc="sum", fill_value=0, observed=True)
    months = pd.date_range("2020-01-01", periods=12, freq="MS").strftime("%b")
    p = p.reindex(columns=[m for m in months if m in p.columns])
    p.index = [["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][i] for i in p.index]
    return p


# =========================================================================== customers
def _segment(r: int, fm: int) -> str:
    """Name an RFM cell using recency and the average of frequency/monetary scores."""
    if r >= 4 and fm >= 4:
        return "Champions"
    if r == 3 and fm >= 4:
        return "Loyal Customers"
    if r >= 4 and fm >= 2:
        return "Potential Loyalists"
    if r == 5:
        return "New Customers"
    if r == 4:
        return "Promising"
    if r == 3:
        return "Need Attention" if fm == 3 else "About to Sleep"
    if fm == 5:
        return "Can't Lose Them"
    if fm >= 3:
        return "At Risk"
    return "Hibernating" if r == 2 else "Lost"


@st.cache_data(show_spinner=False)
def rfm(f: Filters) -> pd.DataFrame:
    """Per-customer recency/frequency/monetary with quintile scores and a named segment."""
    df = filtered(f)
    snapshot = pd.Timestamp(f.end) + pd.Timedelta(days=1)
    t = df.groupby("CustomerID", **OBS).agg(
        LastBuy=("InvoiceDate", "max"), Frequency=("InvoiceNo", "nunique"), Monetary=("Revenue", "sum"),
        City=("City", "first"), Group=("CustomerGroup", "first"))
    if len(t) < 10:
        return pd.DataFrame()
    t["Recency"] = (snapshot - t["LastBuy"]).dt.days
    for col, ascending in (("Recency", False), ("Frequency", True), ("Monetary", True)):
        ranks = t[col].rank(method="first", ascending=ascending)
        t[col[0]] = pd.qcut(ranks, 5, labels=[1, 2, 3, 4, 5]).astype(int)
    t["FM"] = ((t["F"] + t["M"]) / 2).round().astype(int)
    t["Segment"] = [_segment(r, fm) for r, fm in zip(t["R"], t["FM"])]
    t["Action"] = t["Segment"].map(C.RFM_SEGMENT_ACTIONS)
    return _plain(t.reset_index())


@st.cache_resource(max_entries=8, show_spinner="Clustering customers…")
def kmeans_rfm(f: Filters) -> dict | None:
    """K-Means on log + standardised RFM; k in 2..8 chosen by silhouette score."""
    t = rfm(f)
    if len(t) < 30:
        return None
    X = StandardScaler().fit_transform(np.log1p(t[["Recency", "Frequency", "Monetary"]]))
    scores, models = {}, {}
    for k in range(2, 9):
        km = KMeans(n_clusters=k, n_init=10, random_state=C.RANDOM_STATE).fit(X)
        scores[k], models[k] = silhouette_score(X, km.labels_), km
    best = max(scores, key=scores.get)
    labels = models[best].labels_
    # Name clusters 1..k by average monetary value so the highest-value cluster is always "Cluster 1".
    order = pd.Series(t["Monetary"].values).groupby(labels).mean().sort_values(ascending=False).index
    rename = {old: f"Cluster {i + 1}" for i, old in enumerate(order)}
    out = t[["CustomerID", "Recency", "Frequency", "Monetary"]].copy()
    out["Cluster"] = [rename[l] for l in labels]
    out[["PC1", "PC2"]] = PCA(n_components=2, random_state=C.RANDOM_STATE).fit_transform(X)
    profile = out.groupby("Cluster").agg(Customers=("CustomerID", "size"), AvgRecency=("Recency", "mean"),
                                         AvgFrequency=("Frequency", "mean"), AvgMonetary=("Monetary", "mean"),
                                         Revenue=("Monetary", "sum"))
    profile["RevenueShare"] = profile["Revenue"] / profile["Revenue"].sum()
    return {"k": best, "scores": scores, "points": out, "profile": profile.reset_index()}


@st.cache_data(show_spinner=False)
def pareto(f: Filters) -> tuple[pd.DataFrame, float, int]:
    """Cumulative revenue curve (≤ 300 points), top-20% share and customers needed for 80%."""
    rev = filtered(f).groupby("CustomerID", **OBS)["Revenue"].sum().sort_values(ascending=False)
    cum = (rev.cumsum() / rev.sum()).to_numpy()
    n = len(cum)
    x = np.arange(1, n + 1) / n
    idx = np.unique(np.linspace(0, n - 1, min(n, 300)).astype(int))
    top20 = float(cum[max(int(np.ceil(n * 0.2)) - 1, 0)])
    n80 = int(np.searchsorted(cum, 0.8) + 1)
    return pd.DataFrame({"x": np.r_[0, x[idx]], "y": np.r_[0, cum[idx]]}), top20, n80


@st.cache_data(show_spinner="Mining association rules…")
def basket_rules(f: Filters, min_support: float = 0.01) -> pd.DataFrame:
    """Apriori on invoice × main category; rules sorted by lift."""
    df = filtered(f)
    basket = pd.crosstab(df["InvoiceNo"], df["MainCategory"]).gt(0)
    basket.columns = basket.columns.astype(str)
    if basket.shape[0] < 50 or basket.shape[1] < 2:
        return pd.DataFrame()
    items = apriori(basket, min_support=min_support, use_colnames=True, max_len=2)  # simple A → B pairs
    if items.empty or items["itemsets"].map(len).max() < 2:
        return pd.DataFrame()
    rules = association_rules(items, num_itemsets=len(basket), metric="lift", min_threshold=1.0)
    rules["Antecedent"] = rules["antecedents"].map(lambda s: " + ".join(sorted(s)))
    rules["Consequent"] = rules["consequents"].map(lambda s: " + ".join(sorted(s)))
    return (rules[["Antecedent", "Consequent", "support", "confidence", "lift"]]
            .sort_values("lift", ascending=False).reset_index(drop=True))


@st.cache_data(show_spinner=False)
def cohort_retention(f: Filters) -> pd.DataFrame:
    """Share of each first-purchase-month cohort that buys again N months later."""
    df = filtered(f)[["CustomerID", "Month"]].drop_duplicates()
    first = df.groupby("CustomerID", **OBS)["Month"].min().rename("Cohort")
    df = df.join(first, on="CustomerID")
    df["Age"] = ((df["Month"].dt.year - df["Cohort"].dt.year) * 12 + df["Month"].dt.month - df["Cohort"].dt.month)
    counts = df.pivot_table(index="Cohort", columns="Age", values="CustomerID", aggfunc="nunique", observed=True)
    ret = counts.div(counts[0], axis=0)
    ret.index = [f"{d:%b} (n={int(n)})" for d, n in zip(ret.index, counts[0])]
    return ret


# =========================================================================== supply chain
@st.cache_data(show_spinner=False)
def weekly_units_matrix(f: Filters, by: str) -> pd.DataFrame:
    """Weekly units: rows = weeks (full weeks, zero-filled), columns = values of ``by``."""
    weeks = full_week_range(f)
    df = filtered(f)
    df = df[df["Week"].isin(weeks)]
    m = df.groupby(["Week", by], **OBS)["Quantity"].sum().unstack(fill_value=0)
    return m.reindex(weeks, fill_value=0).astype(float)


def monthly_units_matrix(f: Filters, by: str) -> pd.DataFrame:
    """Monthly units: rows = months lying completely inside the selection (zero-filled), columns = ``by``."""
    start, end = pd.Timestamp(f.start), pd.Timestamp(f.end)
    first = start if start.day == 1 else start + pd.offsets.MonthBegin(1)
    months = pd.date_range(first, end + pd.Timedelta(days=1) - pd.offsets.MonthBegin(1), freq="MS")
    months = months[months + pd.offsets.MonthEnd(0) <= end]
    df = filtered(f)
    df = df[df["Month"].isin(months)]
    m = df.groupby(["Month", by], **OBS)["Quantity"].sum().unstack(fill_value=0)
    return m.reindex(months, fill_value=0).astype(float)


@st.cache_data(show_spinner="Classifying products…")
def abc_xyz(f: Filters) -> pd.DataFrame:
    """ABC by revenue share and XYZ by coefficient of variation of monthly units, per product."""
    df = filtered(f)
    prod = df.groupby("StockCode", **OBS).agg(Revenue=("Revenue", "sum"), Units=("Quantity", "sum"))
    prod = prod.sort_values("Revenue", ascending=False)
    cum = prod["Revenue"].cumsum() / prod["Revenue"].sum()
    prod["ABC"] = np.select([cum <= C.ABC_CUTS[0], cum <= C.ABC_CUTS[1]], ["A", "B"], "C")
    monthly = monthly_units_matrix(f, "StockCode")
    if len(monthly) < 2:
        return pd.DataFrame()
    mean, std = monthly.mean(), monthly.std(ddof=0)
    cv = (std / mean.replace(0, np.nan)).reindex(prod.index)
    prod["CV"] = cv
    prod["XYZ"] = np.select([cv < C.XYZ_CUTS[0], cv <= C.XYZ_CUTS[1]], ["X", "Y"], "Z")
    prod["Class"] = prod["ABC"] + prod["XYZ"]
    return _plain(prod.reset_index())


@st.cache_data(show_spinner=False)
def category_forecasts(f: Filters, horizon: int = C.FORECAST_WEEKS) -> dict[str, pd.DataFrame]:
    """Holt forecast of weekly units for each main category."""
    m = weekly_units_matrix(f, "MainCategory")
    return {str(c): fc for c in m.columns if (fc := holt(m[c], horizon)) is not None}


@st.cache_data(show_spinner=False)
def slow_movers(f: Filters) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(products sold on a single invoice line, products with no sale in the last 90 days)."""
    df = filtered(f)
    g = df.groupby("StockCode", **OBS).agg(Lines=("Revenue", "size"), Units=("Quantity", "sum"),
                                            Revenue=("Revenue", "sum"), LastSale=("InvoiceDate", "max"),
                                            Description=("Description", "first"), Category=("Category", "first"))
    cutoff = pd.Timestamp(f.end) - pd.Timedelta(days=C.SLOW_MOVER_DAYS)
    g["DaysSinceSale"] = (pd.Timestamp(f.end) - g["LastSale"]).dt.days
    single = g[g["Lines"] == 1].sort_values("Revenue", ascending=False)
    stale = g[g["LastSale"] < cutoff].sort_values("Revenue", ascending=False)
    return _plain(single.reset_index()), _plain(stale.reset_index())


@st.cache_data(show_spinner=False)
def top_products_by_units(f: Filters, n: int = 200) -> pd.DataFrame:
    """Products with the most units, for the safety-stock picker."""
    df = filtered(f)
    g = df.groupby("StockCode", **OBS).agg(Units=("Quantity", "sum"), Description=("Description", "first"))
    return _plain(g.nlargest(n, "Units").reset_index())


@st.cache_data(show_spinner=False)
def product_weekly_units(f: Filters, stock_code: str) -> pd.Series:
    """Weekly units of one product (full weeks, zero-filled)."""
    df = filtered(f)
    s = df.loc[df["StockCode"] == stock_code].groupby("Week")["Quantity"].sum()
    return s.reindex(full_week_range(f), fill_value=0.0).astype(float)


# =========================================================================== forecasting
def _rf_row(history: list[float], when: pd.Timestamp) -> list[float]:
    """Features: ISO week, month, lags 1–4 and their mean."""
    lags = history[-1:-5:-1]
    return [when.isocalendar().week, when.month, *lags, float(np.mean(lags))]


def _forecast_rf(y: pd.Series, future: pd.DatetimeIndex) -> np.ndarray:
    """Random forest on calendar + lag features, forecast recursively."""
    X = np.array([_rf_row(list(y.iloc[:i]), y.index[i]) for i in range(4, len(y))])
    model = RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=C.RANDOM_STATE)
    model.fit(X, y.iloc[4:].to_numpy())
    history, preds = list(y), []
    for when in future:
        p = float(model.predict(np.array([_rf_row(history, when)]))[0])
        preds.append(p)
        history.append(p)
    return np.array(preds)


def _forecast_holt(y: pd.Series, future: pd.DatetimeIndex) -> np.ndarray:
    """Holt additive trend (statsmodels)."""
    fit = ExponentialSmoothing(y.values, trend="add", initialization_method="estimated").fit()
    return np.clip(fit.forecast(len(future)), 0, None)


MODELS: dict[str, Callable[[pd.Series, pd.DatetimeIndex], np.ndarray]] = {
    "Naive": lambda y, fut: np.repeat(y.iloc[-1], len(fut)),
    "Moving average (4 wk)": lambda y, fut: np.repeat(y.iloc[-4:].mean(), len(fut)),
    "Holt": _forecast_holt,
    "Random forest": _forecast_rf,
}


def _future_index(y: pd.Series, horizon: int) -> pd.DatetimeIndex:
    return pd.date_range(y.index[-1] + pd.Timedelta(weeks=1), periods=horizon, freq="W-MON")


@st.cache_resource(max_entries=8, show_spinner="Back-testing forecast models…")
def backtest(f: Filters) -> dict | None:
    """Fit each model on all but the last ``TEST_WEEKS`` weeks and score it on them."""
    y = weekly_series(f)
    if len(y) < C.TEST_WEEKS + 12:
        return None
    train, test = y.iloc[:-C.TEST_WEEKS], y.iloc[-C.TEST_WEEKS:]
    preds, metrics = {}, []
    nonzero = test.to_numpy() > 0
    for name, fn in MODELS.items():
        p = fn(train, test.index)
        preds[name] = pd.Series(p, index=test.index)
        err = test.to_numpy() - p
        mape = float(np.mean(np.abs(err[nonzero]) / test.to_numpy()[nonzero])) if nonzero.any() else np.nan
        metrics.append({"Model": name, "MAPE": mape, "RMSE": float(np.sqrt(np.mean(err ** 2)))})
    return {"y": y, "test": test, "preds": preds, "metrics": pd.DataFrame(metrics).sort_values("MAPE")}


@st.cache_data(show_spinner="Forecasting…")
def future_forecasts(f: Filters, horizon: int) -> pd.DataFrame | None:
    """Every model refitted on the full series, forecasting ``horizon`` weeks ahead."""
    y = weekly_series(f)
    if len(y) < C.TEST_WEEKS + 12:
        return None
    fut = _future_index(y, horizon)
    return pd.DataFrame({name: fn(y, fut) for name, fn in MODELS.items()}, index=fut)


@st.cache_data(show_spinner=False)
def daily_stats(f: Filters) -> pd.DataFrame:
    """Revenue, invoices and lines per trading day."""
    return filtered(f).groupby("InvoiceDate").agg(Revenue=("Revenue", "sum"), Invoices=("InvoiceNo", "nunique"),
                                                  Lines=("Revenue", "size"))


@st.cache_data(show_spinner=False)
def anomalies_zscore(f: Filters, threshold: float, window: int = 21) -> pd.DataFrame:
    """Flag days whose revenue is more than ``threshold`` rolling standard deviations from the rolling mean."""
    d = daily_stats(f).copy()
    roll = d["Revenue"].rolling(window, center=True, min_periods=5)
    d["Expected"] = roll.mean()
    d["Score"] = (d["Revenue"] - d["Expected"]) / roll.std()
    d["Anomaly"] = d["Score"].abs() > threshold
    return d


@st.cache_resource(max_entries=8, show_spinner="Training Isolation Forest…")
def anomalies_iforest(f: Filters, contamination: float) -> pd.DataFrame:
    """Isolation Forest on log revenue, invoices, lines and weekday per day."""
    d = daily_stats(f).copy()
    if len(d) < 20:
        d["Score"], d["Anomaly"], d["Expected"] = np.nan, False, np.nan
        return d
    X = np.c_[np.log1p(d["Revenue"]), np.log1p(d["Invoices"]), np.log1p(d["Lines"]), d.index.day_of_week]
    model = IsolationForest(contamination=contamination, random_state=C.RANDOM_STATE).fit(X)
    d["Score"] = -model.score_samples(X)
    d["Anomaly"] = model.predict(X) == -1
    d["Expected"] = d["Revenue"].rolling(21, center=True, min_periods=5).median()
    return d
