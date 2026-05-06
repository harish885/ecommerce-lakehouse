# Power BI Report Blueprint

Report title: Azure E-Commerce Lakehouse

Dataset: Brazilian Olist E-Commerce

Primary source: ADLS Gen2 Gold Parquet marts

## Model Setup

Load all nine Gold tables:

| Power BI Table Name | Source Gold Table |
|---------------------|-------------------|
| Daily Sales | `daily_sales` |
| Monthly Revenue | `monthly_revenue` |
| Customer Lifetime Value | `customer_lifetime_value` |
| Product Performance | `product_performance` |
| Seller Performance | `seller_performance` |
| Delivery Delay Analysis | `delivery_delay_analysis` |
| Payment Behavior | `payment_behavior` |
| Review Score Analysis | `review_score_analysis` |
| Regional Sales | `regional_sales` |

Create a separate measure table named `Measures`, then add all measures from `measures.dax`.

Suggested relationships are intentionally light because the Gold tables are already business marts. For filtering, use page-level slicers from the table powering each page rather than forcing unrelated aggregated tables into a brittle star schema.

## Theme

Import `theme.json`.

Design language:

- Executive, Azure-native, clean, and recruiter-friendly
- White canvas with navy section headers
- Blue for revenue, green for positive health, amber for risk, red for late delivery
- Keep pages dense but readable; this is a data engineering portfolio report, not a marketing page

## Page 1: Executive Overview

Goal: Show the whole business in 30 seconds.

Visuals:

| Visual | Fields / Measures | Notes |
|--------|-------------------|-------|
| Card | `Total Revenue` | Format as BRL currency |
| Card | `Total Orders` | Whole number |
| Card | `Unique Customers` | Whole number |
| Card | `Average Order Value` | BRL currency |
| Card | `Repeat Customer Rate` | Percentage |
| Line chart | Axis: `Daily Sales[order_purchase_date]`; Values: `Total Revenue` | Daily revenue trend |
| Bar chart | Axis: `Monthly Revenue[order_purchase_month]`; Values: `SUM(total_payment_value)` | Month-over-month revenue |
| Map or filled map | Location: `Regional Sales[customer_state]`; Size/color: `SUM(total_payment_value)` | Brazil revenue concentration |
| Table | `customer_state`, `total_orders`, `total_payment_value`, `avg_review_score`, `late_order_rate_pct` | Top states |

Slicers:

- Date range from `Daily Sales[order_purchase_date]`
- State from `Regional Sales[customer_state]`

## Page 2: Revenue Trends

Goal: Explain revenue movement and seasonality.

Visuals:

| Visual | Fields / Measures | Notes |
|--------|-------------------|-------|
| Line chart | Date: `Daily Sales[order_purchase_date]`; Value: `Total Revenue` | Main trend |
| Combo chart | Axis: `Monthly Revenue[order_purchase_month]`; Columns: `total_orders`; Line: `avg_order_value` | Volume vs AOV |
| Area chart | Axis: `Monthly Revenue[order_purchase_month]`; Value: `unique_customers` | Customer activity |
| Matrix | Rows: `order_purchase_month`; Values: revenue, orders, AOV, review score | Monthly executive table |

Insights to call out:

- Identify strongest month
- Compare revenue growth to customer growth
- Explain AOV changes

## Page 3: Customer Lifetime Value

Goal: Show customer value distribution and repeat behavior.

Visuals:

| Visual | Fields / Measures | Notes |
|--------|-------------------|-------|
| Card | `Top Customer CLV` | Highest single-customer value |
| Card | `Median Customer CLV` | More realistic customer value |
| Card | `Repeat Customer Rate` | Core retention metric |
| Histogram | `Customer Lifetime Value[total_payment_value]` | CLV spread |
| Bar chart | Axis: `customer_state`; Value: `SUM(total_payment_value)` | Value by state |
| Table | `customer_unique_id`, city, state, orders, total payment, AOV, review score | Top customers |

Slicers:

- `customer_state`
- `repeat_customer_flag`

## Page 4: Product and Seller Performance

Goal: Identify what sells and who drives marketplace revenue.

Visuals:

| Visual | Fields / Measures | Notes |
|--------|-------------------|-------|
| Treemap | Group: `product_category_name_english`; Value: `SUM(product_revenue)` | Category share |
| Bar chart | Category: `product_category_name_english`; Value: `SUM(total_items_sold)` | Units sold |
| Bar chart | Seller: `seller_id`; Value: `SUM(product_revenue)` | Seller leaderboard |
| Scatter chart | X: `total_orders`; Y: `product_revenue`; Size: `unique_customers`; Legend: seller state | Seller productivity |
| Table | seller id, city, state, revenue, freight, products, customers | Seller detail |

Slicers:

- Product category
- Seller state

## Page 5: Delivery and Customer Experience

Goal: Connect delivery quality to customer satisfaction.

Visuals:

| Visual | Fields / Measures | Notes |
|--------|-------------------|-------|
| Card | `Late Delivery Rate` | Operational risk |
| Card | `Average Delivery Days` | Delivery speed |
| Card | `Average Review Score` | Customer sentiment |
| Stacked bar | Axis: `customer_state`; Legend: `delay_status`; Value: `total_orders` | Delay buckets |
| Bar chart | Axis: `review_score`; Value: `review_count`; Legend: `has_comment` | Review distribution |
| Scatter chart | X: `avg_delay_days`; Y: `avg_review_score`; Size: `total_orders`; Legend: state | Delay vs satisfaction |

Slicers:

- Delay status
- Review score

## Page 6: Payment and Regional Sales

Goal: Show payment behavior and geographic sales opportunities.

Visuals:

| Visual | Fields / Measures | Notes |
|--------|-------------------|-------|
| Donut chart | Legend: `payment_type`; Value: `total_payment_value` | Payment mix |
| Stacked bar | Axis: `installment_bucket`; Legend: `payment_type`; Value: `total_orders` | Installment behavior |
| Filled map | Location: `customer_state`; Color: `total_payment_value` | Regional demand |
| Bar chart | Axis: `customer_city`; Value: `total_payment_value` | Top cities |
| Matrix | State, city, orders, customers, revenue, AOV, late rate | Drilldown table |

Slicers:

- Payment type
- Installment bucket
- State

## Publishing Checklist

- Rename all pages clearly.
- Hide technical columns that are not needed by report consumers.
- Format all currency measures as Brazilian Real.
- Format all rates as percentages with one decimal.
- Add the GitHub repository URL as a small text box on the overview page.
- Publish to a Power BI workspace.
- Configure dataset credentials for ADLS Gen2.
- Schedule refresh after the Azure Medallion Pipeline normally runs.
- Export screenshots for README and LinkedIn.
