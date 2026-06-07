from __future__ import annotations


def escape_odbc_value(value: str) -> str:
    """Brace-wrap ODBC connection string values that contain reserved characters."""
    if not value:
        return value
    if ";" in value or "}" in value or "{" in value:
        return "{" + value.replace("}", "}}") + "}"
    return value


def normalize_encrypt_for_driver(driver_name: str, encrypt: str) -> str:
    """
    Map Encrypt= values to a form accepted by the installed Microsoft ODBC driver.

    Driver 17 supports optional|yes|no. Driver 18+ also supports mandatory|strict.
    """
    value = encrypt.strip()
    lowered = value.lower()
    if "driver 17" in driver_name.lower() and lowered in {"mandatory", "strict"}:
        return "yes"
    return value
