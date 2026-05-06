"""
Gold Layer Transformation Pipeline
==================================
Reads cleaned Silver Parquet files and produces nine business-ready
analytics marts that the Power BI semantic model consumes.

Runs identically against local filesystem and Azure Data Lake Storage Gen2
via the `Storage` abstraction.

Usage
-----
    python -m src.transformation.gold_transformations
    python -m src.transformation.gold_transformations --environment azure

Outputs
-------
    {gold_root}/{table}/{table}.parquet
    {logs_root}/gold_transformation_log.csv
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Callable

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.utils.config import load_config
from src.utils.logger import setup_logger, write_gold_log
from src.utils.storage import (
    AdlsStorage,
    LayerPaths,
    Storage,
    get_storage,
)


# ─────────────────────────────────────────────
# Catalog
# ─────────────────────────────────────────────

# The nine Silver tables we read.
SOURCE_TABLES = (
    "customers",
    "orders",
    "order_items",
    "products",
    "sellers",
    "payments",
    "reviews",
    "product_category_translation",
)

# The nine Gold marts we produce, in build order.
GOLD_TABLES = (
    "daily_sales",
    "monthly_revenue",
    "customer_lifetime_value",
    "product_performance",
    "seller_performance",
    "delivery_delay_analysis",
    "payment_behavior",
    "review_score_analysis",
    "regional_sales",
)


# ─────────────────────────────────────────────
# Storage glue (Silver → Gold)
# ─────────────────────────────────────────────


def _read_silver_table(storage: Storage, silver_root: str, table_name: str) -> pd.DataFrame:
    path = f"{silver_root.rstrip('/')}/{table_name}/{table_name}_clean.parquet"
    if not storage.exists(path):
        raise FileNotFoundError(f"Silver file not found: {path}")
    return storage.read_parquet(path)


def _write_gold_table(storage: Storage, df: pd.DataFrame, gold_root: str, table_name: str) -> str:
    path = f"{gold_root.rstrip('/')}/{table_name}/{table_name}.parquet"
    rows = storage.write_parquet(df, path)
    logger.success(f"[{table_name}] Gold -> {path} ({rows:,} rows)")
    return path


# ─────────────────────────────────────────────
# Base table prep — joined, enriched intermediate frames
# used by the Gold builders.
# ─────────────────────────────────────────────


def _add_purchase_date_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["order_purchase_date"] = df["order_purchase_timestamp"].dt.date
    df["order_purchase_month"] = df["order_purchase_timestamp"].dt.to_period("M").astype(str)
    df["order_purchase_year"] = df["order_purchase_timestamp"].dt.year.astype("Int64")
    return df


def _build_product_dim(products: pd.DataFrame, translations: pd.DataFrame) -> pd.DataFrame:
    """Add an English category name (falling back to Portuguese, then 'unknown')."""
    dim = products.merge(translations, on="product_category_name", how="left")
    dim["product_category_name_english"] = (
        dim["product_category_name_english"].fillna(dim["product_category_name"]).fillna("unknown")
    )
    return dim


def _aggregate_payments_by_order(payments: pd.DataFrame) -> pd.DataFrame:
    return (
        payments.groupby("order_id", as_index=False)
        .agg(
            payment_value=("payment_value", "sum"),
            payment_count=("payment_sequential", "count"),
            max_installments=("payment_installments", "max"),
            payment_types=("payment_type", lambda s: ", ".join(sorted(set(s.dropna())))),
        )
        .fillna({"payment_value": 0})
    )


def _aggregate_items_by_order(order_items: pd.DataFrame) -> pd.DataFrame:
    items = (
        order_items.groupby("order_id", as_index=False)
        .agg(
            items_sold=("order_item_id", "count"),
            product_revenue=("price", "sum"),
            freight_revenue=("freight_value", "sum"),
        )
        .fillna({"items_sold": 0, "product_revenue": 0, "freight_revenue": 0})
    )
    items["item_total_value"] = items["product_revenue"] + items["freight_revenue"]
    return items


def _aggregate_reviews_by_order(reviews: pd.DataFrame) -> pd.DataFrame:
    return reviews.groupby("order_id", as_index=False).agg(
        avg_review_score=("review_score", "mean"),
        review_count=("review_id", "count"),
        has_review_comment=("review_comment_message", lambda s: s.notna().any()),
    )


def _build_orders_enriched(
    orders: pd.DataFrame,
    customers: pd.DataFrame,
    payments_by_order: pd.DataFrame,
    items_by_order: pd.DataFrame,
    reviews_by_order: pd.DataFrame,
) -> pd.DataFrame:
    enriched = (
        orders.merge(customers, on="customer_id", how="left")
        .merge(payments_by_order, on="order_id", how="left")
        .merge(items_by_order, on="order_id", how="left")
        .merge(reviews_by_order, on="order_id", how="left")
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
    enriched[fill_cols] = enriched[fill_cols].fillna(0)
    enriched["is_delivered"] = enriched["order_status"].eq("delivered")
    enriched["delivery_days"] = (
        enriched["order_delivered_customer_date"] - enriched["order_purchase_timestamp"]
    ).dt.days
    enriched["estimated_delivery_days"] = (
        enriched["order_estimated_delivery_date"] - enriched["order_purchase_timestamp"]
    ).dt.days
    enriched["delivery_delay_days"] = (
        enriched["order_delivered_customer_date"] - enriched["order_estimated_delivery_date"]
    ).dt.days
    enriched["is_late_delivery"] = enriched["delivery_delay_days"].fillna(0) > 0
    return enriched


def _build_order_items_enriched(
    order_items: pd.DataFrame,
    orders: pd.DataFrame,
    customers: pd.DataFrame,
    product_dim: pd.DataFrame,
    sellers: pd.DataFrame,
) -> pd.DataFrame:
    enriched = (
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
    enriched["item_total_value"] = enriched["price"] + enriched["freight_value"]
    return enriched


def build_base_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Produce the joined intermediate frames consumed by every Gold builder."""
    orders = _add_purchase_date_columns(tables["orders"])
    product_dim = _build_product_dim(tables["products"], tables["product_category_translation"])

    payments_by_order = _aggregate_payments_by_order(tables["payments"])
    items_by_order = _aggregate_items_by_order(tables["order_items"])
    reviews_by_order = _aggregate_reviews_by_order(tables["reviews"])

    return {
        "orders": orders,
        "orders_enriched": _build_orders_enriched(
            orders=orders,
            customers=tables["customers"],
            payments_by_order=payments_by_order,
            items_by_order=items_by_order,
            reviews_by_order=reviews_by_order,
        ),
        "order_items_enriched": _build_order_items_enriched(
            order_items=tables["order_items"],
            orders=orders,
            customers=tables["customers"],
            product_dim=product_dim,
            sellers=tables["sellers"],
        ),
        "payments": tables["payments"],
        "reviews": tables["reviews"],
    }


