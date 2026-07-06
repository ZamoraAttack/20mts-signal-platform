import asyncio
import json
import time

import httpx
import pytest

from app.schwab.auth import SchwabAuth, SchwabAuthError
from app.schwab.auth_setup import _extract_code


def test_extract_code_parses_query_param():
    url = "https://127.0.0.1/?code=ABC%40123&session=xyz"
    assert _extract_code(url) == "ABC@123"


def test_extract_code_missing_raises():
    with pytest.raises(ValueError):
        _extract_code("https://127.0.0.1/?session=xyz")


def test_get_access_token_returns_cached_when_valid(tmp_path):
    tokens_file = tmp_path / "schwab_tokens.json"
    tokens_file.write_text(json.dumps({
        "access_token": "cached-token",
        "refresh_token": "refresh-abc",
        "expires_at": time.time() + 1000,
    }))
    auth = SchwabAuth("client-id", "client-secret", "https://127.0.0.1", str(tokens_file))

    token = asyncio.run(auth.get_access_token())
    assert token == "cached-token"


def test_get_access_token_missing_file_raises(tmp_path):
    auth = SchwabAuth("client-id", "client-secret", "https://127.0.0.1", str(tmp_path / "missing.json"))
    with pytest.raises(SchwabAuthError):
        asyncio.run(auth.get_access_token())


@pytest.mark.asyncio
async def test_get_access_token_refreshes_when_near_expiry(monkeypatch, tmp_path):
    tokens_file = tmp_path / "schwab_tokens.json"
    tokens_file.write_text(json.dumps({
        "access_token": "old-token",
        "refresh_token": "refresh-abc",
        "expires_at": time.time() - 10,
    }))

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/oauth/token"
        body = request.read().decode()
        assert "grant_type=refresh_token" in body
        assert "refresh_token=refresh-abc" in body
        return httpx.Response(200, json={
            "access_token": "new-token",
            "refresh_token": "refresh-def",
            "expires_in": 1800,
        })

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.schwab.auth.httpx.AsyncClient",
        lambda *a, **kw: real_async_client(transport=transport),
    )

    auth = SchwabAuth("client-id", "client-secret", "https://127.0.0.1", str(tokens_file))
    token = await auth.get_access_token()

    assert token == "new-token"
    saved = json.loads(tokens_file.read_text())
    assert saved["access_token"] == "new-token"
    assert saved["refresh_token"] == "refresh-def"


@pytest.mark.asyncio
async def test_refresh_failure_raises_with_guidance(monkeypatch, tmp_path):
    tokens_file = tmp_path / "schwab_tokens.json"
    tokens_file.write_text(json.dumps({
        "access_token": "old-token",
        "refresh_token": "expired-refresh",
        "expires_at": time.time() - 10,
    }))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="refresh token expired")

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.schwab.auth.httpx.AsyncClient",
        lambda *a, **kw: real_async_client(transport=transport),
    )

    auth = SchwabAuth("client-id", "client-secret", "https://127.0.0.1", str(tokens_file))
    with pytest.raises(SchwabAuthError, match="auth_setup"):
        await auth.get_access_token()


@pytest.mark.asyncio
async def test_exchange_code_for_tokens(monkeypatch, tmp_path):
    tokens_file = tmp_path / "schwab_tokens.json"

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        assert "grant_type=authorization_code" in body
        assert "code=auth-code-123" in body
        return httpx.Response(200, json={
            "access_token": "first-token",
            "refresh_token": "first-refresh",
            "expires_in": 1800,
        })

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.schwab.auth.httpx.AsyncClient",
        lambda *a, **kw: real_async_client(transport=transport),
    )

    auth = SchwabAuth("client-id", "client-secret", "https://127.0.0.1", str(tokens_file))
    tokens = await auth.exchange_code_for_tokens("auth-code-123")

    assert tokens["access_token"] == "first-token"
    saved = json.loads(tokens_file.read_text())
    assert saved["refresh_token"] == "first-refresh"
