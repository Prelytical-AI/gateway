/*
Edit these before running:
Database: PrelyticalDemoDW
Login: prelytical_readonly
Password: CHANGE_ME_STRONG_PASSWORD
*/

USE [master];
GO

IF NOT EXISTS (SELECT * FROM sys.sql_logins WHERE name = 'prelytical_readonly')
BEGIN
    CREATE LOGIN [prelytical_readonly] WITH PASSWORD = 'CHANGE_ME_STRONG_PASSWORD';
END
GO

USE [PrelyticalDemoDW];
GO

IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'prelytical_readonly')
BEGIN
    CREATE USER [prelytical_readonly] FOR LOGIN [prelytical_readonly];
END
GO

GRANT SELECT ON SCHEMA::[ai] TO [prelytical_readonly];
GO

-- Optional: full read access to dbo (typical on a trusted VM).
-- Or run sql/02_grant_dbo_readonly.sql separately.
-- GRANT SELECT ON SCHEMA::[dbo] TO [prelytical_readonly];
-- GO

DENY INSERT, UPDATE, DELETE, ALTER, CONTROL TO [prelytical_readonly];
GO
