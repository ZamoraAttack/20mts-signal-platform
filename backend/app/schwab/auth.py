"""
OAuth2 token management for the Schwab Trader API.

Schwab uses a standard OAuth2 authorization-code flow:
  1. A one-time interactive authorization (see auth_setup.py) produces an
     access token (valid ~30 minutes) and a refresh token (valid ~7 days).
  2. This module loads the saved tokens and transparently refreshes the
     access token using the refresh token when it is close to expiring.
  3. The refresh token itself expires after 7 days and requires re-running
     auth_setup.py — there is no way around this with Schwab's API.

Endpoint and token-lifetime details are based on Schwab's published OAuth
flow (developer.schwab.com "OAuth Restart vs Refresh Token" guide) and the
widely-used schwab-py reference implementation. These should be re-verified
once Market Data Production documentation access is approved on this account.
"""

import base64
import json
import time
from pathlib import Path
from typing import Optional

import httpx

TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"
AUTHORIZE_URL = "https://api.schwabapi.com/v1/oauth/authorize"

# Refresh the access token this many seconds before it actually expires.
EXPIRY_SAFETY_MARGIN_SECONDS = 60


class SchwabAuthError(RuntimeError):
    pass


class SchwabAuth:
    """Loads, refreshes, and persists Schwab OAuth2 tokens on disk."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, tokens_path: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.tokens_path = Path(tokens_path)
        self._tokens: Optional[dict] = None

    @property
    def authorization_url(self) -> str:
        return (
            f"{AUTHORIZE_URL}?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}&response_type=code"
        )

    def _basic_auth_header(self) -> dict[str, str]:
        raw = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        return {"Authorization": f"Basic {base64.b64encode(raw).decode('ascii')}"}

    def _load_tokens(self) -> dict:
        if not self.tokens_path.exists():
            raise SchwabAuthError(
                f"Token file not found: {self.tokens_path}. "
                "Run `python -m app.schwab.auth_setup` to complete OAuth2 authorization."
            )
        with open(self.tokens_path) as f:
            return json.load(f)

    def _save_tokens(self, tokens: dict) -> None:
        self.tokens_path.write_text(json.dumps(tokens, indent=2))
        self._tokens = tokens

    def _store_token_response(self, payload: dict) -> dict:
        refresh_token = payload.get("refresh_token")
        if refresh_token is None and self._tokens is not None:
            refresh_token = self._tokens.get("refresh_token")
        tokens = {
            "access_token": payload["access_token"],
            "refresh_token": refresh_token,
            "expires_at": time.time() + payload.get("expires_in", 1800),
        }
        self._save_tokens(tokens)
        return tokens

    async def exchange_code_for_tokens(self, code: str) -> dict:
        """Initial token exchange (authorization_code grant). Used by auth_setup.py."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                headers=self._basic_auth_header(),
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
            )
        if resp.status_code != 200:
            raise SchwabAuthError(
                f"Failed to exchange authorization code (HTTP {resp.status_code}): {resp.text}"
            )
        return self._store_token_response(resp.json())

    async def _refresh(self) -> dict:
        if self._tokens is None:
            self._tokens = self._load_tokens()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                TOKEN_URL,
                headers=self._basic_auth_header(),
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._tokens["refresh_token"],
                },
            )
        if resp.status_code != 200:
            raise SchwabAuthError(
                f"Failed to refresh Schwab access token (HTTP {resp.status_code}): {resp.text}. "
                "The refresh token may have expired (valid ~7 days) — "
                "run `python -m app.schwab.auth_setup` again."
            )
        return self._store_token_response(resp.json())

    async def get_access_token(self) -> str:
        if self._tokens is None:
            self._tokens = self._load_tokens()
        if time.time() >= self._tokens["expires_at"] - EXPIRY_SAFETY_MARGIN_SECONDS:
            await self._refresh()
        return self._tokens["access_token"]
