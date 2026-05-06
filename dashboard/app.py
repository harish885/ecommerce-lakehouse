"""
Executive dashboard for the Azure E-Commerce Lakehouse.

Run:
    streamlit run dashboard/app.py
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = PROJECT_ROOT / "data" / "gold"

GOLD_TABLES = {
    "daily_sales": "daily_sales/daily_sales.parquet",
    "monthly_revenue": "monthly_revenue/monthly_revenue.parquet",
    "customer_lifetime_value": ("customer_lifetime_value/customer_lifetime_value.parquet"),
    "product_performance": "product_performance/product_performance.parquet",
    "seller_performance": "seller_performance/seller_performance.parquet",
    "delivery_delay_analysis": ("delivery_delay_analysis/delivery_delay_analysis.parquet"),
    "payment_behavior": "payment_behavior/payment_behavior.parquet",
    "review_score_analysis": "review_score_analysis/review_score_analysis.parquet",
    "regional_sales": "regional_sales/regional_sales.parquet",
}


st.set_page_config(
    page_title="Azure E-Commerce Lakehouse",
    page_icon=":bar_chart:",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_gold_table(table_name: str) -> pd.DataFrame:
    file_path = GOLD_PATH / GOLD_TABLES[table_name]
    if not file_path.exists():
        raise FileNotFoundError(f"Gold table not found: {file_path}")
    return pd.read_parquet(file_path)


@st.cache_data(show_spinner=False)
def load_gold_tables() -> dict[str, pd.DataFrame]:
    return {table_name: load_gold_table(table_name) for table_name in GOLD_TABLES}


def money(value: float) -> str:
    return f"R$ {value:,.0f}"


def number(value: float) -> str:
    return f"{value:,.0f}"


def pct(value: float) -> str:
    return f"{value:,.1f}%"


def section_header(title: str, caption: str) -> None:
    st.subheader(title)
    st.caption(caption)


def build_sidebar(daily_sales: pd.DataFrame, regional_sales: pd.DataFrame) -> tuple:
    st.sidebar.title("Filters")
    st.sidebar.caption("Gold-layer analytics from Olist marketplace data.")

    daily_sales = daily_sales.copy()
    daily_sales["order_purchase_date"] = pd.to_datetime(daily_sales["order_purchase_date"])

    min_date = daily_sales["order_purchase_date"].min().date()
    max_date = daily_sales["order_purchase_date"].max().date()
    date_range = st.sidebar.date_input(
        "Order date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if len(date_range) != 2:
        date_range = (min_date, max_date)

    states = sorted(regional_sales["customer_state"].dropna().unique().tolist())
    selected_states = st.sidebar.multiselect(
        "Customer states",
        options=states,
        default=states,
    )

    min_revenue = int(regional_sales["total_payment_value"].min())
    max_revenue = int(regional_sales["total_payment_value"].max())
    city_revenue_range = st.sidebar.slider(
        "City revenue range",
        min_value=min_revenue,
        max_value=max_revenue,
        value=(min_revenue, max_revenue),
        step=1000,
    )

    return date_range, selected_states, city_revenue_range


def filter_daily_sales(daily_sales: pd.DataFrame, date_range: tuple) -> pd.DataFrame:
    start_date, end_date = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
    daily_sales = daily_sales.copy()
    daily_sales["order_purchase_date"] = pd.to_datetime(daily_sales["order_purchase_date"])
    return daily_sales[daily_sales["order_purchase_date"].between(start_date, end_date)].copy()


def filter_regional_sales(
    regional_sales: pd.DataFrame,
    selected_states: list[str],
    city_revenue_range: tuple[int, int],
) -> pd.DataFrame:
    low, high = city_revenue_range
    return regional_sales[
        regional_sales["customer_state"].isin(selected_states)
        & regional_sales["total_payment_value"].between(low, high)
    ].copy()


def render_kpis(daily_sales: pd.DataFrame, clv: pd.DataFrame) -> None:
    total_revenue = daily_sales["total_payment_value"].sum()
    total_orders = daily_sales["total_orders"].sum()
    unique_customers = clv["customer_unique_id"].nunique()
    avg_order_value = daily_sales["total_payment_value"].sum() / total_orders if total_orders else 0
    repeat_rate = clv["repeat_customer_flag"].mean() * 100

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Revenue", money(total_revenue))
    col2.metric("Orders", number(total_orders))
    col3.metric("Customers", number(unique_customers))
    col4.metric("AOV", money(avg_order_value))
    col5.metric("Repeat Customers", pct(repeat_rate))


def render_revenue_tab(daily_sales: pd.DataFrame, monthly_revenue: pd.DataFrame) -> None:
    section_header(
        "Revenue Trends",
        "Sales momentum, order volume, average order value, and customer growth.",
    )

    daily_fig = px.line(
        daily_sales,
        x="order_purchase_date",
        y="total_payment_value",
        labels={
            "order_purchase_date": "Date",
            "total_payment_value": "Revenue",
        },
        title="Daily Revenue",
    )
    daily_fig.update_traces(line_color="#2563eb", line_width=2)
    daily_fig.update_layout(hovermode="x unified")
    st.plotly_chart(daily_fig, use_container_width=True)

    col1, col2 = st.columns(2)
    monthly_fig = px.bar(
        monthly_revenue,
        x="order_purchase_month",
        y="total_payment_value",
        labels={
            "order_purchase_month": "Month",
            "total_payment_value": "Revenue",
        },
        title="Monthly Revenue",
        color="avg_review_score",
        color_continuous_scale="Blues",
    )
    col1.plotly_chart(monthly_fig, use_container_width=True)

    aov_fig = go.Figure()
    aov_fig.add_trace(
        go.Scatter(
            x=monthly_revenue["order_purchase_month"],
            y=monthly_revenue["avg_order_value"],
            mode="lines+markers",
            name="AOV",
            line={"color": "#16a34a", "width": 3},
        )
    )
    aov_fig.update_layout(
        title="Average Order Value",
        xaxis_title="Month",
        yaxis_title="AOV",
    )
    col2.plotly_chart(aov_fig, use_container_width=True)


def render_customer_tab(clv: pd.DataFrame, regional_sales: pd.DataFrame) -> None:
    section_header(
        "Customer Value",
        "High-value customers, repeat behavior, and geographic concentration.",
    )

    col1, col2 = st.columns([1.1, 0.9])
    top_customers = clv.head(20).copy()
    customer_fig = px.bar(
        top_customers.sort_values("total_payment_value"),
        x="total_payment_value",
        y="customer_unique_id",
        orientation="h",
        labels={
            "total_payment_value": "CLV",
            "customer_unique_id": "Customer",
        },
        title="Top 20 Customers by Lifetime Value",
        color="repeat_customer_flag",
        color_discrete_map={True: "#16a34a", False: "#94a3b8"},
    )
    col1.plotly_chart(customer_fig, use_container_width=True)

    state_summary = (
        regional_sales.groupby("customer_state", as_index=False)
        .agg(
            total_payment_value=("total_payment_value", "sum"),
            total_orders=("total_orders", "sum"),
            unique_customers=("unique_customers", "sum"),
        )
        .sort_values("total_payment_value", ascending=False)
        .head(15)
    )
    state_fig = px.bar(
        state_summary,
        x="customer_state",
        y="total_payment_value",
        labels={
            "customer_state": "State",
            "total_payment_value": "Revenue",
        },
        title="Top States by Revenue",
        color="total_orders",
        color_continuous_scale="Teal",
    )
    col2.plotly_chart(state_fig, use_container_width=True)

    st.dataframe(
        top_customers[
            [
                "customer_unique_id",
                "customer_city",
                "customer_state",
                "total_orders",
                "total_payment_value",
                "avg_order_value",
                "avg_review_score",
                "repeat_customer_flag",
            ]
        ],
        hide_index=True,
        use_container_width=True,
    )


def render_product_seller_tab(
    product_performance: pd.DataFrame,
    seller_performance: pd.DataFrame,
) -> None:
    section_header(
        "Products and Sellers",
        "Category contribution, seller leaderboard, freight, and item economics.",
    )

    category_summary = (
        product_performance.groupby("product_category_name_english", as_index=False)
        .agg(
            product_revenue=("product_revenue", "sum"),
            total_items_sold=("total_items_sold", "sum"),
            unique_sellers=("unique_sellers", "sum"),
        )
        .sort_values("product_revenue", ascending=False)
        .head(20)
    )

    col1, col2 = st.columns(2)
    category_fig = px.bar(
        category_summary.sort_values("product_revenue"),
        x="product_revenue",
        y="product_category_name_english",
        orientation="h",
        labels={
            "product_revenue": "Revenue",
            "product_category_name_english": "Category",
        },
        title="Top Categories by Revenue",
        color="total_items_sold",
        color_continuous_scale="Viridis",
    )
    col1.plotly_chart(category_fig, use_container_width=True)

    top_sellers = seller_performance.head(20)
    seller_fig = px.bar(
        top_sellers.sort_values("product_revenue"),
        x="product_revenue",
        y="seller_id",
        orientation="h",
        labels={"product_revenue": "Revenue", "seller_id": "Seller"},
        title="Top Sellers by Product Revenue",
        color="unique_customers",
        color_continuous_scale="Oranges",
    )
    col2.plotly_chart(seller_fig, use_container_width=True)

    st.dataframe(
        seller_performance[
            [
                "seller_id",
                "seller_city",
                "seller_state",
                "total_orders",
                "total_items_sold",
                "product_revenue",
                "freight_revenue",
                "unique_products",
                "unique_customers",
            ]
        ].head(50),
        hide_index=True,
        use_container_width=True,
    )


def render_operations_tab(
    delivery_delay: pd.DataFrame,
    payment_behavior: pd.DataFrame,
    review_score: pd.DataFrame,
) -> None:
    section_header(
        "Operations and Experience",
        "Delivery delay, payment behavior, and customer satisfaction signals.",
    )

    col1, col2 = st.columns(2)
    delay_state = (
        delivery_delay.groupby("customer_state", as_index=False)
        .agg(
            total_orders=("total_orders", "sum"),
            late_orders=("late_orders", "sum"),
            avg_delivery_days=("avg_delivery_days", "mean"),
            avg_review_score=("avg_review_score", "mean"),
        )
        .assign(
            late_order_rate_pct=lambda df: (
                df["late_orders"] / df["total_orders"].replace(0, pd.NA) * 100
            )
        )
        .sort_values("late_order_rate_pct", ascending=False)
        .head(15)
    )
    delay_fig = px.bar(
        delay_state,
        x="customer_state",
        y="late_order_rate_pct",
        labels={
            "customer_state": "State",
            "late_order_rate_pct": "Late Order Rate",
        },
        title="Late Delivery Rate by State",
        color="avg_review_score",
        color_continuous_scale="RdYlGn",
    )
    col1.plotly_chart(delay_fig, use_container_width=True)

    payment_tree = payment_behavior[payment_behavior["total_payment_value"].fillna(0) > 0].copy()
    payment_tree["installment_bucket"] = payment_tree["installment_bucket"].astype(str)
    payment_fig = px.treemap(
        payment_tree,
        path=["payment_type", "installment_bucket"],
        values="total_payment_value",
        color="avg_payment_value",
        color_continuous_scale="Blues",
        title="Payment Value by Type and Installments",
    )
    col2.plotly_chart(payment_fig, use_container_width=True)

    review_fig = px.bar(
        review_score,
        x="review_score",
        y="review_count",
        color="has_comment",
        barmode="group",
        labels={
            "review_score": "Review Score",
            "review_count": "Reviews",
            "has_comment": "Has Comment",
        },
        title="Review Distribution",
        color_discrete_map={True: "#2563eb", False: "#94a3b8"},
    )
    st.plotly_chart(review_fig, use_container_width=True)


def render_region_tab(regional_sales: pd.DataFrame) -> None:
    section_header(
        "Regional Sales",
        "City and state contribution, delivery quality, and local AOV patterns.",
    )

    col1, col2 = st.columns([1, 1])
    city_fig = px.scatter(
        regional_sales.head(500),
        x="total_orders",
        y="total_payment_value",
        size="unique_customers",
        color="customer_state",
        hover_data=["customer_city", "avg_order_value", "late_order_rate_pct"],
        labels={
            "total_orders": "Orders",
            "total_payment_value": "Revenue",
            "unique_customers": "Customers",
        },
        title="City Revenue vs Order Volume",
    )
    col1.plotly_chart(city_fig, use_container_width=True)

    city_rank = regional_sales.head(25).sort_values("total_payment_value")
    city_rank_fig = px.bar(
        city_rank,
        x="total_payment_value",
        y="customer_city",
        orientation="h",
        color="customer_state",
        labels={"total_payment_value": "Revenue", "customer_city": "City"},
        title="Top Cities by Revenue",
    )
    col2.plotly_chart(city_rank_fig, use_container_width=True)

    st.dataframe(
        regional_sales[
            [
                "customer_state",
                "customer_city",
                "total_orders",
                "unique_customers",
                "total_payment_value",
                "avg_order_value",
                "avg_review_score",
                "avg_delivery_days",
                "late_order_rate_pct",
            ]
        ].head(100),
        hide_index=True,
        use_container_width=True,
    )


def main() -> None:
    st.title("Azure E-Commerce Lakehouse")
    st.caption(
        "Executive analytics dashboard powered by Gold Parquet marts from the "
        "Brazilian Olist e-commerce dataset."
    )

    try:
        tables = load_gold_tables()
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.info("Run `python src/transformation/gold_transformations.py` first.")
        return

    daily_sales = tables["daily_sales"]
    monthly_revenue = tables["monthly_revenue"]
    clv = tables["customer_lifetime_value"]
    product_performance = tables["product_performance"]
    seller_performance = tables["seller_performance"]
    delivery_delay = tables["delivery_delay_analysis"]
    payment_behavior = tables["payment_behavior"]
    review_score = tables["review_score_analysis"]
    regional_sales = tables["regional_sales"]

    date_range, selected_states, city_revenue_range = build_sidebar(daily_sales, regional_sales)
    filtered_daily = filter_daily_sales(daily_sales, date_range)
    filtered_regional = filter_regional_sales(regional_sales, selected_states, city_revenue_range)

    render_kpis(filtered_daily, clv)

    tab_revenue, tab_customer, tab_product, tab_ops, tab_region = st.tabs(
        [
            "Revenue",
            "Customers",
            "Products and Sellers",
            "Operations",
            "Regions",
        ]
    )

    with tab_revenue:
        render_revenue_tab(filtered_daily, monthly_revenue)
    with tab_customer:
        render_customer_tab(clv, filtered_regional)
    with tab_product:
        render_product_seller_tab(product_performance, seller_performance)
    with tab_ops:
        render_operations_tab(delivery_delay, payment_behavior, review_score)
    with tab_region:
        render_region_tab(filtered_regional)


if __name__ == "__main__":
    main()
