/*
Seed warehouse for the Prelytical gateway AWS test VM.
Creates PrelyticalDemoDW with realistic-ish sales data for analysis questions.
*/

IF DB_ID(N'PrelyticalDemoDW') IS NULL
BEGIN
    CREATE DATABASE [PrelyticalDemoDW];
END
GO

USE [PrelyticalDemoDW];
GO

IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = N'ai')
BEGIN
    EXEC('CREATE SCHEMA ai');
END
GO

IF OBJECT_ID(N'dbo.Regions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Regions (
        region_id INT NOT NULL PRIMARY KEY,
        region_name NVARCHAR(50) NOT NULL,
        country NVARCHAR(50) NOT NULL
    );

    INSERT INTO dbo.Regions (region_id, region_name, country)
    VALUES
        (1, N'Midwest', N'USA'),
        (2, N'West', N'USA'),
        (3, N'East', N'USA'),
        (4, N'South', N'USA');
END
GO

IF OBJECT_ID(N'dbo.ProductCategories', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ProductCategories (
        category_id INT NOT NULL PRIMARY KEY,
        category_name NVARCHAR(100) NOT NULL
    );

    INSERT INTO dbo.ProductCategories (category_id, category_name)
    VALUES
        (1, N'Analytics Platform'),
        (2, N'Data Integration'),
        (3, N'Reporting'),
        (4, N'Support Services');
END
GO

IF OBJECT_ID(N'dbo.Customers', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Customers (
        customer_id INT NOT NULL PRIMARY KEY,
        customer_name NVARCHAR(120) NOT NULL,
        region_id INT NOT NULL REFERENCES dbo.Regions(region_id),
        segment NVARCHAR(50) NOT NULL,
        annual_contract_value DECIMAL(18, 2) NOT NULL,
        active_since DATE NOT NULL
    );

    INSERT INTO dbo.Customers (customer_id, customer_name, region_id, segment, annual_contract_value, active_since)
    VALUES
        (1, N'Acme Bank', 1, N'Enterprise', 420000.00, '2021-03-01'),
        (2, N'Northwind Health', 3, N'Enterprise', 385000.00, '2020-08-15'),
        (3, N'Summit Retail Group', 2, N'Mid-Market', 156000.00, '2022-01-10'),
        (4, N'Harbor Logistics', 4, N'Mid-Market', 98000.00, '2022-06-01'),
        (5, N'BlueSky Manufacturing', 1, N'Enterprise', 275000.00, '2019-11-20'),
        (6, N'Coastal Credit Union', 4, N'Mid-Market', 132000.00, '2023-02-14'),
        (7, N'Pioneer Insurance', 2, N'Enterprise', 510000.00, '2018-05-05'),
        (8, N'Urban Media Co', 3, N'SMB', 64000.00, '2024-01-08');
END
GO

IF OBJECT_ID(N'dbo.Orders', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Orders (
        order_id INT NOT NULL PRIMARY KEY,
        customer_id INT NOT NULL REFERENCES dbo.Customers(customer_id),
        order_date DATE NOT NULL,
        category_id INT NOT NULL REFERENCES dbo.ProductCategories(category_id),
        revenue DECIMAL(18, 2) NOT NULL,
        units INT NOT NULL,
        status NVARCHAR(30) NOT NULL
    );

    INSERT INTO dbo.Orders (order_id, customer_id, order_date, category_id, revenue, units, status)
    VALUES
        (1001, 1, '2025-01-15', 1, 125000.00, 12, N'Closed'),
        (1002, 3, '2025-01-22', 2, 98000.00, 20, N'Closed'),
        (1003, 2, '2025-02-03', 1, 142500.00, 15, N'Closed'),
        (1004, 4, '2025-02-18', 3, 76500.00, 30, N'Closed'),
        (1005, 5, '2025-03-05', 3, 110250.00, 25, N'Closed'),
        (1006, 7, '2025-03-12', 1, 156000.00, 18, N'Closed'),
        (1007, 2, '2025-04-01', 2, 88000.00, 22, N'Closed'),
        (1008, 6, '2025-04-19', 1, 133000.00, 14, N'Closed'),
        (1009, 1, '2025-05-07', 2, 99000.00, 19, N'Closed'),
        (1010, 3, '2025-05-21', 3, 84500.00, 28, N'Closed'),
        (1011, 7, '2025-05-28', 4, 62000.00, 10, N'Closed'),
        (1012, 5, '2025-06-02', 1, 171000.00, 16, N'Closed'),
        (1013, 8, '2025-06-10', 3, 42000.00, 8, N'Closed'),
        (1014, 4, '2025-06-18', 2, 73500.00, 17, N'Open'),
        (1015, 6, '2025-06-22', 4, 28000.00, 6, N'Open');
END
GO

CREATE OR ALTER VIEW ai.vw_sales_by_region AS
SELECT
    r.region_name,
    r.country,
    COUNT(DISTINCT c.customer_id) AS customer_count,
    SUM(o.revenue) AS total_revenue,
    SUM(o.units) AS total_units,
    AVG(o.revenue) AS avg_order_revenue
FROM dbo.Orders AS o
INNER JOIN dbo.Customers AS c ON c.customer_id = o.customer_id
INNER JOIN dbo.Regions AS r ON r.region_id = c.region_id
GROUP BY r.region_name, r.country;
GO

CREATE OR ALTER VIEW ai.vw_sales_by_category AS
SELECT
    pc.category_name,
    COUNT(*) AS order_count,
    SUM(o.revenue) AS total_revenue,
    SUM(o.units) AS total_units
FROM dbo.Orders AS o
INNER JOIN dbo.ProductCategories AS pc ON pc.category_id = o.category_id
GROUP BY pc.category_name;
GO

CREATE OR ALTER VIEW ai.vw_monthly_revenue AS
SELECT
    CAST(DATEFROMPARTS(YEAR(o.order_date), MONTH(o.order_date), 1) AS DATE) AS month_start,
    r.region_name,
    pc.category_name,
    SUM(o.revenue) AS revenue,
    SUM(o.units) AS units_sold,
    COUNT(*) AS order_count
FROM dbo.Orders AS o
INNER JOIN dbo.Customers AS c ON c.customer_id = o.customer_id
INNER JOIN dbo.Regions AS r ON r.region_id = c.region_id
INNER JOIN dbo.ProductCategories AS pc ON pc.category_id = o.category_id
GROUP BY
    CAST(DATEFROMPARTS(YEAR(o.order_date), MONTH(o.order_date), 1) AS DATE),
    r.region_name,
    pc.category_name;
GO

PRINT 'PrelyticalDemoDW seed complete.';
GO
