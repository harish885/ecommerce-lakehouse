// Power Query M queries for Azure Data Lake Storage Gen2 Gold Parquet.
// In Power BI Desktop, create one Blank Query per section below.
// Name each query exactly as the section heading.

// Query name: Daily Sales
let
    StorageAccount = "stecomlakehousehb01",
    FileSystem = "olist-lakehouse",
    GoldPrefix = "gold/olist",
    Source = AzureStorage.DataLake("https://" & StorageAccount & ".dfs.core.windows.net/" & FileSystem),
    File = Table.SelectRows(Source, each [Name] = "daily_sales.parquet" and Text.Contains([Folder Path], GoldPrefix & "/daily_sales/")){0}[Content],
    Result = Parquet.Document(File)
in
    Result

// Query name: Monthly Revenue
let
    StorageAccount = "stecomlakehousehb01",
    FileSystem = "olist-lakehouse",
    GoldPrefix = "gold/olist",
    Source = AzureStorage.DataLake("https://" & StorageAccount & ".dfs.core.windows.net/" & FileSystem),
    File = Table.SelectRows(Source, each [Name] = "monthly_revenue.parquet" and Text.Contains([Folder Path], GoldPrefix & "/monthly_revenue/")){0}[Content],
    Result = Parquet.Document(File)
in
    Result

// Query name: Customer Lifetime Value
let
    StorageAccount = "stecomlakehousehb01",
    FileSystem = "olist-lakehouse",
    GoldPrefix = "gold/olist",
    Source = AzureStorage.DataLake("https://" & StorageAccount & ".dfs.core.windows.net/" & FileSystem),
    File = Table.SelectRows(Source, each [Name] = "customer_lifetime_value.parquet" and Text.Contains([Folder Path], GoldPrefix & "/customer_lifetime_value/")){0}[Content],
    Result = Parquet.Document(File)
in
    Result

// Query name: Product Performance
let
    StorageAccount = "stecomlakehousehb01",
    FileSystem = "olist-lakehouse",
    GoldPrefix = "gold/olist",
    Source = AzureStorage.DataLake("https://" & StorageAccount & ".dfs.core.windows.net/" & FileSystem),
    File = Table.SelectRows(Source, each [Name] = "product_performance.parquet" and Text.Contains([Folder Path], GoldPrefix & "/product_performance/")){0}[Content],
    Result = Parquet.Document(File)
in
    Result

// Query name: Seller Performance
let
    StorageAccount = "stecomlakehousehb01",
    FileSystem = "olist-lakehouse",
    GoldPrefix = "gold/olist",
    Source = AzureStorage.DataLake("https://" & StorageAccount & ".dfs.core.windows.net/" & FileSystem),
    File = Table.SelectRows(Source, each [Name] = "seller_performance.parquet" and Text.Contains([Folder Path], GoldPrefix & "/seller_performance/")){0}[Content],
    Result = Parquet.Document(File)
in
    Result

// Query name: Delivery Delay Analysis
let
    StorageAccount = "stecomlakehousehb01",
    FileSystem = "olist-lakehouse",
    GoldPrefix = "gold/olist",
    Source = AzureStorage.DataLake("https://" & StorageAccount & ".dfs.core.windows.net/" & FileSystem),
    File = Table.SelectRows(Source, each [Name] = "delivery_delay_analysis.parquet" and Text.Contains([Folder Path], GoldPrefix & "/delivery_delay_analysis/")){0}[Content],
    Result = Parquet.Document(File)
in
    Result

// Query name: Payment Behavior
let
    StorageAccount = "stecomlakehousehb01",
    FileSystem = "olist-lakehouse",
    GoldPrefix = "gold/olist",
    Source = AzureStorage.DataLake("https://" & StorageAccount & ".dfs.core.windows.net/" & FileSystem),
    File = Table.SelectRows(Source, each [Name] = "payment_behavior.parquet" and Text.Contains([Folder Path], GoldPrefix & "/payment_behavior/")){0}[Content],
    Result = Parquet.Document(File)
in
    Result

// Query name: Review Score Analysis
let
    StorageAccount = "stecomlakehousehb01",
    FileSystem = "olist-lakehouse",
    GoldPrefix = "gold/olist",
    Source = AzureStorage.DataLake("https://" & StorageAccount & ".dfs.core.windows.net/" & FileSystem),
    File = Table.SelectRows(Source, each [Name] = "review_score_analysis.parquet" and Text.Contains([Folder Path], GoldPrefix & "/review_score_analysis/")){0}[Content],
    Result = Parquet.Document(File)
in
    Result

// Query name: Regional Sales
let
    StorageAccount = "stecomlakehousehb01",
    FileSystem = "olist-lakehouse",
    GoldPrefix = "gold/olist",
    Source = AzureStorage.DataLake("https://" & StorageAccount & ".dfs.core.windows.net/" & FileSystem),
    File = Table.SelectRows(Source, each [Name] = "regional_sales.parquet" and Text.Contains([Folder Path], GoldPrefix & "/regional_sales/")){0}[Content],
    Result = Parquet.Document(File)
in
    Result
