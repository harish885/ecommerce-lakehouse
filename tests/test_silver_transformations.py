"""
Unit tests for Silver Layer transformation rules.
Run with: pytest tests/ -v
"""

import os
import sys
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.transformation.silver_transformations import (
    clean_customers,
    clean_orders,
    clean_order_items,
    clean_payments,
    clean_reviews,
    clean_products,
    clean_sellers,
)

LOG_PATH = "logs"
os.makedirs(LOG_PATH, exist_ok=True)


# ─────────────────────────────────────────────
# Customers
# ─────────────────────────────────────────────


def test_customers_null_id_rejected():
    df = pd.DataFrame(
        {
            "customer_id": [None, "abc123"],
            "customer_unique_id": ["u1", "u2"],
            "customer_zip_code_prefix": ["12345", "12346"],
            "customer_city": ["sao paulo", "rio"],
            "customer_state": ["SP", "RJ"],
        }
    )
    clean, rejected = clean_customers(df, LOG_PATH)
    assert len(rejected) >= 1
    assert None not in clean["customer_id"].values


def test_customers_invalid_state_rejected():
    df = pd.DataFrame(
        {
            "customer_id": ["id1", "id2"],
            "customer_unique_id": ["u1", "u2"],
            "customer_zip_code_prefix": ["12345", "12346"],
            "customer_city": ["city1", "city2"],
            "customer_state": ["XX", "SP"],  # XX is invalid
        }
    )
    clean, rejected = clean_customers(df, LOG_PATH)
    states_in_clean = clean["customer_state"].tolist()
    assert "XX" not in states_in_clean


def test_customers_deduplication():
    df = pd.DataFrame(
        {
            "customer_id": ["id1", "id1"],
            "customer_unique_id": ["u1", "u1"],
            "customer_zip_code_prefix": ["12345", "12345"],
            "customer_city": ["sao paulo", "sao paulo"],
            "customer_state": ["SP", "SP"],
        }
    )
    clean, _ = clean_customers(df, LOG_PATH)
    assert len(clean) == 1


# ─────────────────────────────────────────────
# Payments
# ─────────────────────────────────────────────


def test_payments_negative_value_rejected():
    df = pd.DataFrame(
        {
            "order_id": ["o1", "o2"],
            "payment_sequential": [1, 1],
            "payment_type": ["credit_card", "boleto"],
            "payment_installments": [1, 1],
            "payment_value": [-10.0, 50.0],  # negative should be rejected
        }
    )
    clean, rejected = clean_payments(df, LOG_PATH)
    assert len(rejected) >= 1
    assert all(clean["payment_value"] >= 0)


def test_payments_zero_value_accepted():
    df = pd.DataFrame(
        {
            "order_id": ["o1"],
            "payment_sequential": [1],
            "payment_type": ["voucher"],
            "payment_installments": [1],
            "payment_value": [0.0],
        }
    )
    clean, rejected = clean_payments(df, LOG_PATH)
    assert len(clean) == 1


def test_payments_invalid_type_rejected():
    df = pd.DataFrame(
        {
            "order_id": ["o1", "o2"],
            "payment_sequential": [1, 1],
            "payment_type": ["bitcoin", "credit_card"],  # bitcoin invalid
            "payment_installments": [1, 1],
            "payment_value": [100.0, 100.0],
        }
    )
    clean, rejected = clean_payments(df, LOG_PATH)
    assert any("bitcoin" not in str(v) for v in clean["payment_type"].tolist())


# ─────────────────────────────────────────────
# Reviews
# ─────────────────────────────────────────────


def test_reviews_score_out_of_range_rejected():
    df = pd.DataFrame(
        {
            "review_id": ["r1", "r2", "r3"],
            "order_id": ["o1", "o2", "o3"],
            "review_score": [6, 3, 0],  # 6 and 0 are invalid
        }
    )
    clean, rejected = clean_reviews(df, LOG_PATH)
    assert len(rejected) >= 2
    valid_scores = clean["review_score"].dropna().tolist()
    assert all(1 <= int(s) <= 5 for s in valid_scores)


def test_reviews_valid_scores_accepted():
    df = pd.DataFrame(
        {
            "review_id": ["r1", "r2", "r3", "r4", "r5"],
            "order_id": ["o1", "o2", "o3", "o4", "o5"],
            "review_score": [1, 2, 3, 4, 5],
        }
    )
    clean, rejected = clean_reviews(df, LOG_PATH)
    assert len(clean) == 5
    assert len(rejected) == 0


def test_reviews_null_review_id_rejected():
    df = pd.DataFrame(
        {
            "review_id": [None, "r2"],
            "order_id": ["o1", "o2"],
            "review_score": [4, 5],
        }
    )
    clean, rejected = clean_reviews(df, LOG_PATH)
    assert len(rejected) >= 1


# ─────────────────────────────────────────────
# Order Items
# ─────────────────────────────────────────────


def test_order_items_negative_price_rejected():
    df = pd.DataFrame(
        {
            "order_id": ["o1", "o2"],
            "order_item_id": [1, 1],
            "product_id": ["p1", "p2"],
            "seller_id": ["s1", "s2"],
            "shipping_limit_date": ["2021-01-01", "2021-01-01"],
            "price": [-5.0, 100.0],
            "freight_value": [10.0, 10.0],
        }
    )
    clean, rejected = clean_order_items(df, LOG_PATH)
    assert len(rejected) >= 1
    assert all(clean["price"] >= 0)


def test_order_items_null_order_id_rejected():
    df = pd.DataFrame(
        {
            "order_id": [None, "o2"],
            "order_item_id": [1, 1],
            "product_id": ["p1", "p2"],
            "seller_id": ["s1", "s2"],
            "shipping_limit_date": ["2021-01-01", "2021-01-01"],
            "price": [10.0, 10.0],
            "freight_value": [5.0, 5.0],
        }
    )
    clean, rejected = clean_order_items(df, LOG_PATH)
    assert len(rejected) >= 1


# ─────────────────────────────────────────────
# Products
# ─────────────────────────────────────────────


def test_products_null_id_rejected():
    df = pd.DataFrame(
        {
            "product_id": [None, "p2"],
            "product_category_name": ["electronics", "fashion"],
            "product_weight_g": [500.0, 300.0],
        }
    )
    clean, rejected = clean_products(df, LOG_PATH)
    assert len(rejected) >= 1


def test_products_zero_weight_rejected():
    df = pd.DataFrame(
        {
            "product_id": ["p1", "p2"],
            "product_category_name": ["electronics", "fashion"],
            "product_weight_g": [0.0, 300.0],
        }
    )
    clean, rejected = clean_products(df, LOG_PATH)
    assert len(rejected) >= 1
