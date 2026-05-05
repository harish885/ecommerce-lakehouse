# Data Quality Rules

## Overview

Data quality checks run during the Silver transformation stage. Records that fail any rule
are written to `data/rejected/{table}/` with a `dq_failure_reason` column explaining why.
A summary report is written to `logs/data_quality_report.csv`.

---

## Rules by Table

### customers
| Rule | Column | Check |
|---|---|---|
| DQ-CUST-001 | customer_id | Must not be null |
| DQ-CUST-002 | customer_unique_id | Must not be null |
| DQ-CUST-003 | customer_state | Must be a valid 2-letter Brazilian state code |

### orders
| Rule | Column | Check |
|---|---|---|
| DQ-ORD-001 | order_id | Must not be null |
| DQ-ORD-002 | customer_id | Must not be null |
| DQ-ORD-003 | order_status | Must be one of the known status values |
| DQ-ORD-004 | order_purchase_timestamp | Must not be null |
| DQ-ORD-005 | order_delivered_customer_date | If present, must be >= order_purchase_timestamp |
| DQ-ORD-006 | customer_id | Must exist in customers table (referential integrity) |

### order_items
| Rule | Column | Check |
|---|---|---|
| DQ-ITM-001 | order_id | Must not be null |
| DQ-ITM-002 | product_id | Must not be null |
| DQ-ITM-003 | seller_id | Must not be null |
| DQ-ITM-004 | price | Must be >= 0 |
| DQ-ITM-005 | freight_value | Must be >= 0 |
| DQ-ITM-006 | order_id | Must exist in orders table |
| DQ-ITM-007 | product_id | Must exist in products table |
| DQ-ITM-008 | seller_id | Must exist in sellers table |

### payments
| Rule | Column | Check |
|---|---|---|
| DQ-PAY-001 | order_id | Must not be null |
| DQ-PAY-002 | payment_value | Must be >= 0 |
| DQ-PAY-003 | payment_installments | Must be >= 1 |
| DQ-PAY-004 | payment_type | Must be one of: credit_card, boleto, voucher, debit_card |
| DQ-PAY-005 | order_id | Must exist in orders table |

### reviews
| Rule | Column | Check |
|---|---|---|
| DQ-REV-001 | review_id | Must not be null |
| DQ-REV-002 | order_id | Must not be null |
| DQ-REV-003 | review_score | Must be between 1 and 5 (inclusive) |
| DQ-REV-004 | order_id | Must exist in orders table |

### products
| Rule | Column | Check |
|---|---|---|
| DQ-PRD-001 | product_id | Must not be null |
| DQ-PRD-002 | product_weight_g | If present, must be > 0 |

### sellers
| Rule | Column | Check |
|---|---|---|
| DQ-SEL-001 | seller_id | Must not be null |

---

## Data Quality Report Schema

`logs/data_quality_report.csv`

| Column | Description |
|---|---|
| table_name | Name of the table checked |
| rule_id | Rule identifier (e.g. DQ-ORD-001) |
| rule_description | Human-readable rule description |
| total_records | Total records evaluated |
| passed_records | Records that passed the rule |
| failed_records | Records that failed the rule |
| pass_rate_pct | Percentage that passed |
| status | PASS (>99%) / WARN (95-99%) / FAIL (<95%) |
| execution_timestamp | When the check was run |

---

## Rejected Records

Rejected records are written to `data/rejected/{table}/rejected_{table}.parquet`.
Each rejected record retains all original columns plus:

| Column | Description |
|---|---|
| dq_failure_reason | Human-readable description of which rule failed |
| dq_rule_id | Rule ID that caused rejection |
| rejection_timestamp | When the record was rejected |
