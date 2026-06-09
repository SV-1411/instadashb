"""Connect an Instagram Business/Creator account via Instagram Login (no FB Page).

Paste an Instagram User token (from the app's Instagram product -> "Generate access
token") into META_USER_TOKEN, then run this. It identifies your IG account, upgrades
the token to long-lived (~60 days) when possible, and stores it ENCRYPTED.

    python -m app.scripts.connect_ig_login

Then:  set META_SOURCE=instagram_login + USE_FAKE_CLIENTS=false in .env, and run
       python -c "from app.workers.tasks import ingest_all; print(ingest_all())"
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import select

from app.clients.instagram_login import ig_get
from app.clients.resilient import ExternalServiceError
from app.config import get_settings
from app.database import SessionLocal
from app.models.politician import Politician


def main() -> int:
    load_dotenv()
    load_dotenv(os.path.join("..", ".env"))
    token = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("META_USER_TOKEN", "")
    if not token:
        print("ERROR: set META_USER_TOKEN in .env (the Instagram token) or pass it as an argument.")
        return 1

    secret = get_settings().meta_app_secret.get_secret_value()

    # Upgrade to a long-lived Instagram token if the app secret works.
    long_lived = token
    if secret:
        try:
            data = ig_get(
                "access_token",
                {"grant_type": "ig_exchange_token", "client_secret": secret, "access_token": token},
            )
            long_lived = str(data.get("access_token", token))
            print("OK upgraded to a long-lived Instagram token (~60 days).")
        except ExternalServiceError as exc:
            print(f"! Could not upgrade token ({exc}); using it as-is (shorter-lived).")

    try:
        me = ig_get("me", {"fields": "user_id,username,account_type", "access_token": long_lived})
    except ExternalServiceError as exc:
        print(f"ERROR: token did not work against graph.instagram.com: {exc}")
        print("  Make sure this is an INSTAGRAM token (from the Instagram product's")
        print("  'Generate access token'), not the Facebook Graph API Explorer token.")
        return 2

    user_id = str(me.get("user_id") or me.get("id"))
    username = me.get("username") or "My Instagram"
    acct_type = me.get("account_type", "?")
    print(f"OK Instagram account: @{username} (id={user_id}, type={acct_type})")

    db = SessionLocal()
    try:
        pol = db.execute(
            select(Politician).where(Politician.ig_account_id == user_id)
        ).scalar_one_or_none()
        if pol is None:
            pol = Politician(name=str(username), ig_account_id=user_id)
            db.add(pol)
        pol.meta_token = long_lived
        db.commit()
        db.refresh(pol)
        print(f"OK Connected (politician id={pol.id}).")
        print("Next: ensure .env has META_SOURCE=instagram_login and USE_FAKE_CLIENTS=false, then:")
        print('  python -c "from app.workers.tasks import ingest_all; print(ingest_all())"')
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
