from __future__ import annotations

from html import escape
from pathlib import Path
import sqlite3
import subprocess
import sys
from urllib.parse import quote, unquote

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="AlphaLens",
    page_icon="AL",
    layout="wide",
    initial_sidebar_state="expanded",
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "db" / "market.db"
CSS_PATH = Path(__file__).resolve().with_name("styles.css")
PIPELINE_SCRIPT = PROJECT_ROOT / "run_pipeline.py"

BUY_THRESHOLD = 0.15
SELL_THRESHOLD = -0.15
NAV_ITEMS = ("Overview", "Sentiment", "Prices", "Signals", "News")

COLORS = {
    "bg": "#04060B",
    "panel": "#0A0E18",
    "card": "#0E1320",
    "surface": "#121828",
    "text": "#F1F5F9",
    "secondary": "#94A3B8",
    "muted": "#64748B",
    "faint": "#475569",
    "dim": "#334155",
    "blue": "#4F8CFF",
    "cyan": "#22D3EE",
    "violet": "#8B5CF6",
    "positive": "#34D399",
    "neutral": "#FBBF24",
    "negative": "#F87171",
}

CHART_PALETTE = [
    "#4F8CFF",  # blue
    "#22D3EE",  # cyan
    "#8B5CF6",  # violet
    "#F87171",  # red
    "#FBBF24",  # amber
    "#34D399",  # green
    "#94A3B8",  # slate
]

PLOTLY_CONFIG = {"displayModeBar": False, "responsive": True}


# ---------------------------------------------------------------------------
# CSS helpers
# ---------------------------------------------------------------------------

def _read_css() -> str:
    """Read the stylesheet once and return it as a string."""
    with CSS_PATH.open("r", encoding="utf-8") as css_file:
        return css_file.read()


_CSS_TEXT: str = _read_css()


def load_css() -> None:
    """Inject the CSS into the main Streamlit page."""
    st.markdown(f"<style>{_CSS_TEXT}</style>", unsafe_allow_html=True)


def styled_html(html: str) -> None:
    """Render HTML via st.html with the project stylesheet embedded.

    st.html() renders into its own sandboxed iframe. This means:
    - CSS must be embedded inside each call (the parent page's CSS won't apply).
    - Tags like <article>, <nav>, <em> render correctly (unlike st.markdown
      which sanitizes them away in Streamlit 1.49+).
    - Each call is self-contained — never open a tag in one call and close
      it in another.
    """
    st.html(f"<style>{_CSS_TEXT}</style>\n{html}")


def run_pipeline() -> None:
    """Execute the AlphaLens pipeline and handle UI feedback."""

    if not PIPELINE_SCRIPT.is_file():
        st.error(f"Pipeline script not found: {PIPELINE_SCRIPT}")
        return

    with st.spinner(
        "Running pipeline — fetching news, analyzing sentiment, generating signals..."
    ):
        try:

            VENV_PYTHON = Path(
                "D:/AlphaLens/venv/Scripts/python.exe"
            )

            result = subprocess.run(
                [str(VENV_PYTHON), str(PIPELINE_SCRIPT)],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=900,
            )

        except subprocess.TimeoutExpired:
            st.error(
                "Pipeline timed out after 15 minutes."
            )
            return

        except Exception as e:
            st.error(
                f"Failed to run pipeline: {e}"
            )
            return

    if result.returncode == 0:

        st.success(
            "Pipeline completed — market intelligence updated."
        )

        load_data.clear()

        st.rerun()

    else:

        st.error(
            "Pipeline failed — one or more stages did not complete."
        )

        if result.stderr and result.stderr.strip():

            with st.expander(
                "Show error details",
                expanded=True
            ):
                st.code(
                    result.stderr,
                    language="text"
                )

        elif result.stdout and result.stdout.strip():

            with st.expander(
                "Show pipeline output",
                expanded=True
            ):
                st.code(
                    result.stdout,
                    language="text"
                )

# ---------------------------------------------------------------------------
# Data loading — backend logic (unchanged)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        news = pd.read_sql_query(
            """
            SELECT id, title, source, published_at
            FROM news
            ORDER BY published_at DESC
            """,
            conn,
        )
        sentiment = pd.read_sql_query(
            """
            SELECT
                id,
                ticker,
                title,
                sentiment_label,
                sentiment_score,
                sentiment_value,
                analyzed_at
            FROM sentiment
            ORDER BY analyzed_at DESC, id DESC
            """,
            conn,
        )
        prices = pd.read_sql_query(
            """
            SELECT id, symbol, date, close_price, volume
            FROM prices
            ORDER BY symbol, date
            """,
            conn,
        )

    return news, sentiment, prices


