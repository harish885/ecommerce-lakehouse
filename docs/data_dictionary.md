# Data Dictionary

## Source: Brazilian Olist E-Commerce Dataset

---

### customers

| Column | Type | Description | Nullable |
|---|---|---|---|
| customer_id | string | Unique customer identifier per order (hashed) | No |
| customer_unique_id | string | Permanent customer ID across all orders | No |
| customer_zip_code_prefix | string | 5-digit ZIP code prefix | Yes |
| customer_city | string | City name | Yes |
| customer_state | string | 2-letter Brazilian state code | Yes |

---

### orders

| Column | Type | Description | Nullable |
|---|---|---|---|
| order_id | string | Unique order identifier | No |
| customer_id | string | FK → customers.customer_id | No |
| order_status | string | delivered / shipped / canceled / unavailable / processing / invoiced / approved / created | No |
| order_purchase_timestamp | timestamp | When the order was placed | No |
| order_approved_at | timestamp | When payment was approved | Yes |
| order_delivered_carrier_date | timestamp | When handed to carrier | Yes |
| order_delivered_customer_date | timestamp | When delivered to customer | Yes |
| order_estimated_delivery_date | timestamp | Original estimated delivery date | No |

---

### order_items

| Column | Type | Description | Nullable |
|---|---|---|---|
| order_id | string | FK → orders.order_id | No |
| order_item_id | integer | Item sequence number within order (1-based) | No |
| product_id | string | FK → products.product_id | No |
| seller_id | string | FK → sellers.seller_id | No |
| shipping_limit_date | timestamp | Seller must ship by this date | No |
| price | float | Item price in BRL | No |
| freight_value | float | Freight cost in BRL | No |

---

### products

| Column | Type | Description | Nullable |
|---|---|---|---|
| product_id | string | Unique product identifier | No |
| product_category_name | string | Product category in Portuguese | Yes |
| product_name_lenght | integer | Character length of product name | Yes |
| product_description_lenght | integer | Character length of description | Yes |
| product_photos_qty | integer | Number of photos | Yes |
| product_weight_g | float | Weight in grams | Yes |
| product_length_cm | float | Length in cm | Yes |
| product_height_cm | float | Height in cm | Yes |
| product_width_cm | float | Width in cm | Yes |

---

### sellers

| Column | Type | Description | Nullable |
|---|---|---|---|
| seller_id | string | Unique seller identifier | No |
| seller_zip_code_prefix | string | 5-digit ZIP prefix | Yes |
| seller_city | string | City name | Yes |
| seller_state | string | 2-letter Brazilian state code | Yes |

---

### payments

| Column | Type | Description | Nullable |
|---|---|---|---|
| order_id | string | FK → orders.order_id | No |
| payment_sequential | integer | Payment sequence (for installments) | No |
| payment_type | string | credit_card / boleto / voucher / debit_card | No |
| payment_installments | integer | Number of installments chosen | No |
| payment_value | float | Payment amount in BRL | No |

---

### reviews

| Column | Type | Description | Nullable |
|---|---|---|---|
| review_id | string | Unique review identifier | No |
| order_id | string | FK → orders.order_id | No |
| review_score | integer | Score from 1 (worst) to 5 (best) | No |
| review_comment_title | string | Optional short review title | Yes |
| review_comment_message | string | Optional full review text | Yes |
| review_creation_date | timestamp | When review request was sent | Yes |
| review_answer_timestamp | timestamp | When customer submitted review | Yes |

---

### geolocation

| Column | Type | Description | Nullable |
|---|---|---|---|
| geolocation_zip_code_prefix | string | 5-digit ZIP prefix | No |
| geolocation_lat | float | Latitude | No |
| geolocation_lng | float | Longitude | No |
| geolocation_city | string | City name | Yes |
| geolocation_state | string | 2-letter state code | Yes |

---

### product_category_translation

| Column | Type | Description | Nullable |
|---|---|---|---|
| product_category_name | string | Category name in Portuguese | No |
| product_category_name_english | string | Category name in English | No |

---

## Bronze Metadata Columns (added to all tables)

| Column | Type | Description |
|---|---|---|
| ingestion_timestamp | timestamp | Exact time the record was ingested |
| source_file_name | string | Original CSV file name |
| batch_id | string | Unique batch run identifier |
| ingestion_date | date | Date partition value |