# ─────────────────────────────────────────────
# Gold mart builders
# ─────────────────────────────────────────────


def _safe_pct(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return (numerator / denominator.replace(0, pd.NA) * 100).round(2)


def build_daily_sales(base: dict[str, pd.DataFrame]) -> pd.DataFrame:
    daily = (
        base["orders_enriched"]
        .groupby("order_purchase_date", as_index=False)
        .agg(
            total_orders=("order_id", "nunique"),
            delivered_orders=("is_delivered", "sum"),
            unique_customers=("customer_unique_id", "nunique"),
            items_sold=("items_sold", "sum"),
            product_revenue=("product_revenue", "sum"),
            freight_revenue=("freight_revenue", "sum"),
            total_payment_value=("payment_value", "sum"),
            avg_order_value=("payment_value", "mean"),
        )
    )
    return daily.sort_values("order_purchase_date")


def build_monthly_revenue(base: dict[str, pd.DataFrame]) -> pd.DataFrame:
    monthly = (
        base["orders_enriched"]
        .groupby("order_purchase_month", as_index=False)
        .agg(
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
    )
    monthly["revenue_per_customer"] = (
        monthly["total_payment_value"] / monthly["unique_customers"].replace(0, pd.NA)
    ).round(2)
    return monthly.sort_values("order_purchase_month")


def build_customer_lifetime_value(base: dict[str, pd.DataFrame]) -> pd.DataFrame:
    clv = (
        base["orders_enriched"]
        .groupby("customer_unique_id", as_index=False)
        .agg(
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
    )
    clv["repeat_customer_flag"] = clv["total_orders"] > 1
    return clv.sort_values("total_payment_value", ascending=False)


def build_product_performance(base: dict[str, pd.DataFrame]) -> pd.DataFrame:
    product = (
        base["order_items_enriched"]
        .groupby(
            ["product_id", "product_category_name", "product_category_name_english"],
            as_index=False,
            dropna=False,
        )
        .agg(
            total_orders=("order_id", "nunique"),
            total_items_sold=("order_item_id", "count"),
            product_revenue=("price", "sum"),
            freight_revenue=("freight_value", "sum"),
            total_value=("item_total_value", "sum"),
            avg_item_price=("price", "mean"),
            unique_sellers=("seller_id", "nunique"),
        )
    )
    product["product_category_name_english"] = product["product_category_name_english"].fillna(
        "unknown"
    )
    return product.sort_values("product_revenue", ascending=False)


def build_seller_performance(base: dict[str, pd.DataFrame]) -> pd.DataFrame:
    seller = (
        base["order_items_enriched"]
        .groupby(["seller_id", "seller_city", "seller_state"], as_index=False)
        .agg(
            total_orders=("order_id", "nunique"),
            total_items_sold=("order_item_id", "count"),
            product_revenue=("price", "sum"),
            freight_revenue=("freight_value", "sum"),
            total_value=("item_total_value", "sum"),
            avg_item_price=("price", "mean"),
            unique_products=("product_id", "nunique"),
            unique_customers=("customer_unique_id", "nunique"),
        )
    )
    return seller.sort_values("product_revenue", ascending=False)


def build_delivery_delay_analysis(base: dict[str, pd.DataFrame]) -> pd.DataFrame:
    delivered = base["orders_enriched"][
        base["orders_enriched"]["order_delivered_customer_date"].notna()
    ].copy()
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
    delay["late_order_rate_pct"] = _safe_pct(delay["late_orders"], delay["total_orders"])
    return delay.sort_values(["customer_state", "delay_status"])


def build_payment_behavior(base: dict[str, pd.DataFrame]) -> pd.DataFrame:
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


def build_review_score_analysis(base: dict[str, pd.DataFrame]) -> pd.DataFrame:
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
    score["late_order_rate_pct"] = _safe_pct(score["late_orders"], score["total_orders"])
    return score.sort_values(["review_score", "has_comment"])


def build_regional_sales(base: dict[str, pd.DataFrame]) -> pd.DataFrame:
    regional = (
        base["orders_enriched"]
        .groupby(["customer_state", "customer_city"], as_index=False)
        .agg(
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
    )
    regional["late_order_rate_pct"] = _safe_pct(
        regional["late_orders"], regional["delivered_orders"]
    )
    return regional.sort_values("total_payment_value", ascending=False)


# Builder registry — keyed by Gold table name.
BuilderFn = Callable[[dict[str, pd.DataFrame]], pd.DataFrame]
BUILDERS: dict[str, BuilderFn] = {
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


# ─────────────────────────────────────────────
# Pipeline runner
# ─────────────────────────────────────────────


def run_gold_transformations(environment: str = "local") -> list[dict]:
    setup_logger()
    logger.info("=" * 60)
    logger.info(f"  Gold Transformation Pipeline - Starting ({environment})")
    logger.info("=" * 60)

    config = load_config()
    storage = get_storage(environment, config)
    paths = LayerPaths.from_config(config, environment)
    log_path = config["paths"]["local"]["logs"]
    os.makedirs(log_path, exist_ok=True)

    # Fresh gold log on every run.
    log_file = os.path.join(log_path, "gold_transformation_log.csv")
    if os.path.exists(log_file):
        os.remove(log_file)

    logger.info(f"Backend        : {storage.describe}")

    # Load every Silver source table once.
    tables: dict[str, pd.DataFrame] = {}
    for name in SOURCE_TABLES:
        tables[name] = _read_silver_table(storage, paths.silver, name)
        logger.info(f"[{name}] Loaded {len(tables[name]):,} Silver rows")

    base = build_base_tables(tables)

    # Build each Gold mart.
    results: list[dict] = []
    for name in GOLD_TABLES:
        try:
            gold_df = BUILDERS[name](base)
            _write_gold_table(storage, gold_df, paths.gold, name)
            write_gold_log(log_path, name, len(gold_df), "SUCCESS")
            results.append({"table": name, "rows": len(gold_df), "status": "SUCCESS"})
        except Exception as e:  # noqa: BLE001
            logger.error(f"[{name}] FAILED: {e}")
            write_gold_log(log_path, name, 0, "FAILED", str(e))
            results.append({"table": name, "rows": 0, "status": f"FAILED: {e}"})

    # Summary
    logger.info("=" * 60)
    logger.info("  Gold Transformation Summary")
    logger.info("=" * 60)
    logger.info(f"{'Gold table':<35} {'Rows':>12}  Status")
    logger.info("-" * 70)
    for r in results:
        logger.info(f"{r['table']:<35} {r['rows']:>12,}  {r['status']}")
    logger.info("-" * 70)
    logger.info(f"{'TOTAL':<35} {sum(r['rows'] for r in results):>12,}")
    logger.info(f"Gold log -> {log_file}")

    if isinstance(storage, AdlsStorage):
        remote_log_file = f"{paths.logs.rstrip('/')}/gold_transformation_log.csv"
        storage.upload_local_file(log_file, remote_log_file)
        logger.info(f"Gold log uploaded to ADLS: {remote_log_file}")

    logger.info("=" * 60)
    logger.info("  Gold Transformation Pipeline - Complete")
    logger.info("=" * 60)

    failed = [r for r in results if not r["status"].startswith("SUCCESS")]
    if failed:
        raise RuntimeError(
            "Gold transformation failed for: " + ", ".join(r["table"] for r in failed)
        )
    return results


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Gold transformation pipeline.")
    parser.add_argument(
        "--environment",
        choices=["local", "azure"],
        default="local",
        help="Run against local filesystem or Azure Data Lake Storage Gen2.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_gold_transformations(environment=args.environment)
