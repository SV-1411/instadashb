"""Connect a real Instagram Business account using a manually-minted token.

Faster than the browser OAuth flow for a single account: paste a User token from
the Graph API Explorer and this discovers your IG Business account, upgrades the
token to long-lived (~60 days), and stores it ENCRYPTED on a politician row.

Usage (from backend/, venv active, META_APP_ID/SECRET set in .env):
    python -m app.scripts.connect_with_token <USER_ACCESS_TOKEN>
  or set META_USER_TOKEN in .env and run with no argument.

Then:  python -c "from app.workers.tasks import ingest_all; print(ingest_all())"
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import select

from app.clients.meta import _graph_get, discover_ig_account, exchange_for_long_lived
from app.clients.resilient import ExternalServiceError
from app.database import SessionLocal
from app.models.politician import Politician


def main() -> int:
    # Load the repo-root .env (the app's Settings does this, but plain os.environ does not).
    load_dotenv()  # auto-discovers .env walking up from the cwd
    load_dotenv(os.path.join("..", ".env"))  # explicit repo-root fallback
    token = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("META_USER_TOKEN", "")
    if not token:
        print("ERROR: pass the token as an argument or set META_USER_TOKEN in .env.")
        return 1

    # Upgrade to a long-lived token if possible (needs META_APP_ID/SECRET).
    try:
        long_lived = exchange_for_long_lived(token)
        print("✓ Upgraded to a long-lived token (~60 days).")
    except (ExternalServiceError, KeyError) as exc:
        print(f"! Could not upgrade token ({exc}); using the token as-is.")
        long_lived = token

    try:
        acct = discover_ig_account(long_lived)
    except ExternalServiceError as exc:
        print(f"ERROR: could not find an Instagram Business account: {exc}")
        print("  Check: IG is a Business/Creator account AND linked to a Facebook Page,")
        print("  and the token has scopes instagram_basic, pages_show_list, pages_read_engagement.")
        return 2

    ig_user_id = acct["ig_user_id"]
    try:
        profile = _graph_get(ig_user_id, {"fields": "username,name", "access_token": long_lived})
    except ExternalServiceError:
        profile = {}
    name = profile.get("name") or profile.get("username") or "My Account"

    db = SessionLocal()
    try:
        pol = db.execute(
            select(Politician).where(Politician.ig_account_id == ig_user_id)
        ).scalar_one_or_none()
        if pol is None:
            pol = Politician(name=name, ig_account_id=ig_user_id)
            db.add(pol)
        pol.fb_page_id = acct["page_id"]
        pol.meta_token = long_lived  # encrypted at rest
        db.commit()
        db.refresh(pol)
        print(f"✓ Connected '{name}' (politician id={pol.id}, ig={ig_user_id}).")
        print("Next: set USE_FAKE_CLIENTS=false in .env, then run:")
        print('  python -c "from app.workers.tasks import ingest_all; print(ingest_all())"')
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
