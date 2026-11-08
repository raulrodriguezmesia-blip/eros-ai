from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Eros AI"
    app_version: str = "0.1.0"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8080

    # Feature Flags (env-based, overridable by Azure App Config)
    deep_ast_analysis: bool = False
    auto_patch_generation: bool = False
    strict_compliance_mode: bool = False

    # Microsoft Foundry IQ
    foundry_endpoint: str = ""
    foundry_api_key: str = ""
    foundry_model: str = "gpt-4o"

    # Analysis limits
    max_code_length: int = 50_000
    analysis_timeout_seconds: int = 60
    max_tokens_per_analysis: int = 4096


settings = Settings()
