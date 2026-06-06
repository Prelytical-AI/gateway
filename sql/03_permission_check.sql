USE [PrelyticalDemoDW];
GO

PRINT 'Running permission checks as prelytical_readonly...';
GO

EXECUTE AS USER = 'prelytical_readonly';
GO

SELECT TOP 5
    month_start,
    region,
    product_category,
    revenue,
    units_sold,
    sale_count
FROM ai.vw_demo_sales_summary
ORDER BY revenue DESC;
GO

REVERT;
GO

/*
Expected blocked tests (run separately as prelytical_readonly):

SELECT TOP 5 * FROM dbo.PrelyticalDemoSales;
-- Should fail: permission denied on dbo

INSERT INTO ai.vw_demo_sales_summary (region) VALUES ('Test');
-- Should fail: denied INSERT
*/

PRINT 'Permission check complete.';
GO
