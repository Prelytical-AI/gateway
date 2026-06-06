from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Prelytical Secure SQL Gateway", alias="APP_NAME")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8080, alias="APP_PORT")
    app_env: str = Field(default="local", alias="APP_ENV")

    sqlserver_host: str = Field(default="localhost", alias="SQLSERVER_HOST")
    sqlserver_port: int = Field(default=1433, alias="SQLSERVER_PORT")
    sqlserver_instance: str = Field(default="", alias="SQLSERVER_INSTANCE")
    sqlserver_database: str = Field(default="PrelyticalDemoDW", alias="SQLSERVER_DATABASE")
    sqlserver_username: str = Field(default="prelytical_readonly", alias="SQLSERVER_USERNAME")
    sqlserver_password: str = Field(default="CHANGE_ME", alias="SQLSERVER_PASSWORD")
    sqlserver_driver: str = Field(
        default="ODBC Driver 18 for SQL Server", alias="SQLSERVER_DRIVER"
    )
    sqlserver_trust_server_certificate: bool = Field(
        default=True, alias="SQLSERVER_TRUST_SERVER_CERTIFICATE"
    )
    sqlserver_encrypt: str = Field(default="yes", alias="SQLSERVER_ENCRYPT")
    sqlserver_allowed_schemas: str = Field(default="ai", alias="SQLSERVER_ALLOWED_SCHEMAS")
    sqlserver_blocked_schemas: str = Field(
        default="dbo,sys,INFORMATION_SCHEMA", alias="SQLSERVER_BLOCKED_SCHEMAS"
    )
    sqlserver_max_rows: int = Field(default=200, alias="SQLSERVER_MAX_ROWS")
    sqlserver_query_timeout_seconds: int = Field(
        default=30, alias="SQLSERVER_QUERY_TIMEOUT_SECONDS"
    )

    model_provider: str = Field(default="ollama", alias="MODEL_PROVIDER")
    model_base_url: str = Field(default="http://localhost:11434/v1", alias="MODEL_BASE_URL")
    model_name: str = Field(default="qwen2.5-coder:7b", alias="MODEL_NAME")
    model_api_key: str = Field(default="ollama", alias="MODEL_API_KEY")
    model_timeout_seconds: int = Field(default=600, alias="MODEL_TIMEOUT_SECONDS")
    model_skip_summarization: bool = Field(default=True, alias="MODEL_SKIP_SUMMARIZATION")
    model_max_schema_objects: int = Field(default=40, alias="MODEL_MAX_SCHEMA_OBJECTS")
    brief_timeout_seconds: int = Field(default=900, alias="BRIEF_TIMEOUT_SECONDS")
    brief_export_path: str = Field(default="", alias="BRIEF_EXPORT_PATH")

    audit_db_path: str = Field(default="./prelytical_audit.sqlite3", alias="AUDIT_DB_PATH")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    guardrails_require_select_only: bool = Field(
        default=True, alias="GUARDRAILS_REQUIRE_SELECT_ONLY"
    )
    guardrails_block_pii_columns: bool = Field(default=True, alias="GUARDRAILS_BLOCK_PII_COLUMNS")
    guardrails_blocked_column_patterns: str = Field(
        default=(
            "ssn,social_security,dob,date_of_birth,email,phone,account_number,"
            "routing_number,credit_card,card_number,password,secret,token,salary"
        ),
        alias="GUARDRAILS_BLOCKED_COLUMN_PATTERNS",
    )
    guardrails_require_allowed_schema: bool = Field(
        default=True, alias="GUARDRAILS_REQUIRE_ALLOWED_SCHEMA"
    )
    guardrails_append_top_limit: bool = Field(default=True, alias="GUARDRAILS_APPEND_TOP_LIMIT")

    @field_validator("sqlserver_trust_server_certificate", mode="before")
    @classmethod
    def parse_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @property
    def allowed_schemas(self) -> List[str]:
        return [s.strip().lower() for s in self.sqlserver_allowed_schemas.split(",") if s.strip()]

    @property
    def blocked_schemas(self) -> List[str]:
        return [s.strip().lower() for s in self.sqlserver_blocked_schemas.split(",") if s.strip()]

    @property
    def blocked_column_patterns(self) -> List[str]:
        return [
            p.strip().lower()
            for p in self.guardrails_blocked_column_patterns.split(",")
            if p.strip()
        ]

    @property
    def sql_server_spec(self) -> str:
        if self.sqlserver_instance:
            return f"{self.sqlserver_host}\\{self.sqlserver_instance},{self.sqlserver_port}"
        return f"{self.sqlserver_host},{self.sqlserver_port}"

    def connection_string(self) -> str:
        parts = [
            f"DRIVER={{{self.sqlserver_driver}}}",
            f"SERVER={self.sql_server_spec}",
            f"DATABASE={self.sqlserver_database}",
            f"UID={self.sqlserver_username}",
            f"PWD={self.sqlserver_password}",
            f"Encrypt={self.sqlserver_encrypt}",
        ]
        if self.sqlserver_trust_server_certificate:
            parts.append("TrustServerCertificate=yes")
        return ";".join(parts) + ";"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
