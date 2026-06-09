import { getPublicVoice } from "../lib/api";
import { usePolitician } from "../lib/PoliticianContext";
import { useData } from "../lib/useData";

const toneClass: Record<string, string> = {
  positive: "border-green-200 bg-green-50",
  negative: "border-red-200 bg-red-50",
  neutral: "border-slate-200 bg-white",
};

export function PublicVoice() {
  const { selected } = usePolitician();
  const { data, loading, error } = useData(() => getPublicVoice(selected!.id), selected?.id);

  if (!selected) return <p className="text-slate-500">No connected account.</p>;
  if (loading) return <p className="text-slate-500">Loading public voice…</p>;
  if (error || !data) return <p className="text-red-600">Could not load: {error}</p>;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-ink">Public Voice</h2>
        <p className="text-slate-500">What people are saying about {selected.name}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {Object.entries(data.by_sentiment).map(([k, v]) => (
          <div key={k} className="glass-card sheen p-3">
            <div className="text-xl font-bold text-ink">{v}</div>
            <div className="text-xs uppercase text-slate-400">{k}</div>
          </div>
        ))}
        {Object.entries(data.by_platform).map(([k, v]) => (
          <div key={k} className="glass-card sheen p-3">
            <div className="text-xl font-bold text-pulse">{v}</div>
            <div className="text-xs uppercase text-slate-400">{k}</div>
          </div>
        ))}
      </div>

      <div className="space-y-3">
        {data.samples.map((s, i) => (
          <div
            key={i}
            className={`rounded-lg border p-3 ${toneClass[s.sentiment_label ?? "neutral"]}`}
          >
            <p className="text-sm text-slate-800">{s.text}</p>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              <span className="uppercase">{s.platform}</span>
              <span>· {s.sentiment_label}</span>
              <span>· ❤ {s.likes}</span>
              {s.topics.map((t) => (
                <span key={t} className="rounded bg-slate-200 px-1.5 py-0.5 text-slate-600">
                  {t}
                </span>
              ))}
            </div>
          </div>
        ))}
        {!data.samples.length && <p className="text-sm text-slate-400">No mentions yet.</p>}
      </div>
    </div>
  );
}
