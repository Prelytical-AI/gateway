/*
Optional: grant read-only access to all dbo tables/views.

Run this instead of (or in addition to) ai-only grants when the VM is the
security boundary and you want the model to query real tables directly.

Requires 01_create_readonly_login.sql to have been run first.
Edit the database name below if needed.
*/

USE [PrelyticalDemoDW];
GO

GRANT SELECT ON SCHEMA::[dbo] TO [prelytical_readonly];
GO

PRINT 'dbo SELECT granted to prelytical_readonly.';
GO
