import { getPublicVoice } from "../lib/api";
import { usePolitician } from "../lib/PoliticianContext";
import { useData } from "../lib/useData";

const POS = "#4f8a5b";
const NEG = "#c0392b";
const NEU = "#9A7B5B";

const accent: Record<string, string> = { positive: POS, negative: NEG, neutral: NEU };
const leftBorder: Record<string, string> = {
  positive: "border-l-[#4f8a5b]",
  negative: "border-l-[#c0392b]",
  neutral: "border-l-[#9A7B5B]",
};

export function PublicVoice() {
  const { selected } = usePolitician();
  const { data, loading, error } = useData(() => getPublicVoice(selected!.id), selected?.id);

  if (!selected) return <p className="text-mocha">No connected account.</p>;
  if (loading) return <p className="text-mocha">Loading public voice…</p>;
  if (error || !data) return <p className="text-red-700">Could not load: {error}</p>;

  const totalSent = Object.values(data.by_sentiment).reduce((a, b) => a + b, 0) || 1;

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-extrabold text-ink">Public Voice</h2>
        <p className="text-coffee/70">What people are saying about {selected.name}</p>
      </div>

      <div className="grid grid-cols-3 gap-4 lg:grid-cols-6">
        {Object.entries(data.by_sentiment).map(([k, v]) => (
          <div key={k} className="kpi sheen">
            <div className="text-2xl font-extrabold" style={{ color: accent[k] ?? "#3A2E25" }}>
              {v}
            </div>
            <div className="text-xs uppercase tracking-wide text-mocha">{k}</div>
            <div className="text-[11px] text-coffee/60">{Math.round((v / totalSent) * 100)}%</div>
          </div>
        ))}
        {Object.entries(data.by_platform).map(([k, v]) => (
          <div key={k} className="kpi sheen">
            <div className="text-2xl font-extrabold text-pulse">{v}</div>
            <div className="text-xs uppercase tracking-wide text-mocha">{k}</div>
          </div>
        ))}
      </div>

      <div className="glass-card sheen p-4">
        <div className="mb-3 text-sm font-semibold text-coffee/80">Recent mentions</div>
        <div className="space-y-3">
          {data.samples.map((s, i) => (
            <div
              key={i}
              className={`glass-soft border-l-4 p-3 ${leftBorder[s.sentiment_label ?? "neutral"]}`}
            >
              <p className="text-sm text-ink">{s.text}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-coffee/70">
                <span className="rounded-md bg-white/50 px-1.5 py-0.5 uppercase">{s.platform}</span>
                <span style={{ color: accent[s.sentiment_label ?? "neutral"] }}>
                  {s.sentiment_label}
                </span>
                <span>· ❤ {s.likes}</span>
                {s.topics.map((t) => (
                  <span key={t} className="rounded-md bg-pulse/15 px-1.5 py-0.5 text-coffee">
                    #{t}
                  </span>
                ))}
              </div>
            </div>
          ))}
          {!data.samples.length && <p className="text-sm text-mocha">No mentions yet.</p>}
        </div>
      </div>
    </div>
  );
}
