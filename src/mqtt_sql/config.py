from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    mqtt_host: str = "localhost"
    mqtt_port: int = 1883

    mssql_conn_str: str

    http_host: str = "0.0.0.0"
    http_port: int = 8000

    log_level: str = "INFO"


settings = Settings()
