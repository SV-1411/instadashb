# Connecting a real Instagram account (and the scraper supplement)

CivicPulse gets data two ways (you chose **both**):

| Source | What it gives | What you must provide | Cost |
|--------|---------------|------------------------|------|
| **Official Meta OAuth** (backbone) | His posts, comments on his posts, @-mentions/tags, reach/impressions/insights, audience city/age/gender | A Meta app + one-time login by the account owner | Free |
| **Scraper** (supplement) | Broad public chatter ABOUT him (untagged mentions, hashtags, keyword search) that the official API can't see | A paid provider API key (Apify / SociaVault / similar) | ~$30–100+/mo |

The dashboard reads only our DB — neither source is ever called on page load.

---

## A. Official Meta OAuth — setup (free, ~20 min, one time)

**Prerequisite:** the politician's Instagram must be a **Business or Creator** account, connected
to a **Facebook Page**. (Personal IG accounts get *no* API access — this is a hard Meta rule.)

1. Create an app at https://developers.facebook.com/apps → type **Business**.
2. Add the **Instagram Graph API** and **Facebook Login** products.
3. In *App settings → Basic*, copy **App ID** and **App Secret** into `.env`:
   ```
   META_APP_ID=...
   META_APP_SECRET=...
   META_OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/meta/callback
   USE_FAKE_CLIENTS=false
   ```
4. In *Facebook Login → Settings*, add the redirect URI above to **Valid OAuth Redirect URIs**.
5. Request these permissions (App Review needed before production, but works for your own
   account in *Development* mode immediately):
   `instagram_basic`, `instagram_manage_insights`, `pages_show_list`,
   `pages_read_engagement`, `business_management`.
   > ⚠️ Verify the exact scope list in your App dashboard — Meta renames/splits these
   > periodically. The code requests the set above; adjust `META_SCOPES` if Meta flags one.
6. Start the backend, open `http://localhost:8000/api/auth/meta/connect` (or click **Connect
   Instagram** in the dashboard), log in as the account owner, approve. We exchange the code for a
   **long-lived token (~60 days)**, store it **encrypted**, and the worker refreshes it
   automatically and ingests every 30 min thereafter.

**What you do NOT get from the official API** (by Meta policy, not our limitation):
DM contents, ward/pincode geo, and untagged "what everyone says about him" across all of Instagram.
That last gap is what the scraper fills.

---

## B. Scraper supplement (paid — for broad public mentions)

1. Pick a provider (e.g. **Apify** Instagram scrapers, or **SociaVault/SocialData**). Get an API token.
2. Put it in `.env`:
   ```
   SCRAPER_PROVIDER=apify          # apify | socialdata | fake
   SCRAPER_API_KEY=...
   SCRAPER_QUERIES=@demo_netaji,#demonetaji,"Demo Netaji"
   ```
3. The worker's scraper task pulls public posts/comments matching those queries and writes them
   into the same unified `mentions` table (`source_type="mention"`), so they flow through the same
   sentiment → aggregate → spike pipeline.

> Legal/ToS note: scraping public Instagram data is against Meta's ToS and can break when Instagram
> changes its site. Treat it as best-effort enrichment, not a guaranteed feed. The official OAuth
> backbone is the reliable source of truth.

---

## Switching between demo and live
- `USE_FAKE_CLIENTS=true` (default) → everything runs offline with realistic fake data.
- `USE_FAKE_CLIENTS=false` → the Real Meta client + your chosen scraper are used. Missing/invalid
  credentials surface as a token-health warning on the dashboard (never a crash).
