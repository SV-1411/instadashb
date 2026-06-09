import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getCommandCenter, getPublicVoice, getTrends } from "../lib/api";
import { usePolitician } from "../lib/PoliticianContext";
import { useData } from "../lib/useData";

const POS = "#4f8a5b";
const NEG = "#c0392b";
const NEU = "#9A7B5B";
const ACCENT = "#A9764E";

function scoreColor(s: number): string {
  if (s >= 60) return POS;
  if (s >= 40) return ACCENT;
  return NEG;
}

function Kpi({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) {
  return (
    <div className="kpi sheen">
      <div className="text-2xl font-extrabold" style={{ color: color ?? "#3A2E25" }}>
        {value}
      </div>
      <div className="text-xs uppercase tracking-wide text-mocha">{label}</div>
      {sub && <div className="mt-0.5 text-[11px] text-coffee/70">{sub}</div>}
    </div>
  );
}

export function CommandCenter() {
  const { selected } = usePolitician();
  const id = selected?.id;
  const { data, loading, error } = useData(() => getCommandCenter(id!), id);
  const { data: trends } = useData(() => getTrends(id!), id);
  const { data: voice } = useData(() => getPublicVoice(id!), id);

  if (!selected) return <p className="text-mocha">No connected account.</p>;
  if (loading) return <p className="text-mocha">Loading command center…</p>;
  if (error || !data) return <p className="text-red-700">Could not load: {error}</p>;

  const total = data.positive_count + data.negative_count + data.neutral_count || 1;
  const posPct = Math.round((data.positive_count / total) * 100);
  const negPct = Math.round((data.negative_count / total) * 100);
  const gauge = [{ name: "score", value: data.sentiment_score, fill: scoreColor(data.sentiment_score) }];
  const dist = [
    { name: "Positive", value: data.positive_count, fill: POS },
    { name: "Negative", value: data.negative_count, fill: NEG },
    { name: "Neutral", value: data.neutral_count, fill: NEU },
  ];
  const trend = data.trend.map((t) => ({
    t: new Date(t.bucket_hour).toLocaleTimeString([], { hour: "2-digit" }),
    score: t.sentiment_score,
    neg: t.negative_count,
  }));
  const topics = (trends?.top_topics ?? []).slice(0, 6).map((x) => ({ topic: x.topic, count: x.count }));
  const platforms = Object.entries(voice?.by_platform ?? {});

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-2xl font-extrabold text-ink">Command Center</h2>
        <p className="text-coffee/70">
          {selected.name}
          {selected.constituency ? ` · ${selected.constituency}` : ""}
        </p>
      </div>

      {data.active_spike && (
        <div className="glass-card sheen border-red-300/60 bg-red-50/50 px-4 py-3 text-sm text-red-800">
          ⚠️ <strong>Active negative spike</strong> — negative mentions this hour are well above baseline.
        </div>
      )}
      {data.calibrating && (
        <div className="glass-card sheen px-4 py-2 text-xs text-coffee/80">
          Calibrating — less than a day of history; scores sharpen as data accrues.
        </div>
      )}

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
        <Kpi label="Sentiment" value={`${data.sentiment_score}`} sub="0–100" color={scoreColor(data.sentiment_score)} />
        <Kpi label="Positive" value={`${posPct}%`} sub={`${data.positive_count} mentions`} color={POS} />
        <Kpi label="Negative" value={`${negPct}%`} sub={`${data.negative_count} mentions`} color={NEG} />
        <Kpi label="Mentions (24h)" value={`${data.total_mentions}`} color={ACCENT} />
        <Kpi label="Topics" value={`${trends?.top_topics.length ?? 0}`} sub="tracked" />
        <Kpi label="Spike" value={data.active_spike ? "LIVE" : "calm"} color={data.active_spike ? NEG : POS} />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {/* Gauge */}
        <div className="glass-card sheen p-4">
          <div className="mb-1 text-sm font-semibold text-coffee/80">Overall sentiment</div>
          <ResponsiveContainer width="100%" height={190}>
            <RadialBarChart innerRadius="72%" outerRadius="100%" data={gauge} startAngle={210} endAngle={-30}>
              <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
              <RadialBar background dataKey="value" cornerRadius={10} />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="-mt-24 text-center text-4xl font-extrabold" style={{ color: scoreColor(data.sentiment_score) }}>
            {data.sentiment_score}
          </div>
          <div className="mt-16 text-center text-xs text-mocha">{data.total_mentions} mentions in view</div>
        </div>

        {/* Distribution donut */}
        <div className="glass-card sheen p-4">
          <div className="mb-1 text-sm font-semibold text-coffee/80">Sentiment mix</div>
          <ResponsiveContainer width="100%" height={190}>
            <PieChart>
              <Pie data={dist} dataKey="value" nameKey="name" innerRadius={50} outerRadius={75} paddingAngle={3}>
                {dist.map((d) => (
                  <Cell key={d.name} fill={d.fill} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex justify-center gap-3 text-xs text-coffee/80">
            <span>🟢 {data.positive_count}</span>
            <span>🔴 {data.negative_count}</span>
            <span>⚪ {data.neutral_count}</span>
          </div>
        </div>

        {/* Platform split */}
        <div className="glass-card sheen p-4">
          <div className="mb-3 text-sm font-semibold text-coffee/80">Where people talk</div>
          {platforms.length ? (
            <div className="space-y-3">
              {platforms.map(([p, n]) => {
                const pct = Math.round((n / (voice ? Object.values(voice.by_platform).reduce((a, b) => a + b, 0) : 1)) * 100);
                return (
                  <div key={p}>
                    <div className="flex justify-between text-xs text-coffee/80">
                      <span className="uppercase">{p}</span>
                      <span>{n} · {pct}%</span>
                    </div>
                    <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-white/50">
                      <div className="h-full rounded-full" style={{ width: `${pct}%`, background: ACCENT }} />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-mocha">No mentions yet.</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Trend */}
        <div className="glass-card sheen p-4">
          <div className="mb-3 text-sm font-semibold text-coffee/80">Sentiment trend (24h)</div>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(111,78,55,0.12)" />
              <XAxis dataKey="t" tick={{ fontSize: 11, fill: "#6F4E37" }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#6F4E37" }} />
              <Tooltip />
              <Line type="monotone" dataKey="score" stroke={ACCENT} strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Top topics */}
        <div className="glass-card sheen p-4">
          <div className="mb-3 text-sm font-semibold text-coffee/80">Top topics driving conversation</div>
          {topics.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={topics} layout="vertical" margin={{ left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(111,78,55,0.12)" />
                <XAxis type="number" tick={{ fontSize: 11, fill: "#6F4E37" }} />
                <YAxis type="category" dataKey="topic" tick={{ fontSize: 11, fill: "#6F4E37" }} width={80} />
                <Tooltip />
                <Bar dataKey="count" fill={ACCENT} radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-sm text-mocha">No topics tagged yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
