"""
One-time interactive OAuth2 authorization for the Schwab Trader API.

Run this after setting SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET in .env
(your app's "App Key" and "Secret" from developer.schwab.com). It must be
re-run roughly every 7 days, since Schwab refresh tokens expire after 7 days.

Usage:
    cd backend
    python -m app.schwab.auth_setup
"""

import asyncio
import sys
from urllib.parse import parse_qs, unquote, urlparse

from ..config import settings
from .auth import SchwabAuth


def _extract_code(redirect_url: str) -> str:
    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)
    if "code" not in params:
        raise ValueError("No 'code' parameter found in the pasted URL.")
    return unquote(params["code"][0])


async def main() -> None:
    if not settings.schwab_client_id or not settings.schwab_client_secret:
        print("SCHWAB_CLIENT_ID and SCHWAB_CLIENT_SECRET must be set in .env first.")
        sys.exit(1)

    auth = SchwabAuth(
        client_id=settings.schwab_client_id,
        client_secret=settings.schwab_client_secret,
        redirect_uri=settings.schwab_redirect_uri,
        tokens_path=settings.schwab_tokens_path,
    )

    print("1. Open this URL in a browser, log in, and authorize the app:\n")
    print(f"   {auth.authorization_url}\n")
    print("2. After approving, Schwab redirects to your callback URL")
    print(f"   ({settings.schwab_redirect_uri}). The browser will likely show")
    print("   a 'site can't be reached' error — that's expected. Copy the")
    print("   FULL URL from the browser's address bar anyway.\n")

    redirect_url = input("Paste the full redirect URL here: ").strip()
    code = _extract_code(redirect_url)

    tokens = await auth.exchange_code_for_tokens(code)
    print(f"\nSuccess. Tokens saved to {settings.schwab_tokens_path}")
    print(f"Access token expires at (unix time): {tokens['expires_at']:.0f}")
    print("Refresh token is valid for ~7 days — re-run this script after it expires.")


if __name__ == "__main__":
    asyncio.run(main())
