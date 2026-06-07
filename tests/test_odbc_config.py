from app.core.config import Settings
from app.core.odbc_utils import escape_odbc_value, normalize_encrypt_for_driver


def test_escape_odbc_value_wraps_semicolons():
    assert escape_odbc_value("pass;word") == "{pass;word}"


def test_escape_odbc_value_doubles_closing_braces():
    assert escape_odbc_value("pass}word") == "{pass}}word}"


def test_normalize_encrypt_driver_17_maps_mandatory_to_yes():
    assert (
        normalize_encrypt_for_driver("ODBC Driver 17 for SQL Server", "mandatory")
        == "yes"
    )


def test_connection_string_driver_17_no_long_as_max():
    cfg = Settings.model_construct(
        sqlserver_driver="ODBC Driver 17 for SQL Server",
        sqlserver_encrypt="no",
        sqlserver_password="secret",
        sqlserver_host="localhost",
        sqlserver_port=1433,
        sqlserver_instance="",
        sqlserver_database="DemoDB",
        sqlserver_username="readonly",
        sqlserver_trust_server_certificate=True,
    )
    conn = cfg.connection_string()
    assert "ODBC Driver 17 for SQL Server" in conn
    assert "Encrypt=no" in conn
    assert "LongAsMax" not in conn
    assert "TrustServerCertificate=yes" in conn


def test_connection_string_driver_18_includes_long_as_max():
    cfg = Settings.model_construct(
        sqlserver_driver="ODBC Driver 18 for SQL Server",
        sqlserver_password="secret",
        sqlserver_host="localhost",
        sqlserver_port=1433,
        sqlserver_instance="",
        sqlserver_database="DemoDB",
        sqlserver_username="readonly",
        sqlserver_encrypt="yes",
        sqlserver_trust_server_certificate=True,
    )
    conn = cfg.connection_string()
    assert "LongAsMax=yes" in conn


def test_connection_string_escapes_password_with_semicolon():
    cfg = Settings.model_construct(
        sqlserver_driver="ODBC Driver 17 for SQL Server",
        sqlserver_password="Prelytical;Test",
        sqlserver_host="localhost",
        sqlserver_port=1433,
        sqlserver_instance="",
        sqlserver_database="DemoDB",
        sqlserver_username="readonly",
        sqlserver_encrypt="no",
        sqlserver_trust_server_certificate=True,
    )
    assert "PWD={Prelytical;Test};" in cfg.connection_string()
