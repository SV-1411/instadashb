const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// One-time account linking. In demo mode the backend returns 400 (Meta not configured);
// once credentials are set and USE_FAKE_CLIENTS=false, this kicks off real OAuth.
export function ConnectInstagram() {
  return (
    <div className="max-w-xl space-y-5">
      <div>
        <h2 className="text-2xl font-extrabold text-ink">Connect Instagram</h2>
        <p className="text-coffee/70">
          Link the politician&apos;s Instagram <strong>Business/Creator</strong> account once. After
          that, CivicPulse ingests posts, comments, @-mentions and insights automatically every 30
          minutes — no further logins needed.
        </p>
      </div>

      <div className="glass-card sheen p-5">
        <a
          href={`${BASE}/api/auth/meta/connect`}
          className="inline-block rounded-xl bg-pulse px-4 py-2 text-sm font-semibold text-white shadow-glass transition hover:opacity-90"
        >
          Connect Instagram account
        </a>
        <p className="mt-3 text-xs text-mocha">
          Demo mode (USE_FAKE_CLIENTS=true) uses synthetic data and this button is disabled
          server-side. See <code className="rounded bg-white/50 px-1">docs/CONNECT_INSTAGRAM.md</code>{" "}
          to go live (incl. the no-Facebook-Page Instagram-Login path).
        </p>
      </div>
    </div>
  );
}
