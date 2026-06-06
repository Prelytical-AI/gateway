from app.services.sqlserver import SQLServerService

service = SQLServerService()
ok, message = service.test_connection()
print(f"ok={ok}")
print(message)
if not ok:
    raise SystemExit(1)
