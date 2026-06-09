import { getCrisis, getMisinfo } from "../lib/api";
import { usePolitician } from "../lib/PoliticianContext";
import { useData } from "../lib/useData";

export function CrisisDMs() {
  const { selected } = usePolitician();
  const { data, loading, error } = useData(() => getCrisis(selected!.id), selected?.id);
  const { data: misinfo } = useData(() => getMisinfo(selected!.id), selected?.id);

  if (!selected) return <p className="text-slate-500">No connected account.</p>;
  if (loading) return <p className="text-slate-500">Loading crisis view…</p>;
  if (error || !data) return <p className="text-red-600">Could not load: {error}</p>;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-ink">Crisis &amp; DMs</h2>
        <p className="text-slate-500">Spike alerts and DM activity for {selected.name}</p>
      </div>

      <div
        className={`rounded-lg border px-4 py-3 text-sm ${
          data.active_spike
            ? "border-red-200 bg-red-50 text-red-700"
            : "border-green-200 bg-green-50 text-green-700"
        }`}
      >
        {data.active_spike
          ? "⚠️ Active spike in the last 2 hours — a Firebase push has been sent (once)."
          : "✓ No active spike. Sentiment is within normal range."}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="glass-card sheen p-4">
          <div className="mb-3 text-sm font-medium text-slate-600">Recent spike events</div>
          {data.recent_spikes.length ? (
            <ul className="space-y-2 text-sm">
              {data.recent_spikes.map((s) => (
                <li
                  key={s.bucket_hour}
                  className="flex justify-between border-b pb-2 last:border-0"
                >
                  <span className="text-slate-600">
                    {new Date(s.bucket_hour).toLocaleString([], {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                    })}
                  </span>
                  <span className="font-semibold text-red-600">{s.negative_count} negative</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-400">No spikes recorded.</p>
          )}
        </div>

        <div className="glass-card sheen p-4">
          <div className="mb-3 text-sm font-medium text-slate-600">ManyChat DM activity</div>
          <div className="text-3xl font-bold text-pulse">{data.dm_count.toLocaleString()}</div>
          <p className="mt-1 text-xs text-slate-400">
            DM metadata only (Meta blocks DM content), received via the ManyChat webhook.
          </p>
        </div>
      </div>

      {misinfo && (
        <div
          className={`rounded-lg border p-4 ${
            misinfo.flagged ? "border-red-200 bg-red-50" : "border-slate-200 bg-white"
          }`}
        >
          <div className="mb-1 text-sm font-medium text-slate-600">
            Misinformation watch (last {misinfo.window_hours}h)
          </div>
          <div className="text-sm">
            {misinfo.flagged ? (
              <span className="font-semibold text-red-600">
                ⚠️ Elevated claim/rumor volume: {misinfo.claim_volume} mentions
              </span>
            ) : (
              <span className="text-slate-600">
                No unusual claim volume ({misinfo.claim_volume} flagged mentions).
              </span>
            )}
          </div>
          {misinfo.sample_texts.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-slate-500">
              {misinfo.sample_texts.map((t, i) => (
                <li key={i}>· {t}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
