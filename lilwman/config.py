from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    discord_token: str
    discord_guild_id: int
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:1.5b"
    db_path: str = "data/lilwman.db"
    rss_bridge_url: str = "http://localhost:3000"
    discord_client_id: str = ""
    discord_client_secret: str = ""
    web_base_url: str = "http://localhost:8080"
    web_port: int = 8080
    web_secret_key: str = ""
    web_guild_id: str = ""
