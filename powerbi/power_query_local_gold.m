// =============================================================================
// Power Query M — Local Gold Parquet (offline fallback)
// =============================================================================
//
// Use these queries when you want to develop the report against a local copy
// of the Gold marts (i.e. without an ADLS connection).
//
// Build steps in Power BI Desktop:
//   1. Get data → Blank query, paste the "ProjectRoot" parameter below
//      and update the value to the absolute path of the repository on
//      your Windows machine.
//   2. Create one Blank query per Gold mart and name it exactly as the
//      comment heading. They all delegate to fnLoadGoldTable so the
//      project root is configured in ONE place.
// =============================================================================


// -----------------------------------------------------------------------------
// Query name: ProjectRoot
// Update this to the absolute path to your local clone of the repo.
// Example: "C:\Users\harish\dev\ecommerce-lakehouse"
// -----------------------------------------------------------------------------
"C:\path\to\ecommerce-lakehouse"


// -----------------------------------------------------------------------------
// Query name: fnLoadGoldTable
// Reusable function — pass the Gold mart name and get back the Parquet table.
// -----------------------------------------------------------------------------
let
    fnLoadGoldTable = (tableName as text) as table =>
        let
            FilePath = ProjectRoot
                       & "\data\gold\" & tableName
                       & "\" & tableName & ".parquet",
            Result   = Parquet.Document(File.Contents(FilePath))
        in
            Result
in
    fnLoadGoldTable


// -----------------------------------------------------------------------------
// Query name: Daily Sales
// -----------------------------------------------------------------------------
let
    Result = fnLoadGoldTable("daily_sales")
in
    Result


// -----------------------------------------------------------------------------
// Query name: Monthly Revenue
// -----------------------------------------------------------------------------
let
    Result = fnLoadGoldTable("monthly_revenue")
in
    Result


// -----------------------------------------------------------------------------
// Query name: Customer Lifetime Value
// -----------------------------------------------------------------------------
let
    Result = fnLoadGoldTable("customer_lifetime_value")
in
    Result


// -----------------------------------------------------------------------------
// Query name: Product Performance
// -----------------------------------------------------------------------------
let
    Result = fnLoadGoldTable("product_performance")
in
    Result


// -----------------------------------------------------------------------------
// Query name: Seller Performance
// -----------------------------------------------------------------------------
let
    Result = fnLoadGoldTable("seller_performance")
in
    Result


// -----------------------------------------------------------------------------
// Query name: Delivery Delay Analysis
// -----------------------------------------------------------------------------
let
    Result = fnLoadGoldTable("delivery_delay_analysis")
in
    Result


// -----------------------------------------------------------------------------
// Query name: Payment Behavior
// -----------------------------------------------------------------------------
let
    Result = fnLoadGoldTable("payment_behavior")
in
    Result


// -----------------------------------------------------------------------------
// Query name: Review Score Analysis
// -----------------------------------------------------------------------------
let
    Result = fnLoadGoldTable("review_score_analysis")
in
    Result


// -----------------------------------------------------------------------------
// Query name: Regional Sales
// -----------------------------------------------------------------------------
let
    Result = fnLoadGoldTable("regional_sales")
in
    Result
