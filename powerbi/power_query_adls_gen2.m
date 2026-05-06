// =============================================================================
// Power Query M — Azure Data Lake Storage Gen2 Gold Parquet
// =============================================================================
//
// Build steps in Power BI Desktop:
//   1. Get data → Blank query, paste the "fnLoadGoldTable" function below.
//   2. Create one Blank query per Gold mart (sections further down) and name
//      each query exactly as the comment heading. They all delegate to
//      fnLoadGoldTable so the storage account is configured in ONE place.
//   3. Load all queries to the model.
//
// Permissions:
//   The signed-in Power BI Desktop / Service identity needs at least
//   `Storage Blob Data Reader` on the storage account.
// =============================================================================


// -----------------------------------------------------------------------------
// Query name: fnLoadGoldTable
// Reusable function — pass the Gold mart name (folder + file stem) and get back
// the Parquet table from ADLS Gen2.
// -----------------------------------------------------------------------------
let
    fnLoadGoldTable = (tableName as text) as table =>
        let
            StorageAccount = "stecomlakehousehb01",
            FileSystem     = "olist-lakehouse",
            GoldPrefix     = "gold/olist",
            FolderPath     = GoldPrefix & "/" & tableName & "/",
            FileName       = tableName & ".parquet",
            Source         = AzureStorage.DataLake(
                                "https://" & StorageAccount & ".dfs.core.windows.net/" & FileSystem
                             ),
            File           = Table.SelectRows(
                                Source,
                                each [Name] = FileName and Text.Contains([Folder Path], FolderPath)
                             ){0}[Content],
            Result         = Parquet.Document(File)
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
