/*
Paste these into the Prelytical UI SQL Validator tab.
Each should be blocked by app guardrails.
*/

DELETE FROM ai.vw_demo_sales_summary;

DROP TABLE dbo.Customers;

SELECT SSN FROM ai.vw_customer_detail;

EXEC xp_cmdshell 'dir';

SELECT * FROM dbo.Customers;

SELECT * FROM OtherDb.ai.vw_sales_summary;

SELECT * FROM ai.vw_demo_sales_summary; SELECT TOP 1 * FROM ai.vw_demo_sales_summary;
