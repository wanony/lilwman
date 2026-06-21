from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from itsdangerous import URLSafeTimedSerializer
from lilwman.infrastructure.web.auth import (
    make_serializer, get_session_data, build_oauth_url,
)


def test_build_oauth_url_contains_client_id():
    url = build_oauth_url("12345", "http://localhost:8080/auth/callback")
    assert "12345" in url
    assert "discord.com/oauth2/authorize" in url
    assert "identify" in url


def test_session_roundtrip():
    s = make_serializer("test-secret-key")
    data = {"user_id": "123", "username": "alice", "avatar": ""}

    from itsdangerous import URLSafeTimedSerializer
    cookie = s.dumps(data)
    result = get_session_data(cookie, s)
    assert result is not None
    assert result["user_id"] == "123"


def test_get_session_data_invalid_returns_none():
    s = make_serializer("test-secret-key")
    result = get_session_data("not-a-valid-cookie", s)
    assert result is None


def test_get_session_data_missing_returns_none():
    s = make_serializer("test-secret-key")
    result = get_session_data(None, s)
    assert result is None
