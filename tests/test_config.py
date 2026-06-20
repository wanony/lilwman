import pytest
from pydantic import ValidationError

from lilwman.config import Settings


def test_settings_required_fields_accepted():
    s = Settings(discord_token="my-token", discord_guild_id=12345)
    assert s.discord_token == "my-token"
    assert s.discord_guild_id == 12345


def test_settings_ollama_host_default():
    s = Settings(discord_token="t", discord_guild_id=1)
    assert s.ollama_host == "http://localhost:11434"


def test_settings_ollama_model_default():
    s = Settings(discord_token="t", discord_guild_id=1)
    assert s.ollama_model == "qwen2.5:1.5b"


def test_settings_db_path_default():
    s = Settings(discord_token="t", discord_guild_id=1)
    assert s.db_path == "data/lilwman.db"


def test_settings_custom_ollama_host():
    s = Settings(
        discord_token="t",
        discord_guild_id=1,
        ollama_host="http://remote:11434",
    )
    assert s.ollama_host == "http://remote:11434"


def test_settings_custom_ollama_model():
    s = Settings(
        discord_token="t",
        discord_guild_id=1,
        ollama_model="llama3.2:3b",
    )
    assert s.ollama_model == "llama3.2:3b"


def test_settings_custom_db_path():
    s = Settings(
        discord_token="t",
        discord_guild_id=1,
        db_path="/var/data/bot.db",
    )
    assert s.db_path == "/var/data/bot.db"


def test_settings_guild_id_is_int():
    s = Settings(discord_token="t", discord_guild_id=999888777)
    assert isinstance(s.discord_guild_id, int)
    assert s.discord_guild_id == 999888777
