const BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// One-time account linking. In demo mode the backend returns 400 (Meta not configured);
// once META_APP_ID/SECRET are set and USE_FAKE_CLIENTS=false, this kicks off real OAuth.
export function ConnectInstagram() {
  return (
    <div className="max-w-xl space-y-4">
      <h2 className="text-2xl font-semibold text-ink">Connect Instagram</h2>
      <p className="text-slate-600">
        Link the politician&apos;s Instagram <strong>Business/Creator</strong> account once. After
        that, CivicPulse ingests posts, comments, @-mentions and insights automatically every 30
        minutes — no further logins needed.
      </p>
      <a
        href={`${BASE}/api/auth/meta/connect`}
        className="inline-block rounded-lg bg-pulse px-4 py-2 text-sm font-medium text-white hover:opacity-90"
      >
        Connect Instagram account
      </a>
      <p className="text-xs text-slate-400">
        Demo mode (USE_FAKE_CLIENTS=true) uses synthetic data and this button is disabled
        server-side. See <code>docs/CONNECT_INSTAGRAM.md</code> to go live.
      </p>
    </div>
  );
}
