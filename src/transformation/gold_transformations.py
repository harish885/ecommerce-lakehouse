"""
Gold Layer Transformation Pipeline
==================================
Reads Silver Parquet files and creates business-ready analytics tables.

Usage:
    python src/transformation/gold_transformations.py

Output:
    data/gold/{table}/{table}.parquet
    logs/gold_transformation_log.csv
"""

import csv
import os
import sys
from datetime import datetime

import pandas as pd
import yaml
from loguru import logger

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from src.utils.logger import setup_logger

GOLD_TABLES = [
    "daily_sales",
    "monthly_revenue",
    "customer_lifetime_value",
    "product_performance",
    "seller_performance",
    "delivery_delay_analysis",
    "payment_behavior",
    "review_score_analysis",
    "regional_sales",
]


def load_config(path: str = "config/config.yaml") -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def read_silver_table(silver_path: str, table_name: str) -> pd.DataFrame:
    file_path = os.path.join(silver_path, table_name, f"{table_name}_clean.parquet")
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Silver file not found: {file_path}")
    return pd.read_parquet(file_path)


def write_gold_table(df: pd.DataFrame, gold_path: str, table_name: str) -> str:
    out_dir = os.path.join(gold_path, table_name)
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{table_name}.parquet")
    df.to_parquet(out_file, index=False, engine="pyarrow")
    logger.success(f"[{table_name}] Gold -> {out_file} ({len(df):,} rows)")
    return out_file