def prepare_data(
    news: pd.DataFrame,
    sentiment: pd.DataFrame,
    prices: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    news = news.copy()
    sentiment = sentiment.copy()
    prices = prices.copy()

    if not news.empty:
        news["published_at"] = pd.to_datetime(news["published_at"], errors="coerce", utc=True)
        news["source"] = news["source"].fillna("Unknown")

    if not sentiment.empty:
        sentiment["ticker"] = sentiment["ticker"].fillna("UNKNOWN").astype(str).str.strip().str.upper()
        sentiment["sentiment_label"] = sentiment["sentiment_label"].fillna("neutral").astype(str).str.lower()
        sentiment["sentiment_score"] = pd.to_numeric(sentiment["sentiment_score"], errors="coerce")
        sentiment["sentiment_value"] = pd.to_numeric(sentiment["sentiment_value"], errors="coerce").fillna(0.0)
        sentiment["analyzed_at"] = pd.to_datetime(sentiment["analyzed_at"], errors="coerce")

    if not prices.empty:
        prices["symbol"] = prices["symbol"].fillna("UNKNOWN").astype(str).str.strip().str.upper()
        prices["date"] = pd.to_datetime(prices["date"], errors="coerce", utc=True)
        prices["close_price"] = pd.to_numeric(prices["close_price"], errors="coerce")
        prices["volume"] = pd.to_numeric(prices["volume"], errors="coerce")
        prices = prices.dropna(subset=["symbol", "date", "close_price", "volume"])
        prices = prices.sort_values(["symbol", "date"])

    joined = pd.DataFrame()
    if not sentiment.empty:
        joined = sentiment.merge(
            news[["title", "source", "published_at"]],
            on="title",
            how="left",
        )

    return news, sentiment, prices, joined


def generate_signal(score: float) -> str:
    if score >= BUY_THRESHOLD:
        return "BUY"
    if score <= SELL_THRESHOLD:
        return "SELL"
    return "HOLD"


def state_for_signal(signal: str) -> str:
    return {"BUY": "positive", "SELL": "negative", "HOLD": "neutral"}.get(signal, "neutral")


def state_for_score(score: float) -> str:
    if score >= BUY_THRESHOLD:
        return "positive"
    if score <= SELL_THRESHOLD:
        return "negative"
    return "neutral"


def color_for_score(score: float) -> str:
    return COLORS[state_for_score(score)]


def format_number(value: float | int) -> str:
    if pd.isna(value):
        return "0"
    value = float(value)
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{int(value)}"


def format_datetime(value: pd.Timestamp | None) -> str:
    if value is None or pd.isna(value):
        return "Unavailable"
    if getattr(value, "tzinfo", None) is not None:
        value = value.tz_convert("UTC")
    return value.strftime("%b %d, %Y %H:%M UTC")


def format_date(value: pd.Timestamp | None) -> str:
    if value is None or pd.isna(value):
        return "Unavailable"
    return value.strftime("%b %d, %Y")


def build_sentiment_summary(sentiment: pd.DataFrame) -> pd.DataFrame:
    if sentiment.empty:
        return pd.DataFrame(columns=["ticker", "news_count", "avg_sentiment", "avg_model_score", "signal"])

    summary = sentiment.groupby("ticker", as_index=False).agg(
        news_count=("title", "count"),
        avg_sentiment=("sentiment_value", "mean"),
        avg_model_score=("sentiment_score", "mean"),
        positive_count=("sentiment_label", lambda labels: int((labels == "positive").sum())),
        neutral_count=("sentiment_label", lambda labels: int((labels == "neutral").sum())),
        negative_count=("sentiment_label", lambda labels: int((labels == "negative").sum())),
    )
    summary["signal"] = summary["avg_sentiment"].apply(generate_signal)
    return summary.sort_values(["avg_sentiment", "news_count"], ascending=[False, False]).reset_index(drop=True)


def get_current_section() -> str:
    raw_section = st.query_params.get("section", "Overview")
    if isinstance(raw_section, list):
        raw_section = raw_section[0] if raw_section else "Overview"
    section = unquote(str(raw_section))
    return section if section in NAV_ITEMS else "Overview"


# ---------------------------------------------------------------------------
# Chart theming — publication quality
# ---------------------------------------------------------------------------

def theme_chart(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, -apple-system, sans-serif", "color": COLORS["faint"], "size": 11},
        margin={"l": 4, "r": 12, "t": 6, "b": 18},
        hoverlabel={
            "bgcolor": "#0E1320",
            "bordercolor": "rgba(255,255,255,0.08)",
            "font_color": COLORS["text"],
            "font_family": "Inter, sans-serif",
            "font_size": 12,
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.04,
            "xanchor": "right",
            "x": 1,
            "font": {"size": 11, "color": COLORS["muted"], "family": "Inter, sans-serif"},
            "itemsizing": "constant",
            "tracegroupgap": 12,
        },
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(148,163,184,0.04)",
        gridwidth=0.5,
        zeroline=False,
        color=COLORS["faint"],
        title_font={"size": 10, "color": COLORS["dim"]},
        tickfont={"size": 10, "color": COLORS["dim"]},
        linecolor="rgba(255,255,255,0.04)",
        linewidth=0.5,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(148,163,184,0.03)",
        gridwidth=0.5,
        zeroline=False,
        color=COLORS["faint"],
        tickfont={"size": 10, "family": "Inter, sans-serif", "color": COLORS["faint"]},
        title_font={"size": 10, "color": COLORS["dim"]},
    )
    return fig


# ---------------------------------------------------------------------------
# Reusable UI components
# ---------------------------------------------------------------------------

def empty_state(message: str) -> None:
    styled_html(
        f"""
        <div class="empty-state">
            <div class="empty-label">No data</div>
            <div class="empty-msg">{escape(message)}</div>
        </div>
        """
    )


def section_title(eyebrow: str, title: str, description: str = "") -> None:
    desc_html = f'<div class="heading-desc">{escape(description)}</div>' if description else ""
    styled_html(
        f"""
        <div class="section-heading">
            <div class="heading-left">
                <div class="eyebrow">{escape(eyebrow)}</div>
                <h2>{escape(title)}</h2>
            </div>
            {desc_html}
        </div>
        """
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar(section: str, total_news: int, tracked_tickers: int, last_update: str) -> None:
    nav_meta = {
        "Overview": "OV",
        "Sentiment": "SE",
        "Prices": "PR",
        "Signals": "SI",
        "News": "NW",
    }
    nav_links = []
    for item in NAV_ITEMS:
        active_class = " active" if item == section else ""
        nav_links.append(
            f"""
            <a class="app-nav-item{active_class}" href="?section={quote(item)}" target="_self">
                <div class="nav-icon">{nav_meta[item]}</div>
                <div class="nav-label">{item}</div>
            </a>
            """
        )

    with st.sidebar:
        styled_html(
            f"""
            <div class="sidebar-brand">
                <div class="brand-mark">AL</div>
                <div>
                    <div class="sidebar-brand-name">AlphaLens</div>
                    <div class="sidebar-brand-sub">Market Intelligence</div>
                </div>
            </div>
            <nav class="app-nav-list">{''.join(nav_links)}</nav>
            <div class="sidebar-status">
                <div class="meta-label">System status</div>
                <div class="meta-value"><span class="status-dot"></span>Connected</div>
            </div>
            <div class="sidebar-meta-grid">
                <div><div class="meta-label">Headlines</div><div class="meta-value">{total_news}</div></div>
                <div><div class="meta-label">Tickers</div><div class="meta-value">{tracked_tickers}</div></div>
            </div>
            <div class="sidebar-footer">
                <div class="meta-label">Last analysis</div>
                <p>{escape(last_update)}</p>
            </div>
            """
        )


# ---------------------------------------------------------------------------
# Hero banner
# ---------------------------------------------------------------------------

def render_top_bar(tickers: list[str], latest_news: str, latest_price: str) -> tuple[str, str, str]:
    styled_html(
        f"""
        <div class="hero-banner">
            <div class="hero-content">
                <div class="hero-identity">
                    <div class="hero-brand">AlphaLens</div>
                    <div class="hero-tagline">Turning Financial News into Actionable Intelligence</div>
                </div>
                <div class="freshness-strip">
                    <span class="fresh-label">Latest news</span>
                    <span class="fresh-value">{escape(latest_news)}</span>
                    <span class="fresh-label">Latest price</span>
                    <span class="fresh-value">{escape(latest_price)}</span>
                </div>
            </div>
        </div>
        """
    )

    # --- Refresh button row ---
    refresh_col, spacer = st.columns([1, 4])
    with refresh_col:
        if st.button("🔄  Refresh Market Intelligence", use_container_width=True):
            run_pipeline()

    c1, c2, c3 = st.columns([2.2, 1, 1])
    with c1:
        search = st.text_input("Search headlines", placeholder="Search company, source, or headline")
    with c2:
        ticker = st.selectbox("Ticker", ["All tickers"] + tickers)
    with c3:
        sort_mode = st.selectbox("News sort", ["Latest", "Strongest sentiment"])
    return ticker, search, sort_mode


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------

def kpi_card(label: str, value: str, detail: str, status: str, state: str, primary: bool = False, highlight: bool = False) -> None:
    cls = "kpi-card animate-in"
    if primary:
        cls += " primary"
    elif highlight:
        cls += " highlight"
    styled_html(
        f"""
        <div class="{cls}">
            <div class="kpi-topline">
                <div class="kpi-label">{escape(label)}</div>
                <div class="status-pill {state}">{escape(status)}</div>
            </div>
            <div class="kpi-value">{escape(value)}</div>
            <div class="kpi-detail">{escape(detail)}</div>
        </div>
        """
    )


def render_kpis(
    total_news: int,
    analyzed_news: int,
    tracked_tickers: int,
    market_sentiment: float,
    top_signal_row: pd.Series | None,
    summary: pd.DataFrame,
) -> None:
    mood_state = state_for_score(market_sentiment)
    mood_label = {"positive": "Bullish", "neutral": "Neutral", "negative": "Bearish"}[mood_state]

    buy_count = int((summary["signal"] == "BUY").sum()) if not summary.empty else 0
    sell_count = int((summary["signal"] == "SELL").sum()) if not summary.empty else 0
    hold_count = int((summary["signal"] == "HOLD").sum()) if not summary.empty else 0
    ratio_state = "positive" if buy_count > sell_count else "negative" if sell_count > buy_count else "neutral"

    if top_signal_row is None:
        top_value = "—"
        top_detail = "No signal data"
        top_state = "neutral"
    else:
        top_value = f"{top_signal_row['ticker']} {top_signal_row['signal']}"
        top_detail = f"Sentiment {float(top_signal_row['avg_sentiment']):.3f}"
        top_state = state_for_signal(str(top_signal_row["signal"]))

    cols = st.columns(5)
    with cols[0]:
        kpi_card("Market mood", f"{market_sentiment:.3f}", "Avg. analyzed sentiment", mood_label, mood_state, primary=True)
    with cols[1]:
        kpi_card("News analyzed", format_number(analyzed_news), f"{format_number(total_news)} collected", "Active", "positive")
    with cols[2]:
        kpi_card("Tracked tickers", format_number(tracked_tickers), "Price or sentiment coverage", "Coverage", "neutral")
    with cols[3]:
        kpi_card("Buy / Sell", f"{buy_count}:{sell_count}", f"{hold_count} hold", "Mix", ratio_state)
    with cols[4]:
        kpi_card("Top signal", top_value, top_detail, "Signal", top_state, highlight=True)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def sentiment_chart(summary: pd.DataFrame) -> None:
    section_title("Sentiment", "Company sentiment ranking", "Average headline sentiment by ticker.")
    if summary.empty:
        empty_state("No sentiment rows are available yet.")
        return

    chart_df = summary.sort_values("avg_sentiment", ascending=True)
    bar_colors = [color_for_score(v) for v in chart_df["avg_sentiment"]]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=chart_df["avg_sentiment"],
            y=chart_df["ticker"],
            orientation="h",
            width=0.48,
            marker={
                "color": bar_colors,
                "line": {"width": 0, "color": "rgba(0,0,0,0)"},
                "cornerradius": 3,
                "opacity": 0.85,
            },
            text=[f"{v:+.3f}" for v in chart_df["avg_sentiment"]],
            textposition="outside",
            textfont={"family": "Inter Tight, Inter, sans-serif", "size": 11, "color": COLORS["muted"]},
            cliponaxis=False,
            hovertemplate="%{y}  %{x:+.3f}<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_width=0.5, line_color="rgba(148,163,184,0.15)")
    fig.add_vrect(x0=BUY_THRESHOLD, x1=1, fillcolor="rgba(52,211,153,0.02)", line_width=0)
    fig.add_vrect(x0=-1, x1=SELL_THRESHOLD, fillcolor="rgba(248,113,113,0.02)", line_width=0)
    fig.update_layout(bargap=0.35)
    fig.update_xaxes(title="Sentiment score", range=[-1, 1])
    fig.update_yaxes(
        title="",
        automargin=True,
        tickfont={"size": 12, "color": COLORS["secondary"], "family": "Inter Tight, Inter, sans-serif"},
    )
    st.plotly_chart(theme_chart(fig, 300), use_container_width=True, config=PLOTLY_CONFIG)


def signal_engine(summary: pd.DataFrame) -> None:
    section_title("Signals", "Signal engine", "Buy, Hold, and Sell thresholds applied by ticker.")
    if summary.empty:
        empty_state("No signal rows are available yet.")
        return

    ranked = summary.copy()
    ranked["signal_strength"] = ranked["avg_sentiment"].abs()
    ranked = ranked.sort_values(["signal_strength", "news_count"], ascending=[False, False])

    cards = []
    for rank, (_, row) in enumerate(ranked.iterrows(), 1):
        signal = str(row["signal"])
        state = state_for_signal(signal)
        score = float(row["avg_sentiment"])
        confidence = float(row["avg_model_score"]) if not pd.isna(row["avg_model_score"]) else 0.0
        meter_width = min(abs(score) * 100, 100)
        conf_cls = " high-confidence" if confidence >= 0.85 else ""
        cards.append(
            f"""
            <div class="signal-card {state}{conf_cls}">
                <div class="signal-head">
                    <div class="signal-info">
                        <div class="signal-ticker">{escape(str(row['ticker']))}</div>
                        <div class="signal-type">{escape(signal)}</div>
                    </div>
                    <div class="status-pill {state}">{escape(signal)}</div>
                </div>
                <div class="signal-body">
                    <div class="stat-group"><div class="stat-label">Score</div><div class="stat-value">{score:+.3f}</div></div>
                    <div class="stat-group"><div class="stat-label">Headlines</div><div class="stat-value">{int(row['news_count'])}</div></div>
                    <div class="stat-group"><div class="stat-label">Confidence</div><div class="stat-value">{confidence:.2f}</div></div>
                </div>
                <div class="signal-meter {state}"><div class="meter-fill" style="width: {meter_width:.1f}%"></div></div>
            </div>
            """
        )

    styled_html(f"<div class='signal-stack'>{''.join(cards)}</div>")


def price_chart(prices: pd.DataFrame, selected_ticker: str) -> None:
    section_title("Prices", "Price trend")
    if prices.empty:
        empty_state("No price rows are available yet.")
        return

    fig = go.Figure()
    if selected_ticker == "All tickers":
        for idx, (symbol, symbol_df) in enumerate(prices.groupby("symbol", sort=True)):
            symbol_df = symbol_df.sort_values("date")
            first_close = symbol_df["close_price"].iloc[0]
            indexed_close = (symbol_df["close_price"] / first_close) * 100
            fig.add_trace(
                go.Scatter(
                    x=symbol_df["date"],
                    y=indexed_close,
                    mode="lines",
                    name=symbol,
                    line={"width": 1.8, "color": CHART_PALETTE[idx % len(CHART_PALETTE)]},
                    hovertemplate=f"<b>{symbol}</b>  %{{x|%b %d}}  %{{y:.1f}}<extra></extra>",
                )
            )
        fig.update_yaxes(title="Indexed close (100 = start)")
    else:
        prices = prices.sort_values("date")
        fig.add_trace(
            go.Scatter(
                x=prices["date"],
                y=prices["close_price"],
                mode="lines",
                name=selected_ticker,
                line={"width": 2, "color": COLORS["cyan"]},
                fill="tozeroy",
                fillcolor="rgba(34,211,238,0.04)",
                hovertemplate="<b>%{x|%b %d, %Y}</b>  $%{y:.2f}<extra></extra>",
            )
        )
        fig.update_yaxes(title="Close ($)")
    fig.update_xaxes(title="")
    st.plotly_chart(theme_chart(fig, 280), use_container_width=True, config=PLOTLY_CONFIG)


def news_distribution(joined: pd.DataFrame) -> None:
    section_title("Coverage", "News distribution")
    if joined.empty:
        empty_state("No analyzed news rows are available yet.")
        return

    distribution = (
        joined[joined["ticker"] != "UNKNOWN"]
        .groupby("ticker", as_index=False)
        .agg(news_count=("title", "count"))
        .sort_values("news_count", ascending=False)
    )

    if distribution.empty:
        empty_state("No mapped company news available.")
        return

    fig = go.Figure(
        data=[
            go.Pie(
                labels=distribution["ticker"],
                values=distribution["news_count"],
                hole=0.70,
                marker={
                    "colors": CHART_PALETTE[: len(distribution)],
                    "line": {"color": "rgba(0,0,0,0.3)", "width": 1},
                },
                textinfo="label+percent",
                textfont={"family": "Inter, sans-serif", "size": 11, "color": COLORS["secondary"]},
                hovertemplate="<b>%{label}</b>  %{value} articles  %{percent}<extra></extra>",
                pull=[0.02] * len(distribution),
            )
        ]
    )
    st.plotly_chart(theme_chart(fig, 280), use_container_width=True, config=PLOTLY_CONFIG)


def news_feed(joined: pd.DataFrame, search: str, sort_mode: str) -> None:
    section_title("News", "Latest intelligence feed")
    if joined.empty:
        empty_state("No joined news and sentiment rows are available yet.")
        return

    feed = joined[
        joined["ticker"] != "UNKNOWN"
    ].copy()
    if search.strip():
        query = search.strip().lower()
        searchable = (
            feed["title"].fillna("").astype(str)
            + " "
            + feed["source"].fillna("").astype(str)
            + " "
            + feed["ticker"].fillna("").astype(str)
        ).str.lower()
        feed = feed[searchable.str.contains(query, regex=False)]

    if sort_mode == "Strongest sentiment":
        feed = feed.assign(strength=feed["sentiment_value"].abs()).sort_values("strength", ascending=False)
    else:
        feed = feed.sort_values("published_at", ascending=False, na_position="last")

    feed = feed.head(12)
    if feed.empty:
        empty_state("No headlines match the current search.")
        return

    rows = []
    for _, row in feed.iterrows():
        value = float(row.get("sentiment_value", 0.0) or 0.0)
        state = state_for_score(value)
        source = escape(str(row.get('source', 'Unknown')))
        date = escape(format_date(row.get('published_at')))
        rows.append(
            f"""
            <div class="feed-row">
                <div class="feed-ticker">{escape(str(row.get('ticker', 'UNKNOWN')))}</div>
                <div class="feed-title">
                    <div class="headline">{escape(str(row.get('title', 'Untitled headline')))}</div>
                    <div class="source-line">{source} &middot; {date}</div>
                </div>
                <div class="feed-score">
                    <div class="sentiment-chip {state}">{escape(str(row.get('sentiment_label', 'neutral')).title())}</div>
                    <div class="score-value">{value:+.3f}</div>
                </div>
            </div>
            """
        )
    styled_html(f"<div class='feed-table'>{''.join(rows)}</div>")


def source_coverage(joined: pd.DataFrame) -> None:
    section_title("Sources", "Source coverage")
    if joined.empty:
        empty_state("No source coverage is available yet.")
        return
    top_sources = (
        joined.groupby("source", as_index=False)
        .agg(total=("title", "count"))
        .sort_values("total", ascending=False)
        .head(8)
    )
    fig = go.Figure(
        data=[
            go.Bar(
                x=top_sources["total"],
                y=top_sources["source"],
                orientation="h",
                width=0.50,
                marker={
                    "color": COLORS["blue"],
                    "line": {"width": 0, "color": "rgba(0,0,0,0)"},
                    "cornerradius": 3,
                    "opacity": 0.80,
                },
                hovertemplate="<b>%{y}</b>  %{x} articles<extra></extra>",
            )
        ]
    )
    fig.update_yaxes(
        autorange="reversed",
        tickfont={"size": 11, "color": COLORS["secondary"], "family": "Inter, sans-serif"},
    )
    st.plotly_chart(theme_chart(fig, 300), use_container_width=True, config=PLOTLY_CONFIG)


def price_cards(prices: pd.DataFrame) -> None:
    if prices.empty:
        return
    latest_rows = prices.sort_values("date").groupby("symbol", as_index=False).tail(1).sort_values("symbol")
    cards = []
    for _, row in latest_rows.iterrows():
        cards.append(
            f"""
            <div class="price-card">
                <div class="price-symbol">{escape(str(row['symbol']))}</div>
                <div class="price-value">${float(row['close_price']):,.2f}</div>
                <div class="price-meta">{escape(format_date(row['date']))} &middot; Vol {format_number(row['volume'])}</div>
            </div>
            """
        )
    styled_html(f"<div class='price-grid'>{''.join(cards)}</div>")


# ---------------------------------------------------------------------------
# Data filtering
# ---------------------------------------------------------------------------

def filter_dashboard_data(
    summary: pd.DataFrame,
    joined: pd.DataFrame,
    prices: pd.DataFrame,
    selected_ticker: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if selected_ticker == "All tickers":
        return summary, joined, prices
    filtered_summary = summary[summary["ticker"] == selected_ticker]
    filtered_joined = joined[joined["ticker"] == selected_ticker] if not joined.empty else joined
    filtered_prices = prices[prices["symbol"] == selected_ticker] if not prices.empty else prices
    return filtered_summary, filtered_joined, filtered_prices


def panel():
    return st.container(border=True)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main() -> None:
    load_css()

    try:
        raw_news, raw_sentiment, raw_prices = load_data()
    except Exception as exc:
        st.error(f"Unable to load AlphaLens data: {exc}")
        return

    news, sentiment, prices, joined = prepare_data(raw_news, raw_sentiment, raw_prices)
    summary = build_sentiment_summary(sentiment)

    total_news = int(len(news))
    analyzed_news = int(len(sentiment))
    tracked_tickers = int(
        len(
            set(prices["symbol"].dropna().unique()).union(
                set(summary.loc[summary["ticker"] != "UNKNOWN", "ticker"].dropna().unique())
            )
        )
    )

    latest_news = format_datetime(news["published_at"].max() if not news.empty else None)
    latest_price = format_date(prices["date"].max() if not prices.empty else None)
    latest_analysis = format_datetime(sentiment["analyzed_at"].max() if not sentiment.empty else None)

    market_sentiment = float(sentiment["sentiment_value"].mean()) if not sentiment.empty else 0.0

    top_signal_row = None
    if not summary.empty:
        signal_rank = summary.copy()
        signal_rank["signal_strength"] = signal_rank["avg_sentiment"].abs()
        top_signal_row = signal_rank.sort_values(["signal_strength", "news_count"], ascending=[False, False]).iloc[0]

    section = get_current_section()
    render_sidebar(section, total_news, tracked_tickers, latest_analysis)

    tickers = sorted(
        set(prices["symbol"].dropna().unique()).union(set(summary["ticker"].dropna().unique())) - {"UNKNOWN"}
    )
    selected_ticker, search, sort_mode = render_top_bar(tickers, latest_news, latest_price)
    filtered_summary, filtered_joined, filtered_prices = filter_dashboard_data(summary, joined, prices, selected_ticker)

    render_kpis(total_news, analyzed_news, tracked_tickers, market_sentiment, top_signal_row, filtered_summary)

    if section == "Overview":
        primary_col, signal_col = st.columns([1.6, 1])
        with primary_col:
            with panel():
                sentiment_chart(filtered_summary)
        with signal_col:
            with panel():
                signal_engine(filtered_summary)

        price_col, news_col = st.columns([1.15, 1])
        with price_col:
            with panel():
                price_chart(filtered_prices, selected_ticker)
        with news_col:
            with panel():
                news_distribution(filtered_joined)

        with panel():
            news_feed(filtered_joined, search, sort_mode)

    elif section == "Sentiment":
        left, right = st.columns([1.35, 1])
        with left:
            with panel():
                sentiment_chart(filtered_summary)
        with right:
            with panel():
                news_distribution(filtered_joined)

    elif section == "Prices":
        with panel():
            price_chart(filtered_prices, selected_ticker)
        price_cards(filtered_prices if selected_ticker != "All tickers" else prices)

    elif section == "Signals":
        with panel():
            signal_engine(filtered_summary)

    elif section == "News":
        source_col, feed_col = st.columns([0.85, 1.5])
        with source_col:
            with panel():
                source_coverage(filtered_joined)
        with feed_col:
            with panel():
                news_feed(filtered_joined, search, sort_mode)


if __name__ == "__main__":
    main()
