import { getCrisis, getMisinfo } from "../lib/api";
import { usePolitician } from "../lib/PoliticianContext";
import { useData } from "../lib/useData";

export function CrisisDMs() {
  const { selected } = usePolitician();
  const { data, loading, error } = useData(() => getCrisis(selected!.id), selected?.id);
  const { data: misinfo } = useData(() => getMisinfo(selected!.id), selected?.id);

  if (!selected) return <p className="text-mocha">No connected account.</p>;
  if (loading) return <p className="text-mocha">Loading crisis view…</p>;
  if (error || !data) return <p className="text-red-700">Could not load: {error}</p>;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-extrabold text-ink">Crisis &amp; DMs</h2>
        <p className="text-coffee/70">Spike alerts and DM activity for {selected.name}</p>
      </div>

      <div
        className={`glass-card sheen px-4 py-3 text-sm ${
          data.active_spike ? "border-red-300/60 text-red-800" : "border-green-300/50 text-green-800"
        }`}
      >
        {data.active_spike
          ? "⚠️ Active spike in the last 2 hours — a Firebase push has been sent (once)."
          : "✓ No active spike. Sentiment is within normal range."}
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="glass-card sheen p-4">
          <div className="mb-3 text-sm font-semibold text-coffee/80">Recent spike events</div>
          {data.recent_spikes.length ? (
            <ul className="space-y-2 text-sm">
              {data.recent_spikes.map((s) => (
                <li
                  key={s.bucket_hour}
                  className="glass-soft flex items-center justify-between rounded-lg px-3 py-2"
                >
                  <span className="text-coffee/80">
                    {new Date(s.bucket_hour).toLocaleString([], {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                    })}
                  </span>
                  <span className="font-bold text-red-700">{s.negative_count} negative</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-mocha">No spikes recorded.</p>
          )}
        </div>

        <div className="glass-card sheen p-4">
          <div className="mb-3 text-sm font-semibold text-coffee/80">ManyChat DM activity</div>
          <div className="text-4xl font-extrabold text-pulse">{data.dm_count.toLocaleString()}</div>
          <p className="mt-1 text-xs text-mocha">
            DM metadata only (Meta blocks DM content), received via the ManyChat webhook.
          </p>
        </div>
      </div>

      {misinfo && (
        <div
          className={`glass-card sheen p-4 ${misinfo.flagged ? "border-red-300/60" : ""}`}
        >
          <div className="mb-1 text-sm font-semibold text-coffee/80">
            Misinformation watch · last {misinfo.window_hours}h
          </div>
          {misinfo.flagged ? (
            <div className="font-bold text-red-700">
              ⚠️ Elevated claim/rumor volume: {misinfo.claim_volume} mentions
            </div>
          ) : (
            <div className="text-coffee/80">
              No unusual claim volume ({misinfo.claim_volume} flagged).
            </div>
          )}
          {misinfo.sample_texts.length > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-mocha">
              {misinfo.sample_texts.map((t, i) => (
                <li key={i} className="glass-soft rounded-md px-2 py-1">
                  · {t}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