def write_gold_log(log_path: str, table_name: str, rows_written: int, status: str, error: str = ""):
    os.makedirs(log_path, exist_ok=True)
    log_file = os.path.join(log_path, "gold_transformation_log.csv")
    file_exists = os.path.isfile(log_file)
    with open(log_file, "a", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "table_name",
                "rows_written",
                "status",
                "error_message",
                "execution_timestamp",
            ],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(
            {
                "table_name": table_name,
                "rows_written": rows_written,
                "status": status,
                "error_message": error,
                "execution_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )


def add_date_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["order_purchase_date"] = df["order_purchase_timestamp"].dt.date
    df["order_purchase_month"] = df["order_purchase_timestamp"].dt.to_period("M").astype(str)
    df["order_purchase_year"] = df["order_purchase_timestamp"].dt.year.astype("Int64")
    return df


def build_base_tables(tables: dict) -> dict:
    orders = add_date_columns(tables["orders"])
    customers = tables["customers"]
    order_items = tables["order_items"]
    products = tables["products"]
    sellers = tables["sellers"]
    payments = tables["payments"]
    reviews = tables["reviews"]
    translations = tables["product_category_translation"]

    product_dim = products.merge(translations, on="product_category_name", how="left")
    product_dim["product_category_name_english"] = (
        product_dim["product_category_name_english"]
        .fillna(product_dim["product_category_name"])
        .fillna("unknown")
    )

    order_items_enriched = (
        order_items.merge(
            orders[
                [
                    "order_id",
                    "customer_id",
                    "order_status",
                    "order_purchase_timestamp",
                    "order_purchase_date",
                    "order_purchase_month",
                    "order_purchase_year",
                    "order_delivered_customer_date",
                    "order_estimated_delivery_date",
                ]
            ],
            on="order_id",
            how="left",
        )
        .merge(customers, on="customer_id", how="left")
        .merge(
            product_dim[
                [
                    "product_id",
                    "product_category_name",
                    "product_category_name_english",
                    "product_weight_g",
                    "product_photos_qty",
                ]
            ],
            on="product_id",
            how="left",
        )
        .merge(sellers, on="seller_id", how="left")
    )
    order_items_enriched["item_total_value"] = (
        order_items_enriched["price"] + order_items_enriched["freight_value"]
    )

    payment_by_order = (
        payments.groupby("order_id", as_index=False)
        .agg(
            payment_value=("payment_value", "sum"),
            payment_count=("payment_sequential", "count"),
            max_installments=("payment_installments", "max"),
            payment_types=("payment_type", lambda s: ", ".join(sorted(set(s.dropna())))),
        )
        .fillna({"payment_value": 0})
    )

    items_by_order = (
        order_items.groupby("order_id", as_index=False)
        .agg(
            items_sold=("order_item_id", "count"),
            product_revenue=("price", "sum"),
            freight_revenue=("freight_value", "sum"),
        )
        .fillna({"items_sold": 0, "product_revenue": 0, "freight_revenue": 0})
    )
    items_by_order["item_total_value"] = (
        items_by_order["product_revenue"] + items_by_order["freight_revenue"]
    )

    review_by_order = reviews.groupby("order_id", as_index=False).agg(
        avg_review_score=("review_score", "mean"),
        review_count=("review_id", "count"),
        has_review_comment=("review_comment_message", lambda s: s.notna().any()),
    )

    orders_enriched = (
        orders.merge(customers, on="customer_id", how="left")
        .merge(payment_by_order, on="order_id", how="left")
        .merge(items_by_order, on="order_id", how="left")
        .merge(review_by_order, on="order_id", how="left")
    )
    fill_cols = [
        "payment_value",
        "payment_count",
        "items_sold",
        "product_revenue",
        "freight_revenue",
        "item_total_value",
        "review_count",
    ]
    orders_enriched[fill_cols] = orders_enriched[fill_cols].fillna(0)
    orders_enriched["is_delivered"] = orders_enriched["order_status"].eq("delivered")
    orders_enriched["delivery_days"] = (
        orders_enriched["order_delivered_customer_date"]
        - orders_enriched["order_purchase_timestamp"]
    ).dt.days
    orders_enriched["estimated_delivery_days"] = (
        orders_enriched["order_estimated_delivery_date"]
        - orders_enriched["order_purchase_timestamp"]
    ).dt.days
    orders_enriched["delivery_delay_days"] = (
        orders_enriched["order_delivered_customer_date"]
        - orders_enriched["order_estimated_delivery_date"]
    ).dt.days
    orders_enriched["is_late_delivery"] = orders_enriched["delivery_delay_days"].fillna(0) > 0

    return {
        "orders": orders,
        "orders_enriched": orders_enriched,
        "order_items_enriched": order_items_enriched,
        "payments": payments,
        "reviews": reviews,
    }


def build_daily_sales(base: dict) -> pd.DataFrame:
    orders = base["orders_enriched"]
    daily = orders.groupby("order_purchase_date", as_index=False).agg(
        total_orders=("order_id", "nunique"),
        delivered_orders=("is_delivered", "sum"),
        unique_customers=("customer_unique_id", "nunique"),
        items_sold=("items_sold", "sum"),
        product_revenue=("product_revenue", "sum"),
        freight_revenue=("freight_revenue", "sum"),
        total_payment_value=("payment_value", "sum"),
        avg_order_value=("payment_value", "mean"),
    )
    return daily.sort_values("order_purchase_date")


def build_monthly_revenue(base: dict) -> pd.DataFrame:
    orders = base["orders_enriched"]
    monthly = orders.groupby("order_purchase_month", as_index=False).agg(
        total_orders=("order_id", "nunique"),
        delivered_orders=("is_delivered", "sum"),
        unique_customers=("customer_unique_id", "nunique"),
        items_sold=("items_sold", "sum"),
        product_revenue=("product_revenue", "sum"),
        freight_revenue=("freight_revenue", "sum"),
        total_payment_value=("payment_value", "sum"),
        avg_order_value=("payment_value", "mean"),
        avg_review_score=("avg_review_score", "mean"),
    )
    monthly["revenue_per_customer"] = (
        monthly["total_payment_value"] / monthly["unique_customers"].replace(0, pd.NA)
    ).round(2)
    return monthly.sort_values("order_purchase_month")


def build_customer_lifetime_value(base: dict) -> pd.DataFrame:
    orders = base["orders_enriched"]
    clv = orders.groupby("customer_unique_id", as_index=False).agg(
        customer_state=("customer_state", "first"),
        customer_city=("customer_city", "first"),
        first_order_date=("order_purchase_date", "min"),
        last_order_date=("order_purchase_date", "max"),
        total_orders=("order_id", "nunique"),
        delivered_orders=("is_delivered", "sum"),
        total_items=("items_sold", "sum"),
        total_payment_value=("payment_value", "sum"),
        avg_order_value=("payment_value", "mean"),
        avg_review_score=("avg_review_score", "mean"),
    )
    clv["repeat_customer_flag"] = clv["total_orders"] > 1
    return clv.sort_values("total_payment_value", ascending=False)


def build_product_performance(base: dict) -> pd.DataFrame:
    items = base["order_items_enriched"]
    product = items.groupby(
        ["product_id", "product_category_name", "product_category_name_english"],
        as_index=False,
        dropna=False,
    ).agg(
        total_orders=("order_id", "nunique"),
        total_items_sold=("order_item_id", "count"),
        product_revenue=("price", "sum"),
        freight_revenue=("freight_value", "sum"),
        total_value=("item_total_value", "sum"),
        avg_item_price=("price", "mean"),
        unique_sellers=("seller_id", "nunique"),
    )
    product["product_category_name_english"] = product["product_category_name_english"].fillna(
        "unknown"
    )
    return product.sort_values("product_revenue", ascending=False)


def build_seller_performance(base: dict) -> pd.DataFrame:
    items = base["order_items_enriched"]
    seller = items.groupby(["seller_id", "seller_city", "seller_state"], as_index=False).agg(
        total_orders=("order_id", "nunique"),
        total_items_sold=("order_item_id", "count"),
        product_revenue=("price", "sum"),
        freight_revenue=("freight_value", "sum"),
        total_value=("item_total_value", "sum"),
        avg_item_price=("price", "mean"),
        unique_products=("product_id", "nunique"),
        unique_customers=("customer_unique_id", "nunique"),
    )
    return seller.sort_values("product_revenue", ascending=False)


def build_delivery_delay_analysis(base: dict) -> pd.DataFrame:
    orders = base["orders_enriched"]
    delivered = orders[orders["order_delivered_customer_date"].notna()].copy()
    delivered["delay_status"] = pd.cut(
        delivered["delivery_delay_days"],
        bins=[-10_000, 0, 3, 7, 10_000],
        labels=["on_time_or_early", "late_1_3_days", "late_4_7_days", "late_8_plus_days"],
    )
    delay = delivered.groupby(
        ["customer_state", "delay_status"], as_index=False, observed=True
    ).agg(
        total_orders=("order_id", "nunique"),
        late_orders=("is_late_delivery", "sum"),
        avg_delivery_days=("delivery_days", "mean"),
        avg_estimated_delivery_days=("estimated_delivery_days", "mean"),
        avg_delay_days=("delivery_delay_days", "mean"),
        avg_review_score=("avg_review_score", "mean"),
        total_payment_value=("payment_value", "sum"),
    )
    delay["late_order_rate_pct"] = (
        delay["late_orders"] / delay["total_orders"].replace(0, pd.NA) * 100
    ).round(2)
    return delay.sort_values(["customer_state", "delay_status"])


def build_payment_behavior(base: dict) -> pd.DataFrame:
    payments = base["payments"].merge(
        base["orders_enriched"][
            ["order_id", "order_purchase_month", "customer_state", "avg_review_score"]
        ],
        on="order_id",
        how="left",
    )
    payments["installment_bucket"] = pd.cut(
        payments["payment_installments"].astype(float),
        bins=[0, 1, 3, 6, 12, 10_000],
        labels=["1", "2-3", "4-6", "7-12", "13+"],
    )
    behavior = payments.groupby(
        ["payment_type", "installment_bucket"], as_index=False, observed=True
    ).agg(
        payment_records=("order_id", "count"),
        total_orders=("order_id", "nunique"),
        total_payment_value=("payment_value", "sum"),
        avg_payment_value=("payment_value", "mean"),
        avg_installments=("payment_installments", "mean"),
        avg_review_score=("avg_review_score", "mean"),
    )
    return behavior.sort_values("total_payment_value", ascending=False)


def build_review_score_analysis(base: dict) -> pd.DataFrame:
    reviews = base["reviews"].merge(
        base["orders_enriched"][
            [
                "order_id",
                "order_purchase_month",
                "customer_state",
                "payment_value",
                "delivery_days",
                "delivery_delay_days",
                "is_late_delivery",
            ]
        ],
        on="order_id",
        how="left",
    )
    reviews["has_comment"] = reviews["review_comment_message"].notna()
    score = reviews.groupby(["review_score", "has_comment"], as_index=False).agg(
        review_count=("review_id", "count"),
        total_orders=("order_id", "nunique"),
        avg_payment_value=("payment_value", "mean"),
        avg_delivery_days=("delivery_days", "mean"),
        avg_delay_days=("delivery_delay_days", "mean"),
        late_orders=("is_late_delivery", "sum"),
    )
    score["late_order_rate_pct"] = (
        score["late_orders"] / score["total_orders"].replace(0, pd.NA) * 100
    ).round(2)
    return score.sort_values(["review_score", "has_comment"])


def build_regional_sales(base: dict) -> pd.DataFrame:
    orders = base["orders_enriched"]
    regional = orders.groupby(["customer_state", "customer_city"], as_index=False).agg(
        total_orders=("order_id", "nunique"),
        delivered_orders=("is_delivered", "sum"),
        unique_customers=("customer_unique_id", "nunique"),
        total_items=("items_sold", "sum"),
        total_payment_value=("payment_value", "sum"),
        avg_order_value=("payment_value", "mean"),
        avg_review_score=("avg_review_score", "mean"),
        avg_delivery_days=("delivery_days", "mean"),
        late_orders=("is_late_delivery", "sum"),
    )
    regional["late_order_rate_pct"] = (
        regional["late_orders"] / regional["delivered_orders"].replace(0, pd.NA) * 100
    ).round(2)
    return regional.sort_values("total_payment_value", ascending=False)


BUILDERS = {
    "daily_sales": build_daily_sales,
    "monthly_revenue": build_monthly_revenue,
    "customer_lifetime_value": build_customer_lifetime_value,
    "product_performance": build_product_performance,
    "seller_performance": build_seller_performance,
    "delivery_delay_analysis": build_delivery_delay_analysis,
    "payment_behavior": build_payment_behavior,
    "review_score_analysis": build_review_score_analysis,
    "regional_sales": build_regional_sales,
}


def run_gold_transformations():
    setup_logger()

    logger.info("=" * 60)
    logger.info("  Gold Transformation Pipeline - Starting")
    logger.info("=" * 60)

    config = load_config()
    silver_path = config["paths"]["local"]["silver"]
    gold_path = config["paths"]["local"]["gold"]
    log_path = config["paths"]["local"]["logs"]

    log_file = os.path.join(log_path, "gold_transformation_log.csv")
    if os.path.exists(log_file):
        os.remove(log_file)

    source_tables = [
        "customers",
        "orders",
        "order_items",
        "products",
        "sellers",
        "payments",
        "reviews",
        "product_category_translation",
    ]
    tables = {}
    for table_name in source_tables:
        tables[table_name] = read_silver_table(silver_path, table_name)
        logger.info(f"[{table_name}] Loaded {len(tables[table_name]):,} Silver rows")

    base = build_base_tables(tables)

    results = []
    for table_name in GOLD_TABLES:
        try:
            gold_df = BUILDERS[table_name](base)
            write_gold_table(gold_df, gold_path, table_name)
            write_gold_log(log_path, table_name, len(gold_df), "SUCCESS")
            results.append({"table": table_name, "rows": len(gold_df), "status": "SUCCESS"})
        except Exception as e:
            logger.error(f"[{table_name}] FAILED: {e}")
            write_gold_log(log_path, table_name, 0, "FAILED", str(e))
            results.append({"table": table_name, "rows": 0, "status": f"FAILED: {e}"})

    logger.info("=" * 60)
    logger.info("  Gold Transformation Summary")
    logger.info("=" * 60)
    logger.info(f"{'Gold table':<35} {'Rows':>10} {'Status'}")
    logger.info("-" * 60)
    for result in results:
        logger.info(f"{result['table']:<35} {result['rows']:>10,} {result['status']}")
    logger.info("-" * 60)
    logger.info(f"{'TOTAL':<35} {sum(r['rows'] for r in results):>10,}")
    logger.info(f"Gold log -> {log_file}")
    logger.info("=" * 60)
    logger.info("  Gold Transformation Pipeline - Complete")
    logger.info("=" * 60)

    failed = [r for r in results if not r["status"].startswith("SUCCESS")]
    if failed:
        failed_tables = ", ".join(r["table"] for r in failed)
        raise RuntimeError(f"Gold transformation failed for: {failed_tables}")

    return results


if __name__ == "__main__":
    run_gold_transformations()
