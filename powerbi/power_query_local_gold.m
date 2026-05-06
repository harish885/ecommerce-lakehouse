// Local fallback Power Query M queries for Gold Parquet.
// Replace ProjectRoot with the local path to this repository on the Windows machine.
// Example:
// ProjectRoot = "C:\Users\harish\ecommerce-lakehouse"

// Query name: Daily Sales
let
    ProjectRoot = "C:\path\to\ecommerce-lakehouse",
    Result = Parquet.Document(File.Contents(ProjectRoot & "\data\gold\daily_sales\daily_sales.parquet"))
in
    Result

// Query name: Monthly Revenue
let
    ProjectRoot = "C:\path\to\ecommerce-lakehouse",
    Result = Parquet.Document(File.Contents(ProjectRoot & "\data\gold\monthly_revenue\monthly_revenue.parquet"))
in
    Result

// Query name: Customer Lifetime Value
let
    ProjectRoot = "C:\path\to\ecommerce-lakehouse",
    Result = Parquet.Document(File.Contents(ProjectRoot & "\data\gold\customer_lifetime_value\customer_lifetime_value.parquet"))
in
    Result

// Query name: Product Performance
let
    ProjectRoot = "C:\path\to\ecommerce-lakehouse",
    Result = Parquet.Document(File.Contents(ProjectRoot & "\data\gold\product_performance\product_performance.parquet"))
in
    Result

// Query name: Seller Performance
let
    ProjectRoot = "C:\path\to\ecommerce-lakehouse",
    Result = Parquet.Document(File.Contents(ProjectRoot & "\data\gold\seller_performance\seller_performance.parquet"))
in
    Result

// Query name: Delivery Delay Analysis
let
    ProjectRoot = "C:\path\to\ecommerce-lakehouse",
    Result = Parquet.Document(File.Contents(ProjectRoot & "\data\gold\delivery_delay_analysis\delivery_delay_analysis.parquet"))
in
    Result

// Query name: Payment Behavior
let
    ProjectRoot = "C:\path\to\ecommerce-lakehouse",
    Result = Parquet.Document(File.Contents(ProjectRoot & "\data\gold\payment_behavior\payment_behavior.parquet"))
in
    Result

// Query name: Review Score Analysis
let
    ProjectRoot = "C:\path\to\ecommerce-lakehouse",
    Result = Parquet.Document(File.Contents(ProjectRoot & "\data\gold\review_score_analysis\review_score_analysis.parquet"))
in
    Result

// Query name: Regional Sales
let
    ProjectRoot = "C:\path\to\ecommerce-lakehouse",
    Result = Parquet.Document(File.Contents(ProjectRoot & "\data\gold\regional_sales\regional_sales.parquet"))
in
    Result
