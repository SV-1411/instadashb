"""Diagnose a Meta connection problem. Prints facts (no secrets/tokens).

python -m app.scripts.diagnose_meta
"""

from __future__ import annotations

import os

import httpx
from dotenv import load_dotenv

from app.config import get_settings


def main() -> int:
    load_dotenv()
    load_dotenv(os.path.join("..", ".env"))
    s = get_settings()
    base = f"https://graph.facebook.com/{s.meta_graph_api_version}"
    token = os.environ.get("META_USER_TOKEN", "")
    app_id = s.meta_app_id
    secret = s.meta_app_secret.get_secret_value()

    print(f"APP_ID set: {bool(app_id)} (len {len(app_id)})")
    print(f"APP_SECRET set: {bool(secret)} (len {len(secret)})")
    print(f"USER_TOKEN set: {bool(token)} (len {len(token)})")
    print(f"Graph version: {s.meta_graph_api_version}")
    print("-" * 50)

    # 1. Are App ID + Secret a valid pair?
    r = httpx.get(
        f"{base}/oauth/access_token",
        params={"client_id": app_id, "client_secret": secret, "grant_type": "client_credentials"},
        timeout=20,
    )
    if r.status_code < 400:
        print("App ID + Secret: VALID OK")
    else:
        print(f"App ID + Secret: INVALID FAIL -> {r.json().get('error', {}).get('message')}")

    # 2. Is the user token valid, and whose is it?
    r2 = httpx.get(f"{base}/me", params={"access_token": token, "fields": "id,name"}, timeout=20)
    if r2.status_code < 400:
        print(f"User token: VALID OK  (belongs to: {r2.json().get('name')})")
    else:
        print(f"User token: INVALID FAIL -> {r2.json().get('error', {}).get('message')}")

    # 2b. Which permissions did the user actually grant? (needs only the user token)
    rp = httpx.get(f"{base}/me/permissions", params={"access_token": token}, timeout=20)
    if rp.status_code < 400:
        perms = rp.json().get("data", [])
        granted = sorted(p["permission"] for p in perms if p.get("status") == "granted")
        declined = sorted(p["permission"] for p in perms if p.get("status") == "declined")
        print(f"Granted scopes: {', '.join(granted) or '(none)'}")
        if declined:
            print(f"Declined scopes: {', '.join(declined)}")
        for needed in ("pages_show_list", "instagram_basic", "pages_read_engagement"):
            mark = "OK" if needed in granted else "MISSING"
            print(f"   {needed}: {mark}")

    # 3. What Pages does the token see, and is Instagram linked?
    r3 = httpx.get(
        f"{base}/me/accounts",
        params={"access_token": token, "fields": "name,instagram_business_account"},
        timeout=20,
    )
    if r3.status_code < 400:
        pages = r3.json().get("data", [])
        print(f"Pages visible to token: {len(pages)}")
        for p in pages:
            linked = bool(p.get("instagram_business_account"))
            print(f"   - {p.get('name')} | Instagram linked: {linked}")
        if not pages:
            print("   (none — token likely missing 'pages_show_list' OR you manage no Page)")
    else:
        print(f"me/accounts: ERROR -> {r3.json().get('error', {}).get('message')}")

    # 4. Token scopes (only if app creds valid).
    if r.status_code < 400:
        app_token = f"{app_id}|{secret}"
        r4 = httpx.get(
            f"{base}/debug_token",
            params={"input_token": token, "access_token": app_token},
            timeout=20,
        )
        if r4.status_code < 400:
            d = r4.json().get("data", {})
            print(f"Token's app id: {d.get('app_id')}  (should match APP_ID above)")
            print(f"Token scopes: {', '.join(d.get('scopes', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
