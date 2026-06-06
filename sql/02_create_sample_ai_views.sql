/*
Replace the demo section below with client-specific AI-safe views.
Do not expose raw PII or sensitive fields.
Prefer aggregated views over row-level customer detail.
*/

USE [PrelyticalDemoDW];
GO

-- ============================================================================
-- DEMO ONLY: create sample data when no client tables exist yet
-- ============================================================================

IF OBJECT_ID(N'dbo.PrelyticalDemoSales', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.PrelyticalDemoSales (
        sale_id INT NOT NULL PRIMARY KEY,
        sale_date DATE NOT NULL,
        region NVARCHAR(50) NOT NULL,
        product_category NVARCHAR(100) NOT NULL,
        revenue DECIMAL(18, 2) NOT NULL,
        units_sold INT NOT NULL
    );

    INSERT INTO dbo.PrelyticalDemoSales (sale_id, sale_date, region, product_category, revenue, units_sold)
    VALUES
        (1, '2025-01-15', 'Midwest', 'Analytics Platform', 125000.00, 12),
        (2, '2025-01-22', 'West', 'Data Integration', 98000.00, 20),
        (3, '2025-02-03', 'East', 'Analytics Platform', 142500.00, 15),
        (4, '2025-02-18', 'South', 'Reporting', 76500.00, 30),
        (5, '2025-03-05', 'Midwest', 'Reporting', 110250.00, 25),
        (6, '2025-03-12', 'West', 'Analytics Platform', 156000.00, 18),
        (7, '2025-04-01', 'East', 'Data Integration', 88000.00, 22),
        (8, '2025-04-19', 'South', 'Analytics Platform', 133000.00, 14),
        (9, '2025-05-07', 'Midwest', 'Data Integration', 99000.00, 19),
        (10, '2025-05-21', 'West', 'Reporting', 84500.00, 28);
END
GO

CREATE OR ALTER VIEW ai.vw_demo_sales_summary AS
SELECT
    CAST(DATEFROMPARTS(YEAR(s.sale_date), MONTH(s.sale_date), 1) AS DATE) AS month_start,
    s.region,
    s.product_category,
    SUM(s.revenue) AS revenue,
    SUM(s.units_sold) AS units_sold,
    COUNT(*) AS sale_count
FROM dbo.PrelyticalDemoSales AS s
GROUP BY
    CAST(DATEFROMPARTS(YEAR(s.sale_date), MONTH(s.sale_date), 1) AS DATE),
    s.region,
    s.product_category;
GO

-- Example client-safe view template (replace with real logic):
-- CREATE OR ALTER VIEW ai.vw_example_monthly_summary AS
-- SELECT
--     month_start,
--     region,
--     SUM(revenue) AS revenue
-- FROM dbo.YourSafeSourceTable
-- GROUP BY month_start, region;
-- GO
